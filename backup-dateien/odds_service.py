"""Service layer for fetching and aggregating odds per fixture."""
from __future__ import annotations

from typing import List

from packages.logging_utils import get_logger
from packages.models import Fixture, OddsQuote
from packages.providers.odds_api_io import OddsApiIoClient

log = get_logger(__name__)


class OddsService:
    """High-level service to fetch odds for fixtures."""

    def __init__(self, odds_client: OddsApiIoClient) -> None:
        self.odds_client = odds_client

    def fetch_odds_for_fixture(self, fixture: Fixture) -> List[OddsQuote]:
        """Fetch odds for a single fixture."""
        try:
            odds = self.odds_client.fetch_odds_for_fixture(fixture)
        except Exception as exc:
            log.error(
                "Failed to fetch odds for fixture_id=%s (%s vs %s): %s",
                fixture.fixture_id,
                fixture.home_team,
                fixture.away_team,
                exc,
            )
            return []

        log.info(
            "Fetched %d odds entries for fixture_id=%s (%s vs %s)",
            len(odds),
            fixture.fixture_id,
            fixture.home_team,
            fixture.away_team,
        )
        return odds

    def fetch_odds_for_fixtures(self, fixtures: List[Fixture]) -> List[OddsQuote]:
        """Fetch odds for multiple fixtures and aggregate."""
        all_odds: List[OddsQuote] = []

        for fixture in fixtures:
            odds = self.fetch_odds_for_fixture(fixture)

            if not odds:
                log.info(
                    "No odds found for fixture_id=%s (%s vs %s)",
                    fixture.fixture_id,
                    fixture.home_team,
                    fixture.away_team,
                )
                continue

            log.info(
                "Fixture_id=%s: %d odds entries",
                fixture.fixture_id,
                len(odds),
            )

            all_odds.extend(odds)

        log.info("Total odds entries fetched: %d", len(all_odds))
        return all_odds