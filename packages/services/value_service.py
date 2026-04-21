"""Value-bet detection for 1x2 markets using market consensus (no model)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from packages.models import OddsQuote


SELECTIONS_1X2 = ("home", "draw", "away")


def implied_probability(odds: float) -> float:
    """Implied probability from decimal odds."""
    return 1.0 / odds


def normalize_probabilities(probs: List[float]) -> List[float]:
    """Remove bookmaker margin by normalizing probabilities to sum to 1."""
    total = sum(probs)
    if total <= 0:
        return [0.0 for _ in probs]
    return [p / total for p in probs]


def value_edge(prob: float, odds: float) -> float:
    """Edge of a bet given fair probability and bookmaker odds."""
    return prob * odds - 1.0


def _is_usable(q: OddsQuote) -> bool:
    if q.market != "1x2":
        return False
    if q.selection not in SELECTIONS_1X2:
        return False
    if not q.bookmaker:
        return False
    try:
        return float(q.odds) > 0
    except (TypeError, ValueError):
        return False


def _latest_per_book_selection(quotes: List[OddsQuote]) -> List[OddsQuote]:
    """Keep only the last entry (input order) per (bookmaker, selection)."""
    latest: Dict[tuple, OddsQuote] = {}
    for q in quotes:
        if not _is_usable(q):
            continue
        latest[(q.bookmaker, q.selection)] = q
    return list(latest.values())


def _consensus_probabilities(
    quotes: List[OddsQuote],
) -> Optional[Dict[str, float]]:
    """Average implied probability per selection, then normalize.

    Returns None if home/draw/away are not all covered by at least one bookmaker.
    """
    probs_by_selection: Dict[str, List[float]] = {s: [] for s in SELECTIONS_1X2}
    for q in quotes:
        probs_by_selection[q.selection].append(implied_probability(float(q.odds)))

    if not all(probs_by_selection[s] for s in SELECTIONS_1X2):
        return None

    avg_probs = [
        sum(probs_by_selection[s]) / len(probs_by_selection[s]) for s in SELECTIONS_1X2
    ]
    normalized = normalize_probabilities(avg_probs)
    return dict(zip(SELECTIONS_1X2, normalized))


def analyze_fixture_1x2(quotes: List[OddsQuote]) -> Optional[Dict[str, Any]]:
    """Analyze 1x2 value for a single fixture's odds quotes.

    Returns None if the fixture cannot be analyzed (no usable 1x2 quotes,
    or incomplete consensus across home/draw/away).
    """
    deduped = _latest_per_book_selection(quotes)
    if not deduped:
        return None

    consensus = _consensus_probabilities(deduped)
    if consensus is None:
        return None

    fair_odds = {s: 1.0 / consensus[s] for s in SELECTIONS_1X2}
    fixture_id = deduped[0].fixture_id

    per_bookmaker: List[Dict[str, Any]] = []
    for q in deduped:
        prob = consensus[q.selection]
        odds = float(q.odds)
        edge = value_edge(prob, odds)
        per_bookmaker.append(
            {
                "bookmaker": q.bookmaker,
                "selection": q.selection,
                "odds": odds,
                "fair_odds": fair_odds[q.selection],
                "edge": edge,
                "is_value": edge > 0,
            }
        )

    return {
        "fixture_id": fixture_id,
        "market": "1x2",
        "consensus_probabilities": consensus,
        "fair_odds": fair_odds,
        "per_bookmaker": per_bookmaker,
    }


def analyze_value(
    odds_by_fixture: Dict[int, List[OddsQuote]],
) -> Dict[int, Dict[str, Any]]:
    """Run 1x2 value analysis across all fixtures.

    Accepts the same dict shape produced by OddsService.fetch_odds_for_fixtures.
    Fixtures without a complete 1x2 consensus are skipped.
    """
    results: Dict[int, Dict[str, Any]] = {}
    for fixture_id, quotes in odds_by_fixture.items():
        analysis = analyze_fixture_1x2(quotes)
        if analysis is not None:
            results[fixture_id] = analysis
    return results