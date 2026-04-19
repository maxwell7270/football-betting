"""odds-api.io client. Supports 1x2 and Over/Under 2.5 markets."""
from __future__ import annotations

import json
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from packages.config import Config
from packages.logging_utils import get_logger
from packages.models import Fixture, OddsQuote

log = get_logger(__name__)


# Best-effort slug mapping for odds-api.io football leagues. Based on the
# documented pattern "<country>-<competition>"; adjust if the provider uses
# different slugs for your account.
LEAGUE_SLUGS: Dict[str, str] = {
    "premier_league": "england-premier-league",
    "bundesliga": "germany-bundesliga",
    "la_liga": "spain-laliga",
    "serie_a": "italy-serie-a",
}


# Cache TTL for /odds responses (seconds). 30 minutes.
ODDS_CACHE_TTL_SECONDS = 30 * 60

# Persistent cache file for /odds responses, relative to the project root.
ODDS_CACHE_FILE = Path("data/odds_cache.json")


class OddsApiIoError(Exception):
    """Raised when odds-api.io cannot be queried successfully."""


def _normalize(name: str) -> str:
    """Lowercase, strip accents, collapse spaces — for loose team-name matching."""
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)
    )
    return " ".join(stripped.lower().split())


def _teams_match(fx: Fixture, event: Dict[str, Any]) -> bool:
    home = _normalize(str(event.get("home", "")))
    away = _normalize(str(event.get("away", "")))
    fx_home = _normalize(fx.home_team)
    fx_away = _normalize(fx.away_team)
    if not home or not away:
        return False
    return _name_match(fx_home, home) and _name_match(fx_away, away)


def _name_match(a: str, b: str) -> bool:
    """Loose match: containment in either direction, or shared first token."""
    if a in b or b in a:
        return True
    a_first = a.split(" ", 1)[0]
    b_first = b.split(" ", 1)[0]
    # Require at least 4 chars to avoid spurious hits like "FC" or short prefixes.
    return len(a_first) >= 4 and a_first == b_first


def _event_summary(event: Dict[str, Any]) -> str:
    """Compact one-line representation of an event for debug logs."""
    league = event.get("league")
    if isinstance(league, dict):
        league_repr = league.get("slug") or league.get("name") or "?"
    else:
        league_repr = league if league is not None else "?"
    return (
        f"id={event.get('id')} "
        f"home={event.get('home')!r} away={event.get('away')!r} "
        f"date={event.get('date')} league={league_repr}"
    )


@dataclass
class OddsApiIoClient:
    config: Config
    # Lazy-loaded file-backed cache: { "<event_id>|<bookmakers>": {"fetched_at": float, "payload": dict} }
    _odds_cache: Optional[Dict[str, Dict[str, Any]]] = field(default=None, repr=False)

    def _ensure_cache_loaded(self) -> Dict[str, Dict[str, Any]]:
        if self._odds_cache is not None:
            return self._odds_cache
        try:
            if ODDS_CACHE_FILE.exists():
                with ODDS_CACHE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    raise ValueError(f"cache root is not a dict (got {type(data).__name__})")
                self._odds_cache = data
                log.info(
                    "odds cache loaded from %s (%d entries)",
                    ODDS_CACHE_FILE, len(self._odds_cache),
                )
            else:
                self._odds_cache = {}
                log.info("odds cache file %s not found — starting empty", ODDS_CACHE_FILE)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            log.warning(
                "odds cache file %s unreadable (%s) — rebuilding clean", ODDS_CACHE_FILE, exc,
            )
            self._odds_cache = {}
        return self._odds_cache

    def _save_cache(self) -> None:
        if self._odds_cache is None:
            return
        try:
            ODDS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with ODDS_CACHE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(self._odds_cache, fh)
        except OSError as exc:
            log.warning("Failed to persist odds cache to %s: %s", ODDS_CACHE_FILE, exc)

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        url = f"{self.config.odds_api_io_base_url.rstrip('/')}/{path.lstrip('/')}"
        params = {"apiKey": self.config.odds_api_io_key, **params}
        attempts = max(1, self.config.retry_attempts)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    url, params=params, timeout=self.config.request_timeout_s
                )
                response.raise_for_status()
                return response.json()
            except requests.Timeout as exc:
                last_error = exc
                log.warning("Timeout on %s (attempt %d/%d)", url, attempt, attempts)
            except requests.HTTPError as exc:
                last_error = exc
                log.warning(
                    "HTTP error on %s (attempt %d/%d): %s",
                    url, attempt, attempts, exc,
                )
            except requests.RequestException as exc:
                last_error = exc
                log.warning(
                    "Request error on %s (attempt %d/%d): %s",
                    url, attempt, attempts, exc,
                )

            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 5))

        raise OddsApiIoError(
            f"Failed to GET {url} after {attempts} attempts: {last_error}"
        )

    def _find_event_id(self, fixture: Fixture) -> Optional[int]:
        slug = LEAGUE_SLUGS.get(fixture.league_key)
        if not slug:
            log.warning(
                "No odds-api.io slug for league_key=%s — skipping", fixture.league_key
            )
            return None

        # --- DEBUG: log the outgoing events request (API key redacted). ---
        events_path = f"{self.config.odds_api_io_base_url.rstrip('/')}/events"
        debug_params = {"sport": "football", "league": slug, "apiKey": "***"}
        log.info(
            "odds-api.io events lookup | league_key=%s slug=%s url=%s params=%s",
            fixture.league_key, slug, events_path, debug_params,
        )

        try:
            events = self._get("/events", {"sport": "football", "league": slug})
        except OddsApiIoError as exc:
            log.error("Failed to list events for %s: %s", slug, exc)
            return None

        # --- DEBUG: report response shape and a preview of the first events. ---
        if not isinstance(events, list):
            top_keys: List[str] = []
            if isinstance(events, dict):
                top_keys = list(events.keys())
            log.info(
                "odds-api.io /events response is not a list | type=%s top_keys=%s",
                type(events).__name__, top_keys,
            )
            log.info(
                "No events list returned for league=%s (fixture %s vs %s)",
                slug, fixture.home_team, fixture.away_team,
            )
            return None

        log.info("odds-api.io /events returned %d events for slug=%s", len(events), slug)
        for i, ev in enumerate(events[:5]):
            if isinstance(ev, dict):
                log.info("  event[%d] %s", i, _event_summary(ev))
            else:
                log.info("  event[%d] (non-dict) type=%s", i, type(ev).__name__)

        if not events:
            log.info(
                "No events returned for league=%s (fixture %s vs %s)",
                slug, fixture.home_team, fixture.away_team,
            )
            return None

        for event in events:
            if not isinstance(event, dict):
                continue
            if _teams_match(fixture, event):
                event_id = event.get("id")
                if event_id is not None:
                    return int(event_id)

        # --- DEBUG: show normalized names of the fixture and first few events. ---
        fx_home_n = _normalize(fixture.home_team)
        fx_away_n = _normalize(fixture.away_team)
        log.info(
            "Match failed | fixture normalized home=%r away=%r", fx_home_n, fx_away_n
        )
        shown = 0
        for ev in events:
            if not isinstance(ev, dict):
                continue
            log.info(
                "  candidate normalized home=%r away=%r (raw home=%r away=%r)",
                _normalize(str(ev.get("home", ""))),
                _normalize(str(ev.get("away", ""))),
                ev.get("home"), ev.get("away"),
            )
            shown += 1
            if shown >= 5:
                break

        log.info(
            "Unresolved fixture match: %s vs %s (%s) — no event id found",
            fixture.home_team, fixture.away_team, slug,
        )
        return None

    def fetch_odds_for_fixture(self, fixture: Fixture) -> List[OddsQuote]:
        """Fetch 1x2 and Over/Under 2.5 odds for one fixture across configured bookmakers."""
        event_id = self._find_event_id(fixture)
        if event_id is None:
            return []

        bookmakers = ",".join(self.config.odds_api_io_bookmakers)
        params: Dict[str, Any] = {"eventId": event_id}
        if bookmakers:
            params["bookmakers"] = bookmakers
        # Cache key uses the effective bookmakers param (empty string when absent).
        bookmakers_key = str(params.get("bookmakers", ""))
        cache_key = f"{event_id}|{bookmakers_key}"
        cache = self._ensure_cache_loaded()

        cached = cache.get(cache_key)
        payload: Any = None
        if isinstance(cached, dict):
            fetched_at = cached.get("fetched_at")
            cached_payload = cached.get("payload")
            if isinstance(fetched_at, (int, float)) and isinstance(cached_payload, dict):
                age = time.time() - float(fetched_at)
                if 0 <= age < ODDS_CACHE_TTL_SECONDS:
                    log.info(
                        "odds cache HIT | event_id=%s bookmakers=%r age=%.1fs",
                        event_id, bookmakers_key, age,
                    )
                    payload = cached_payload
                else:
                    log.info(
                        "odds cache MISS (expired) | event_id=%s bookmakers=%r age=%.1fs",
                        event_id, bookmakers_key, age,
                    )
                    cache.pop(cache_key, None)
            else:
                log.info(
                    "odds cache MISS (malformed entry) | event_id=%s bookmakers=%r",
                    event_id, bookmakers_key,
                )
                cache.pop(cache_key, None)
        else:
            log.info(
                "odds cache MISS | event_id=%s bookmakers=%r", event_id, bookmakers_key
            )

        if payload is None:
            try:
                payload = self._get("/odds", params)
            except OddsApiIoError as exc:
                log.error("Failed to fetch odds for fixture_id=%d: %s", fixture.fixture_id, exc)
                return []

        if not isinstance(payload, dict):
            log.warning(
                "Unexpected odds payload for fixture_id=%d: %r",
                fixture.fixture_id, type(payload),
            )
            return []

        books = payload.get("bookmakers")
        if not isinstance(books, dict) or not books:
            log.info("No bookmaker odds returned for fixture_id=%d", fixture.fixture_id)
            return []

        # Only store on successful, non-empty odds payloads.
        if cache_key not in cache:
            cache[cache_key] = {"fetched_at": time.time(), "payload": payload}
            self._save_cache()

        return _parse_odds(fixture, books)


def _parse_odds(fixture: Fixture, books: Dict[str, Any]) -> List[OddsQuote]:
    now = datetime.now(timezone.utc)
    quotes: List[OddsQuote] = []

    for bookmaker_name, markets in books.items():
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            market_name = str(market.get("name", "")).strip()
            odds_list = market.get("odds")
            if not isinstance(odds_list, list) or not odds_list:
                continue

            if market_name.upper() == "ML":
                quotes.extend(_parse_1x2(fixture, bookmaker_name, odds_list, now))
                continue

            # DEBUG: log non-ML markets so we can inspect their raw shape and
            # confirm the ou25 parser sees what we expect.
            preview = odds_list[:3]
            log.info(
                "non-ML market | bookmaker=%s market=%r entries=%d sample=%s",
                bookmaker_name, market_name, len(odds_list), preview,
            )

            if market_name.lower() in {"totals", "over/under", "over under"}:
                quotes.extend(_parse_ou25(fixture, bookmaker_name, odds_list, now))
            # Everything else is ignored — we only care about 1x2 and ou25.

    return quotes


def _parse_1x2(
    fixture: Fixture, bookmaker: str, odds_list: List[Any], now: datetime
) -> List[OddsQuote]:
    out: List[OddsQuote] = []
    entry = odds_list[0] if isinstance(odds_list[0], dict) else None
    if entry is None:
        return out
    for selection in ("home", "draw", "away"):
        raw = entry.get(selection)
        price = _to_float(raw)
        if price is None:
            continue
        out.append(
            OddsQuote(
                fixture_id=fixture.fixture_id,
                league_key=fixture.league_key,
                market="1x2",
                selection=selection,
                bookmaker=bookmaker,
                odds=price,
                fetched_at_utc=now,
            )
        )
    return out


def _parse_ou25(
    fixture: Fixture, bookmaker: str, odds_list: List[Any], now: datetime
) -> List[OddsQuote]:
    out: List[OddsQuote] = []
    for entry in odds_list:
        if not isinstance(entry, dict):
            continue
        # odds-api.io uses `hdp` for the Totals line; keep other common keys
        # as fallbacks in case a bookmaker feed differs.
        line = _to_float(
            entry.get("hdp")
            if entry.get("hdp") is not None
            else entry.get("line")
            or entry.get("total")
            or entry.get("point")
        )
        if line is None or abs(line - 2.5) > 1e-6:
            continue
        for selection in ("over", "under"):
            price = _to_float(entry.get(selection))
            if price is None:
                continue
            out.append(
                OddsQuote(
                    fixture_id=fixture.fixture_id,
                    league_key=fixture.league_key,
                    market="ou25",
                    selection=selection,
                    bookmaker=bookmaker,
                    odds=price,
                    fetched_at_utc=now,
                )
            )
    return out


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None