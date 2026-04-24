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


LEAGUE_SLUGS: Dict[str, str] = {
    "premier_league": "england-premier-league",
    "bundesliga": "germany-bundesliga",
    "la_liga": "spain-laliga",
    "serie_a": "italy-serie-a",
}

ODDS_CACHE_TTL_SECONDS = 30 * 60
ODDS_CACHE_FILE = Path("data/odds_cache.json")

_STRIP_TOKENS = {
    "fc",
    "cf",
    "afc",
    "sc",
    "sv",
    "tsg",
    "vfb",
    "vfl",
    "as",
    "ss",
    "us",
    "ac",
    "rb",
    "calcio",
    "1.",
}

_ALIASES: Dict[str, List[str]] = {
    "bayern": ["bayern munich", "fc bayern", "bayern munchen", "fc bayern munchen"],
    "inter": ["inter milan", "internazionale"],
    "juventus": ["juventus turin", "juve"],
    "west ham": ["west ham united"],
    "napoli": ["ssc napoli"],
    "roma": ["as roma"],
    "lazio": ["ss lazio"],
    "milan": ["ac milan"],
    "bologna": ["bologna fc"],
    "crystal palace": ["crystal palace fc"],
}

_ALIAS_INDEX: Dict[str, str] = {}
for canonical_name, variants in _ALIASES.items():
    _ALIAS_INDEX[canonical_name] = canonical_name
    for variant in variants:
        _ALIAS_INDEX[variant] = canonical_name

CONF_EXACT = "EXACT"
CONF_NORMALIZED = "NORMALIZED"
CONF_ALIAS = "ALIAS"

_KICKOFF_EXACT_S = 2 * 3600
_KICKOFF_WINDOW_S = 7 * 24 * 3600


class OddsApiIoError(Exception):
    """Raised when odds-api.io cannot be queried successfully."""


def _normalize(name: str) -> str:
    """Lowercase, strip accents, collapse spaces."""
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)
    )
    return " ".join(stripped.lower().split())


def _canonical(name: str) -> str:
    """Normalize and strip structural football tokens."""
    tokens = [t for t in _normalize(name).split() if t not in _STRIP_TOKENS]
    return " ".join(tokens)


def _resolve_alias(name: str) -> str:
    """Resolve canonical alias key if known."""
    return _ALIAS_INDEX.get(name, name)


def _parse_event_kickoff(event: Dict[str, Any]) -> Optional[datetime]:
    raw = event.get("date") or event.get("commence_time")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except (TypeError, ValueError):
        return None


def _kickoff_delta_s(fixture: Fixture, event: Dict[str, Any]) -> Optional[float]:
    event_kickoff = _parse_event_kickoff(event)
    if event_kickoff is None:
        return None
    return abs((event_kickoff - fixture.kickoff_utc).total_seconds())


def _match_confidence(fixture: Fixture, event: Dict[str, Any]) -> Optional[str]:
    """Return confidence tier if the event matches the fixture, else None.

    EXACT      — _normalize() alone produces equal names.
    NORMALIZED — _canonical() stripping was required; no alias used.
    ALIAS      — alias resolution was required.

    Substring/partial/fuzzy matching is not used.
    """
    ev_home_raw = str(event.get("home", ""))
    ev_away_raw = str(event.get("away", ""))
    if not ev_home_raw or not ev_away_raw:
        return None

    fx_home_n = _normalize(fixture.home_team)
    fx_away_n = _normalize(fixture.away_team)
    ev_home_n = _normalize(ev_home_raw)
    ev_away_n = _normalize(ev_away_raw)

    fx_home_c = _canonical(fixture.home_team)
    fx_away_c = _canonical(fixture.away_team)
    ev_home_c = _canonical(ev_home_raw)
    ev_away_c = _canonical(ev_away_raw)

    fx_home_r = _resolve_alias(fx_home_c)
    fx_away_r = _resolve_alias(fx_away_c)
    ev_home_r = _resolve_alias(ev_home_c)
    ev_away_r = _resolve_alias(ev_away_c)

    exact_match = (fx_home_n == ev_home_n) and (fx_away_n == ev_away_n)
    strip_match = (fx_home_c == ev_home_c) and (fx_away_c == ev_away_c)
    alias_match = (fx_home_r == ev_home_r) and (fx_away_r == ev_away_r)

    if not exact_match and not strip_match and not alias_match:
        return None

    delta = _kickoff_delta_s(fixture, event)
    if delta is None:
        if exact_match:
            return CONF_EXACT
        if strip_match:
            return CONF_NORMALIZED
        return CONF_ALIAS

    if delta > _KICKOFF_WINDOW_S:
        return None

    if exact_match:
        return CONF_EXACT if delta <= _KICKOFF_EXACT_S else CONF_NORMALIZED
    if strip_match:
        return CONF_NORMALIZED
    return CONF_ALIAS


def _teams_match(fx: Fixture, event: Dict[str, Any]) -> bool:
    return _match_confidence(fx, event) is not None


def _name_match(a: str, b: str) -> bool:
    """Retained for compatibility; exact normalized equality only."""
    return a == b


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
    _odds_cache: Optional[Dict[str, Dict[str, Any]]] = field(default=None, repr=False)
    match_confidence: Dict[int, str] = field(default_factory=dict, repr=False)

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
                    ODDS_CACHE_FILE,
                    len(self._odds_cache),
                )
            else:
                self._odds_cache = {}
                log.info("odds cache file %s not found — starting empty", ODDS_CACHE_FILE)

        except (OSError, ValueError, json.JSONDecodeError) as exc:
            log.warning(
                "odds cache file %s unreadable (%s) — rebuilding clean",
                ODDS_CACHE_FILE,
                exc,
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
                    url,
                    params=params,
                    timeout=self.config.request_timeout_s,
                )
                response.raise_for_status()
                return response.json()

            except requests.Timeout as exc:
                last_error = exc
                log.warning("Timeout on %s (attempt %d/%d)", url, attempt, attempts)

            except requests.HTTPError as exc:
                last_error = exc
                log.warning(
                    "HTTP error on %s attempt %d/%d: %s",
                    url,
                    attempt,
                    attempts,
                    exc,
                )

            except requests.RequestException as exc:
                last_error = exc
                log.warning(
                    "Request error on %s attempt %d/%d: %s",
                    url,
                    attempt,
                    attempts,
                    exc,
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
                "No odds-api.io slug for league_key=%s — skipping",
                fixture.league_key,
            )
            return None

        events_path = f"{self.config.odds_api_io_base_url.rstrip('/')}/events"
        debug_params = {"sport": "football", "league": slug, "apiKey": "***"}
        log.debug(
            "odds-api.io events lookup | league_key=%s slug=%s url=%s params=%s",
            fixture.league_key,
            slug,
            events_path,
            debug_params,
        )

        try:
            events = self._get("/events", {"sport": "football", "league": slug})
        except OddsApiIoError as exc:
            log.error("Failed to list events for %s: %s", slug, exc)
            return None

        if not isinstance(events, list):
            top_keys: List[str] = list(events.keys()) if isinstance(events, dict) else []
            log.debug(
                "odds-api.io /events response is not a list | type=%s top_keys=%s",
                type(events).__name__,
                top_keys,
            )
            log.warning(
                "match FAILED | fixture=%s vs %s | slug=%s | checked=0 | top_candidates=[]",
                fixture.home_team,
                fixture.away_team,
                slug,
            )
            return None

        log.debug("odds-api.io /events returned %d events for slug=%s", len(events), slug)
        for i, ev in enumerate(events[:5]):
            if isinstance(ev, dict):
                log.debug("  event[%d] %s", i, _event_summary(ev))
            else:
                log.debug("  event[%d] (non-dict) type=%s", i, type(ev).__name__)

        for event in events:
            if not isinstance(event, dict):
                continue

            confidence = _match_confidence(fixture, event)
            if confidence in (CONF_EXACT, CONF_NORMALIZED, CONF_ALIAS):
                event_id = event.get("id")
                if event_id is None:
                    continue

                delta = _kickoff_delta_s(fixture, event)
                delta_min = int(delta / 60) if delta is not None else "?"

                log.info(
                    "match OK | confidence=%s | fixture=%s vs %s | event_id=%s | "
                    "matched=%s vs %s | kickoff_delta=%smin",
                    confidence,
                    fixture.home_team,
                    fixture.away_team,
                    event_id,
                    event.get("home"),
                    event.get("away"),
                    delta_min,
                )

                self.match_confidence[fixture.fixture_id] = confidence
                return int(event_id)

        fx_tokens = (
            set(_canonical(fixture.home_team).split())
            | set(_canonical(fixture.away_team).split())
        )

        def _candidate_score(ev: Dict[str, Any]) -> int:
            ev_tokens = (
                set(_canonical(str(ev.get("home", ""))).split())
                | set(_canonical(str(ev.get("away", ""))).split())
            )
            return len(fx_tokens & ev_tokens)

        ranked = sorted(
            [ev for ev in events if isinstance(ev, dict)],
            key=lambda ev: (
                -_candidate_score(ev),
                str(ev.get("home", "")),
                str(ev.get("away", "")),
            ),
        )

        top = [
            "'"
            + _canonical(str(ev.get("home", "")))
            + "' vs '"
            + _canonical(str(ev.get("away", "")))
            + "'"
            for ev in ranked[:3]
        ]

        log.warning(
            "match FAILED | fixture=%s vs %s | slug=%s | checked=%d | top_candidates=%s",
            fixture.home_team,
            fixture.away_team,
            slug,
            len(events),
            top,
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
                        event_id,
                        bookmakers_key,
                        age,
                    )
                    payload = cached_payload
                else:
                    log.info(
                        "odds cache MISS (expired) | event_id=%s bookmakers=%r age=%.1fs",
                        event_id,
                        bookmakers_key,
                        age,
                    )
                    cache.pop(cache_key, None)
            else:
                log.info(
                    "odds cache MISS (malformed entry) | event_id=%s bookmakers=%r",
                    event_id,
                    bookmakers_key,
                )
                cache.pop(cache_key, None)
        else:
            log.info(
                "odds cache MISS | event_id=%s bookmakers=%r",
                event_id,
                bookmakers_key,
            )

        if payload is None:
            try:
                payload = self._get("/odds", params)
            except OddsApiIoError as exc:
                log.error(
                    "Failed to fetch odds for fixture_id=%d event_id=%s bookmakers=%r: %s",
                    fixture.fixture_id,
                    event_id,
                    bookmakers_key,
                    exc,
                )
                return []

        if not isinstance(payload, dict):
            log.warning(
                "Unexpected odds payload | fixture_id=%d | event_id=%s | bookmakers=%r | type=%s",
                fixture.fixture_id,
                event_id,
                bookmakers_key,
                type(payload).__name__,
            )
            return []

        books = payload.get("bookmakers")
        if not isinstance(books, dict) or not books:
            log.info(
                "No bookmaker odds returned | fixture_id=%d | event_id=%s | bookmakers=%r",
                fixture.fixture_id,
                event_id,
                bookmakers_key,
            )
            return []

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

            log.debug(
                "non-ML market | bookmaker=%s market=%r entries=%d sample=%s",
                bookmaker_name,
                market_name,
                len(odds_list),
                odds_list[:3],
            )

            if market_name.lower() in {"totals", "over/under", "over under"}:
                quotes.extend(_parse_ou25(fixture, bookmaker_name, odds_list, now))

    return quotes


def _parse_1x2(
    fixture: Fixture,
    bookmaker: str,
    odds_list: List[Any],
    now: datetime,
) -> List[OddsQuote]:
    out: List[OddsQuote] = []
    entry = odds_list[0] if odds_list and isinstance(odds_list[0], dict) else None

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
    fixture: Fixture,
    bookmaker: str,
    odds_list: List[Any],
    now: datetime,
) -> List[OddsQuote]:
    out: List[OddsQuote] = []

    for entry in odds_list:
        if not isinstance(entry, dict):
            continue

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