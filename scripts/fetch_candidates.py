"""Build a real candidate watchlist (players + salaries) for ranking.

Pulls the candidate pool from real nba_api player data and salaries from
Basketball-Reference's contracts page, writing data/manual/candidates.csv.
Salaries that cannot be matched online are left blank (never invented) for
manual entry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.fetch_candidates import build_candidates_csv  # noqa: E402
from moreymachine.utils.paths import CANDIDATES_PATH, PLAYER_SEASONS_PATH  # noqa: E402


def main() -> int:
    """CLI entry point for building the candidate watchlist."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI", help="Team to exclude from the pool.")
    parser.add_argument("--players", type=Path, default=PLAYER_SEASONS_PATH)
    parser.add_argument("--output", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--min-minutes", type=float, default=1000.0)
    parser.add_argument(
        "--no-refresh-salaries",
        action="store_true",
        help="Use cached Basketball-Reference HTML instead of fetching live.",
    )
    args = parser.parse_args()

    result = build_candidates_csv(
        player_seasons_path=args.players,
        output_path=args.output,
        target_team=args.team,
        min_minutes=args.min_minutes,
        refresh_salaries=not args.no_refresh_salaries,
    )

    print(f"Candidates: {result.rows} -> {result.output_path}")
    print(
        f"Salaries matched: {result.salaries_matched} "
        f"(source: {result.salary_source})"
    )
    if result.salaries_matched == 0:
        print(
            "WARNING: no salaries were matched online. Fill expected_salary in "
            "data/manual/candidates.csv with real values before trusting "
            "contract-value scores."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
