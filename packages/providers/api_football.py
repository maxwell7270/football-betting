"""API-Football client. Fetches upcoming fixtures only."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from packages.config import LEAGUE_IDS, Config
from packages.logging_utils import get_logger
from packages.models import Fixture

log = get_logger(__name__)


class ApiFootballError(Exception):
    """Raised when the API-Football service cannot be queried successfully."""


@dataclass
class ApiFootballClient:
    config: Config

    def _headers(self) -> Dict[str, str]:
        return {
            "x-apisports-key": self.config.api_key,
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        attempts = max(1, self.config.retry_attempts)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.config.request_timeout_s,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ApiFootballError(f"Unexpected response type: {type(data)}")
                # API-Football returns errors inside the body even on HTTP 200.
                api_errors = data.get("errors")
                if api_errors:
                    if isinstance(api_errors, dict) and api_errors:
                        raise ApiFootballError(f"API errors: {api_errors}")
                    if isinstance(api_errors, list) and api_errors:
                        raise ApiFootballError(f"API errors: {api_errors}")
                return data
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

        raise ApiFootballError(
            f"Failed to GET {url} after {attempts} attempts: {last_error}"
        )

    def fetch_upcoming_fixtures(self, league_key: str) -> List[Fixture]:
        """Fetch upcoming fixtures for one configured league within the lookahead window."""
        if league_key not in LEAGUE_IDS:
            raise ApiFootballError(f"Unknown league key: {league_key}")

        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=self.config.odds_lookahead_days)

        params = {
            "league": LEAGUE_IDS[league_key],
            "season": self.config.season,
            "from": today.isoformat(),
            "to": end.isoformat(),
            "timezone": "UTC",
        }

        data = self._get("/fixtures", params)
        raw_response = data.get("response")
        if not isinstance(raw_response, list):
            log.warning(
                "Unexpected 'response' field for %s: %r", league_key, type(raw_response)
            )
            return []

        fixtures: List[Fixture] = []
        for item in raw_response:
            parsed = _parse_fixture(item, league_key)
            if parsed is not None:
                fixtures.append(parsed)
        return fixtures


def _parse_fixture(item: Dict[str, Any], league_key: str) -> Fixture | None:
    try:
        fx = item["fixture"]
        teams = item["teams"]
        kickoff_raw = fx["date"]  # ISO 8601 with timezone
        kickoff_utc = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        return Fixture(
            fixture_id=int(fx["id"]),
            league_key=league_key,
            kickoff_utc=kickoff_utc,
            home_team=str(teams["home"]["name"]),
            away_team=str(teams["away"]["name"]),
            status=str(fx.get("status", {}).get("short", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("Skipping malformed fixture payload (%s): %s", league_key, exc)
        return None