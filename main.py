from __future__ import annotations

import argparse

from app.engine import NHLEngine
from app.services.board_service import BoardService


def main() -> None:
    parser = argparse.ArgumentParser(description="NHL betting board generator")
    parser.add_argument("--run-type", choices=["early", "final"], default="early")
    parser.add_argument("--min-score", type=int, default=60)
    parser.add_argument("--all-bets", action="store_true", help="Show all bets, not only playable ones")
    parser.add_argument(
        "--changes-report",
        action="store_true",
        help="When running final, compare with latest early snapshot and print a changes report",
    )
    args = parser.parse_args()

    engine = NHLEngine()
    snapshot = engine.run_board(args.run_type)

    board_min_score = 0 if args.all_bets else args.min_score
    board_service = BoardService(min_score=board_min_score, playable_only=not args.all_bets)

    print(board_service.render_board(snapshot))

    if args.changes_report and args.run_type == "final":
        early_snapshot = engine.snapshot_store.latest_snapshot("early")
        if early_snapshot:
            deltas = engine.comparison_service.compare(early_snapshot, snapshot)
            print("\n" + "=" * 72 + "\n")
            print(board_service.render_changes_report(early_snapshot, snapshot, deltas))
        else:
            print("\nNo early snapshot found for comparison.")


if __name__ == "__main__":
    main()