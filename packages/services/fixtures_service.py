"""Fixtures service — thin wrapper around the API-Football provider."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from packages.config import LEAGUE_IDS, Config
from packages.logging_utils import get_logger
from packages.models import Fixture
from packages.providers.api_football import ApiFootballClient, ApiFootballError

log = get_logger(__name__)


@dataclass
class FixturesService:
    config: Config
    client: ApiFootballClient

    def fetch_all_upcoming(self) -> Dict[str, List[Fixture]]:
        results: Dict[str, List[Fixture]] = {}
        for league_key in self.config.betting_leagues:
            if league_key not in LEAGUE_IDS:
                log.error("Unknown league key '%s' — skipping", league_key)
                results[league_key] = []
                continue
            try:
                fixtures = self.client.fetch_upcoming_fixtures(league_key)
                results[league_key] = fixtures
                log.info("Fetched %d fixtures for %s", len(fixtures), league_key)
            except ApiFootballError as exc:
                log.error("Failed to fetch fixtures for %s: %s", league_key, exc)
                results[league_key] = []
        return results