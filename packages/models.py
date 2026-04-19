"""Domain models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Fixture:
    fixture_id: int
    league_key: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    status: str


@dataclass(frozen=True)
class OddsQuote:
    fixture_id: int
    league_key: str
    market: str        # "1x2" or "ou25"
    selection: str     # 1x2: "home" | "draw" | "away"; ou25: "over" | "under"
    bookmaker: str
    odds: float
    fetched_at_utc: datetime