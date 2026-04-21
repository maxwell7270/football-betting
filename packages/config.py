"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


# Internal league key -> API-Football league id
LEAGUE_IDS: Dict[str, int] = {
    "premier_league": 39,
    "bundesliga": 78,
    "la_liga": 140,
    "serie_a": 135,
}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def current_season(now: datetime | None = None) -> int:
    """Return the current football season year.

    If current month >= 7 -> current year, otherwise previous year.
    """
    now = now or datetime.utcnow()
    return now.year if now.month >= 7 else now.year - 1


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    request_timeout_ms: int
    retry_attempts: int
    enable_logging: bool
    timezone: str
    betting_leagues: List[str]
    odds_lookahead_days: int
    odds_api_io_key: str = ""
    odds_api_io_base_url: str = "https://api.odds-api.io/v3"
    odds_api_io_bookmakers: List[str] = field(default_factory=list)
    value_min_edge: float = 0.02
    season: int = field(default_factory=current_season)

    @property
    def request_timeout_s(self) -> float:
        return self.request_timeout_ms / 1000.0


def load_config() -> Config:
    return Config(
        api_key=os.getenv("API_FOOTBALL_KEY", ""),
        base_url=os.getenv("API_SPORT_BASE_URL", "https://v3.football.api-sports.io"),
        request_timeout_ms=_get_int("REQUEST_TIMEOUT_MS", 10000),
        retry_attempts=_get_int("RETRY_ATTEMPTS", 3),
        enable_logging=_get_bool("ENABLE_LOGGING", True),
        timezone=os.getenv("TIMEZONE", "Europe/Zurich"),
        betting_leagues=_get_list(
            "BETTING_LEAGUES",
            ["premier_league", "bundesliga", "la_liga", "serie_a"],
        ),
        odds_lookahead_days=_get_int("ODDS_LOOKAHEAD_DAYS", 7),
        odds_api_io_key=os.getenv("ODDS_API_IO_KEY", ""),
        odds_api_io_base_url=os.getenv(
            "ODDS_API_IO_BASE_URL", "https://api.odds-api.io/v3"
        ),
        odds_api_io_bookmakers=_get_list("ODDS_API_IO_BOOKMAKERS", ["Bet365"]),
        value_min_edge=_get_float("VALUE_MIN_EDGE", 0.02),
    )