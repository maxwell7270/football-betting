"""Value-bet analysis using multi-bookmaker best-odds aggregation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from packages.models import OddsQuote


def _implied_prob(odds: float) -> float:
    return 1.0 / odds


def _normalize_book_probs(book_quotes: List[OddsQuote]) -> Dict[str, float]:
    raw = {
        q.selection: _implied_prob(q.odds)
        for q in book_quotes
        if q.market == "1x2" and q.odds > 1.0
    }

    total = sum(raw.values())
    if total <= 0:
        return {}

    return {selection: prob / total for selection, prob in raw.items()}


def analyze_value(
    odds_by_fixture: Dict[int, List[OddsQuote]],
    min_bookmakers: int = 2,
) -> Dict[int, Dict[str, Any]]:
    """Detect value bets using best available odds vs bookmaker consensus.

    Logic:
    - use only 1x2 markets
    - require at least `min_bookmakers` complete bookmaker price sets
    - normalize each bookmaker's implied probabilities
    - calculate consensus fair probability per selection
    - select best odds per selection
    - calculate edge = best_odds * consensus_probability - 1
    """

    results: Dict[int, Dict[str, Any]] = {}

    for fixture_id, quotes in odds_by_fixture.items():
        one_x_two = [
            q for q in quotes
            if q.market == "1x2"
            and q.selection in {"home", "draw", "away"}
            and q.odds > 1.0
        ]

        if not one_x_two:
            continue

        by_bookmaker: Dict[str, List[OddsQuote]] = defaultdict(list)
        for q in one_x_two:
            by_bookmaker[q.bookmaker].append(q)

        complete_books: Dict[str, List[OddsQuote]] = {}
        for bookmaker, book_quotes in by_bookmaker.items():
            selections = {q.selection for q in book_quotes}
            if {"home", "draw", "away"}.issubset(selections):
                complete_books[bookmaker] = book_quotes

        if len(complete_books) < min_bookmakers:
            continue

        normalized_by_book: Dict[str, Dict[str, float]] = {}
        for bookmaker, book_quotes in complete_books.items():
            normalized = _normalize_book_probs(book_quotes)
            if {"home", "draw", "away"}.issubset(normalized.keys()):
                normalized_by_book[bookmaker] = normalized

        if len(normalized_by_book) < min_bookmakers:
            continue

        consensus_prob: Dict[str, float] = {}
        for selection in ("home", "draw", "away"):
            probs = [
                book_probs[selection]
                for book_probs in normalized_by_book.values()
                if selection in book_probs
            ]
            if probs:
                consensus_prob[selection] = sum(probs) / len(probs)

        if {"home", "draw", "away"} - set(consensus_prob.keys()):
            continue

        best_by_selection: Dict[str, OddsQuote] = {}
        for selection in ("home", "draw", "away"):
            selection_quotes = [
                q for q in one_x_two
                if q.selection == selection and q.bookmaker in normalized_by_book
            ]
            if not selection_quotes:
                continue
            best_by_selection[selection] = max(selection_quotes, key=lambda q: q.odds)

        per_bookmaker: List[Dict[str, Any]] = []

        for selection, best_quote in best_by_selection.items():
            fair_prob = consensus_prob[selection]
            fair_odds = 1.0 / fair_prob if fair_prob > 0 else 0.0
            edge = best_quote.odds * fair_prob - 1.0

            per_bookmaker.append({
                "bookmaker": best_quote.bookmaker,
                "selection": selection,
                "odds": best_quote.odds,
                "fair_odds": fair_odds,
                "edge": edge,
                "consensus_probability": fair_prob,
                "bookmakers_used": len(normalized_by_book),
            })

        if per_bookmaker:
            results[fixture_id] = {
                "market": "1x2",
                "method": "best_odds_vs_consensus",
                "bookmakers_used": len(normalized_by_book),
                "per_bookmaker": per_bookmaker,
            }

    return results