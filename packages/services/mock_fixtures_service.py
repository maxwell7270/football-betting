"""Hardcoded mock fixtures for development while API-Football is paused."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from packages.models import Fixture


def get_mock_fixtures() -> List[Fixture]:
    """Return 4 hardcoded development fixtures kicking off in the next 1–3 days."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    return [
        Fixture(
            fixture_id=900001,
            league_key="premier_league",
            kickoff_utc=now + timedelta(days=1, hours=2),
            home_team="Crystal Palace",
            away_team="West Ham United",
            status="NS",
        ),
        Fixture(
            fixture_id=900002,
            league_key="bundesliga",
            kickoff_utc=now + timedelta(days=2, hours=3),
            home_team="Bayern Munich",
            away_team="VfB Stuttgart",
            status="NS",
        ),
        Fixture(
            fixture_id=900003,
            league_key="la_liga",
            kickoff_utc=now + timedelta(days=2, hours=5),
            home_team="Real Madrid",
            away_team="Deportivo Alaves",
            status="NS",
        ),
        Fixture(
            fixture_id=900004,
            league_key="serie_a",
            kickoff_utc=now + timedelta(days=1, hours=6),
            home_team="Juventus Turin",
            away_team="Bologna FC",
            status="NS",
        ),
    ]