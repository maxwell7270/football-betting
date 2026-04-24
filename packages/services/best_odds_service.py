"""Best-odds aggregation service."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from packages.models import OddsQuote


def _normalize_bookmaker_name(name: str) -> str:
    """Normalize provider variants to one bookmaker identity."""
    cleaned = name.strip()

    if cleaned.lower() == "bet365 (no latency)":
        return "Bet365"

    return cleaned


def compute_best_odds(odds: list[OddsQuote]) -> list[dict[str, Any]]:
    """Compute best and second-best odds per fixture, market and selection.

    Provider variants like "Bet365 (no latency)" are treated as "Bet365".
    If the same bookmaker appears multiple times for the same selection,
    only that bookmaker's best quote is kept.
    """

    grouped: dict[tuple[int, str, str], dict[str, OddsQuote]] = defaultdict(dict)

    for quote in odds:
        key = (quote.fixture_id, quote.market, quote.selection)
        bookmaker = _normalize_bookmaker_name(quote.bookmaker)

        existing = grouped[key].get(bookmaker)

        if existing is None or quote.odds > existing.odds:
            grouped[key][bookmaker] = quote

    rows: list[dict[str, Any]] = []

    for (fixture_id, market, selection), bookmaker_quotes in grouped.items():
        sorted_quotes = sorted(
            bookmaker_quotes.items(),
            key=lambda item: item[1].odds,
            reverse=True,
        )

        best_bookmaker, best_quote = sorted_quotes[0]

        second_bookmaker = ""
        second_odds_value: float | None = None

        if len(sorted_quotes) > 1:
            second_bookmaker, second_quote = sorted_quotes[1]
            second_odds_value = second_quote.odds

        spread = (
            best_quote.odds - second_odds_value
            if second_odds_value is not None
            else 0.0
        )

        spread_pct = (
            (best_quote.odds / second_odds_value) - 1
            if second_odds_value and second_odds_value > 0
            else 0.0
        )

        rows.append(
            {
                "fixture_id": fixture_id,
                "market": market,
                "selection": selection,
                "best_bookmaker": best_bookmaker,
                "best_odds": f"{best_quote.odds:.2f}",
                "second_bookmaker": second_bookmaker,
                "second_odds": f"{second_odds_value:.2f}" if second_odds_value else "",
                "spread": f"{spread:.2f}",
                "spread_pct": f"{spread_pct:.4f}",
            }
        )

    return rows