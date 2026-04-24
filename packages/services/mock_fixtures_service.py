"""Mock fixtures for local/dev pipeline testing.

API-Football is paused while quota is limited/exhausted.
These fixtures are aligned with odds-api.io events visible around 2026-04-24.
"""
from __future__ import annotations

from datetime import datetime, timezone

from packages.models import Fixture


def _utc(value: str) -> datetime:
    """Parse an ISO datetime string as UTC."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def get_mock_fixtures() -> list[Fixture]:
    """Return mock fixtures close to kickoff for odds-api.io dev testing."""
    fixtures = [
        # Premier League
        Fixture(
            fixture_id=900101,
            league_key="premier_league",
            home_team="Sunderland",
            away_team="Nottingham Forest",
            kickoff_utc=_utc("2026-04-24T19:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900102,
            league_key="premier_league",
            home_team="Fulham",
            away_team="Aston Villa",
            kickoff_utc=_utc("2026-04-25T11:30:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900103,
            league_key="premier_league",
            home_team="Liverpool",
            away_team="Crystal Palace",
            kickoff_utc=_utc("2026-04-25T14:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900104,
            league_key="premier_league",
            home_team="West Ham United",
            away_team="Everton",
            kickoff_utc=_utc("2026-04-25T14:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900105,
            league_key="premier_league",
            home_team="Arsenal",
            away_team="Newcastle United",
            kickoff_utc=_utc("2026-04-25T16:30:00Z"),
            status="NS",
        ),

        # Bundesliga
        Fixture(
            fixture_id=900201,
            league_key="bundesliga",
            home_team="RB Leipzig",
            away_team="Union Berlin",
            kickoff_utc=_utc("2026-04-24T18:30:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900202,
            league_key="bundesliga",
            home_team="FSV Mainz",
            away_team="Bayern Munich",
            kickoff_utc=_utc("2026-04-25T13:30:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900203,
            league_key="bundesliga",
            home_team="1. FC Cologne",
            away_team="Bayer Leverkusen",
            kickoff_utc=_utc("2026-04-25T13:30:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900204,
            league_key="bundesliga",
            home_team="Hamburger SV",
            away_team="TSG Hoffenheim",
            kickoff_utc=_utc("2026-04-25T16:30:00Z"),
            status="NS",
        ),

        # La Liga
        Fixture(
            fixture_id=900301,
            league_key="la_liga",
            home_team="Real Betis Seville",
            away_team="Real Madrid",
            kickoff_utc=_utc("2026-04-24T19:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900302,
            league_key="la_liga",
            home_team="Deportivo Alaves",
            away_team="RCD Mallorca",
            kickoff_utc=_utc("2026-04-25T12:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900303,
            league_key="la_liga",
            home_team="Getafe",
            away_team="Barcelona",
            kickoff_utc=_utc("2026-04-25T14:15:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900304,
            league_key="la_liga",
            home_team="Atletico Madrid",
            away_team="Athletic Bilbao",
            kickoff_utc=_utc("2026-04-25T19:00:00Z"),
            status="NS",
        ),

        # Serie A
        Fixture(
            fixture_id=900401,
            league_key="serie_a",
            home_team="SSC Napoli",
            away_team="US Cremonese",
            kickoff_utc=_utc("2026-04-24T18:45:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900402,
            league_key="serie_a",
            home_team="Parma",
            away_team="Pisa",
            kickoff_utc=_utc("2026-04-25T13:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900403,
            league_key="serie_a",
            home_team="Bologna",
            away_team="Roma",
            kickoff_utc=_utc("2026-04-25T16:00:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900404,
            league_key="serie_a",
            home_team="Hellas Verona",
            away_team="Lecce",
            kickoff_utc=_utc("2026-04-25T18:45:00Z"),
            status="NS",
        ),
        Fixture(
            fixture_id=900405,
            league_key="serie_a",
            home_team="AC Milan",
            away_team="Juventus Turin",
            kickoff_utc=_utc("2026-04-26T18:45:00Z"),
            status="NS",
        ),
    ]

    return fixtures