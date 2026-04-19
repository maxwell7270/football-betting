"""Odds service — thin wrapper around the odds-api.io provider."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from packages.logging_utils import get_logger
from packages.models import Fixture, OddsQuote
from packages.providers.odds_api_io import OddsApiIoClient

log = get_logger(__name__)


@dataclass
class OddsService:
    client: OddsApiIoClient

    def fetch_odds_for_fixtures(
        self, fixtures: List[Fixture]
    ) -> Dict[int, List[OddsQuote]]:
        results: Dict[int, List[OddsQuote]] = {}
        for fx in fixtures:
            try:
                quotes = self.client.fetch_odds_for_fixture(fx)
            except Exception as exc:  # noqa: BLE001 — defensive for dev runs
                log.error(
                    "Unexpected error fetching odds for fixture_id=%d (%s vs %s): %s",
                    fx.fixture_id, fx.home_team, fx.away_team, exc,
                )
                quotes = []
            results[fx.fixture_id] = quotes
            log.info(
                "Fetched %d odds entries for fixture_id=%d (%s vs %s)",
                len(quotes), fx.fixture_id, fx.home_team, fx.away_team,
            )
        return results