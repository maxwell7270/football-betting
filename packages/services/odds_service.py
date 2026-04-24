"""Service layer for fetching odds for fixtures."""
from __future__ import annotations

from packages.logging_utils import get_logger
from packages.models import Fixture, OddsQuote
from packages.providers.odds_api_io import OddsApiIoClient

log = get_logger(__name__)


class OddsService:
    """Fetch odds for a list of fixtures using the configured odds provider."""

    def __init__(self, client: OddsApiIoClient) -> None:
        self.client = client

    def fetch_odds_for_fixtures(
        self,
        fixtures: list[Fixture],
    ) -> dict[int, list[OddsQuote]]:
        odds_by_fixture: dict[int, list[OddsQuote]] = {}

        for fixture in fixtures:
            try:
                quotes = self.client.fetch_odds_for_fixture(fixture)
            except Exception as exc:
                log.error(
                    "Failed to fetch odds for fixture_id=%d (%s vs %s): %s",
                    fixture.fixture_id,
                    fixture.home_team,
                    fixture.away_team,
                    exc,
                )
                quotes = []

            odds_by_fixture[fixture.fixture_id] = quotes

            log.info(
                "Fetched %d odds entries for fixture_id=%d (%s vs %s)",
                len(quotes),
                fixture.fixture_id,
                fixture.home_team,
                fixture.away_team,
            )

        return odds_by_fixture