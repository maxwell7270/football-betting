"""Hardcoded mock fixtures for development while API-Football is paused."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from packages.models import Fixture


def get_mock_fixtures() -> List[Fixture]:
    """Return 4 hardcoded development fixtures matching current odds-api.io events."""
    return [
        Fixture(
            fixture_id=900001,
            league_key="premier_league",
            kickoff_utc=datetime(2026, 5, 10, 15, 30, tzinfo=timezone.utc),
            home_team="West Ham United",
            away_team="Arsenal",
            status="NS",
        ),
        Fixture(
            fixture_id=900002,
            league_key="bundesliga",
            kickoff_utc=datetime(2026, 5, 16, 13, 30, tzinfo=timezone.utc),
            home_team="Bayern Munich",
            away_team="Cologne",
            status="NS",
        ),
        Fixture(
            fixture_id=900003,
            league_key="la_liga",
            kickoff_utc=datetime(2026, 5, 13, 19, 30, tzinfo=timezone.utc),
            home_team="Deportivo Alaves",
            away_team="Barcelona",
            status="NS",
        ),
        Fixture(
            fixture_id=900004,
            league_key="serie_a",
            kickoff_utc=datetime(2026, 5, 3, 16, 0, tzinfo=timezone.utc),
            home_team="Juventus Turin",
            away_team="Hellas Verona",
            status="NS",
        ),
    ]