"""Daily pipeline (dev mode): log mock fixtures and fetch odds from odds-api.io.

API-Football is paused while the monthly quota is exhausted.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.config import load_config  # noqa: E402
from packages.logging_utils import configure_logging, get_logger  # noqa: E402
from packages.models import Fixture, OddsQuote  # noqa: E402
from packages.providers.odds_api_io import OddsApiIoClient  # noqa: E402
from packages.services.best_odds_service import compute_best_odds  # noqa: E402
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


def _export_odds_quotes(
    odds_by_fixture: dict[int, list[OddsQuote]],
    fixtures_by_id: dict[int, Fixture],
    tz: ZoneInfo,
) -> None:
    rows: list[list[str]] = []
    timestamp = datetime.now().isoformat(timespec="seconds")

    for fixture_id, quotes in odds_by_fixture.items():
        fx = fixtures_by_id.get(fixture_id)

        for q in quotes:
            rows.append(
                [
                    timestamp,
                    q.fixture_id,
                    fx.league_key if fx else q.league_key,
                    fx.home_team if fx else "",
                    fx.away_team if fx else "",
                    fx.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                    if fx
                    else "",
                    q.market,
                    q.selection,
                    q.bookmaker,
                    f"{q.odds:.2f}",
                    q.fetched_at_utc.isoformat() if q.fetched_at_utc else "",
                ]
            )

    if not rows:
        return

    csv_path = Path("data/odds_quotes.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "timestamp",
        "fixture_id",
        "league_key",
        "home_team",
        "away_team",
        "kickoff",
        "market",
        "selection",
        "bookmaker",
        "odds",
        "fetched_at_utc",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _export_best_odds(rows: list[dict]) -> None:
    if not rows:
        return

    csv_path = Path("data/best_odds.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "fixture_id",
        "market",
        "selection",
        "best_bookmaker",
        "best_odds",
        "second_bookmaker",
        "second_odds",
        "spread",
        "spread_pct",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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

    fixtures = get_mock_fixtures()
    fixtures_by_id = {fx.fixture_id: fx for fx in fixtures}

    log.info("Loaded %d mock fixtures", len(fixtures))

    for fx in sorted(fixtures, key=lambda f: f.kickoff_utc):
        log.info(_format_fixture_line(fx, tz))

    odds_client = OddsApiIoClient(config=config)
    odds_service = OddsService(client=odds_client)
    odds_by_fixture = odds_service.fetch_odds_for_fixtures(fixtures)

    total_quotes = 0
    all_odds: list[OddsQuote] = []

    for fx in fixtures:
        quotes = odds_by_fixture.get(fx.fixture_id, [])

        if not quotes:
            log.info(
                "No odds found for fixture_id=%d (%s vs %s)",
                fx.fixture_id,
                fx.home_team,
                fx.away_team,
            )
            continue

        for q in quotes:
            log.info(_format_odds_line(q))

        log.info("Fixture_id=%d: %d odds entries", fx.fixture_id, len(quotes))

        total_quotes += len(quotes)
        all_odds.extend(quotes)

    log.info("Total odds entries fetched: %d", total_quotes)

    _export_odds_quotes(odds_by_fixture, fixtures_by_id, tz)

    if total_quotes:
        log.info("Exported %d odds quote(s) to data/odds_quotes.csv", total_quotes)

    best_odds = compute_best_odds(all_odds)
    _export_best_odds(best_odds)

    if best_odds:
        log.info("Exported %d best odds row(s) to data/best_odds.csv", len(best_odds))

    value_results = analyze_value(odds_by_fixture)
    value_rows: list[dict] = []

    for fixture_id, analysis in value_results.items():
        for entry in analysis["per_bookmaker"]:
            if entry["edge"] <= config.value_min_edge:
                continue

            log.info(
                "VALUE BET | fixture_id=%d | bookmaker=%s | selection=%s | "
                "odds=%.2f | fair_odds=%.2f | edge=%.4f",
                fixture_id,
                entry["bookmaker"],
                entry["selection"],
                entry["odds"],
                entry["fair_odds"],
                entry["edge"],
            )

            value_rows.append(
                {
                    "fixture_id": fixture_id,
                    "market": analysis["market"],
                    "bookmaker": entry["bookmaker"],
                    "selection": entry["selection"],
                    "odds": entry["odds"],
                    "fair_odds": entry["fair_odds"],
                    "edge": entry["edge"],
                }
            )

    if not value_rows:
        log.info("No 1x2 value bets found")

    if value_rows:
        csv_path = Path("data/value_bets.csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat(timespec="seconds")

        header = [
            "timestamp",
            "fixture_id",
            "league_key",
            "home_team",
            "away_team",
            "kickoff",
            "market",
            "bookmaker",
            "selection",
            "odds",
            "fair_odds",
            "edge",
        ]

        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)

            for r in value_rows:
                fx = fixtures_by_id.get(r["fixture_id"])

                writer.writerow(
                    [
                        timestamp,
                        r["fixture_id"],
                        fx.league_key if fx else "",
                        fx.home_team if fx else "",
                        fx.away_team if fx else "",
                        fx.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M")
                        if fx
                        else "",
                        r["market"],
                        r["bookmaker"],
                        r["selection"],
                        f"{r['odds']:.2f}",
                        f"{r['fair_odds']:.2f}",
                        f"{r['edge']:.4f}",
                    ]
                )

        log.info("Exported %d value bet(s) to data/value_bets.csv", len(value_rows))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())