"""Daily pipeline (dev mode): log mock fixtures and fetch odds from odds-api.io.

API-Football is paused while the monthly quota is exhausted.
"""
from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Allow `python jobs/run_daily_pipeline.py` from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.config import load_config  # noqa: E402
from packages.logging_utils import configure_logging, get_logger  # noqa: E402
from packages.models import Fixture, OddsQuote  # noqa: E402
from packages.providers.odds_api_io import OddsApiIoClient  # noqa: E402
from packages.services.mock_fixtures_service import get_mock_fixtures  # noqa: E402
from packages.services.odds_service import OddsService  # noqa: E402
from packages.services.value_service import analyze_value  # noqa: E402


def _resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _format_fixture_line(fx: Fixture, tz: ZoneInfo) -> str:
    local = fx.kickoff_utc.astimezone(tz)
    return (
        f"[{fx.league_key}] {local.strftime('%Y-%m-%d %H:%M')} | "
        f"{fx.home_team} vs {fx.away_team} | fixture_id={fx.fixture_id}"
    )


def _format_odds_line(q: OddsQuote) -> str:
    return (
        f"[{q.league_key}] fixture_id={q.fixture_id} | market={q.market} | "
        f"selection={q.selection} | bookmaker={q.bookmaker} | odds={q.odds:.2f}"
    )


def main() -> int:
    config = load_config()
    configure_logging(enabled=config.enable_logging)
    log = get_logger("pipeline")

    if not config.odds_api_io_key:
        log.error("ODDS_API_IO_KEY is not set")
        return 1

    tz = _resolve_tz(config.timezone)
    log.info(
        "Starting daily pipeline (dev/mock) | bookmakers=%s tz=%s",
        ",".join(config.odds_api_io_bookmakers) or "(none)",
        tz.key,
    )

    # 1. Load mock fixtures and log them.
    fixtures = get_mock_fixtures()
    log.info("Loaded %d mock fixtures", len(fixtures))
    for fx in sorted(fixtures, key=lambda f: f.kickoff_utc):
        log.info(_format_fixture_line(fx, tz))

    # 2. Fetch odds for each mock fixture.
    odds_client = OddsApiIoClient(config=config)
    odds_service = OddsService(client=odds_client)
    odds_by_fixture = odds_service.fetch_odds_for_fixtures(fixtures)

    # 3. Log odds per fixture.
    total_quotes = 0
    for fx in fixtures:
        quotes = odds_by_fixture.get(fx.fixture_id, [])
        if not quotes:
            log.info(
                "No odds found for fixture_id=%d (%s vs %s)",
                fx.fixture_id, fx.home_team, fx.away_team,
            )
            continue
        for q in quotes:
            log.info(_format_odds_line(q))
        log.info("Fixture_id=%d: %d odds entries", fx.fixture_id, len(quotes))
        total_quotes += len(quotes)

    log.info("Total odds entries fetched: %d", total_quotes)

    # 4. Value-bet detection (1x2 only, consensus-based).
    value_results = analyze_value(odds_by_fixture)
    value_lines_logged = 0
    for fixture_id, analysis in value_results.items():
        for entry in analysis["per_bookmaker"]:
            if not entry["is_value"]:
                continue
            log.info(
                "VALUE BET | fixture_id=%d | bookmaker=%s | selection=%s | "
                "odds=%.2f | fair_odds=%.2f | edge=%.4f",
                fixture_id, entry["bookmaker"], entry["selection"],
                entry["odds"], entry["fair_odds"], entry["edge"],
            )
            value_lines_logged += 1
    if value_lines_logged == 0:
        log.info("No 1x2 value bets found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())