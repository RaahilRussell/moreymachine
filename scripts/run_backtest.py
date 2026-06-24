"""Run chronological offseason backtests for MoreyMachine rankings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.player_archetypes import (  # noqa: E402
    PLAYER_ARCHETYPES_PATH,
    PLAYER_SEASONS_BASIC_PATH,
)
from moreymachine.features.roster_archetypes import (  # noqa: E402
    TEAM_ROSTER_ARCHETYPES_PATH,
)
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH  # noqa: E402
from moreymachine.models.backtest import (  # noqa: E402
    BACKTEST_RANKINGS_PATH,
    BACKTEST_RESULTS_PATH,
    BACKTEST_SUMMARY_PATH,
    build_backtest,
)


def main() -> int:
    """CLI entry point for offseason backtesting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--players", type=Path, default=PLAYER_SEASONS_BASIC_PATH)
    parser.add_argument(
        "--team-fingerprints",
        type=Path,
        default=TEAM_FINGERPRINTS_PATH,
    )
    parser.add_argument(
        "--player-archetypes",
        type=Path,
        default=PLAYER_ARCHETYPES_PATH,
    )
    parser.add_argument(
        "--team-roster-archetypes",
        type=Path,
        default=TEAM_ROSTER_ARCHETYPES_PATH,
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        help="Optional CSV or Parquet with salary or contract estimates.",
    )
    parser.add_argument("--target-team", default="PHI")
    parser.add_argument("--start-season")
    parser.add_argument("--end-season")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--results-output", type=Path, default=BACKTEST_RESULTS_PATH)
    parser.add_argument("--rankings-output", type=Path, default=BACKTEST_RANKINGS_PATH)
    parser.add_argument("--summary-output", type=Path, default=BACKTEST_SUMMARY_PATH)
    args = parser.parse_args()

    result = build_backtest(
        player_stats_path=args.players,
        team_fingerprints_path=args.team_fingerprints,
        player_archetypes_path=args.player_archetypes,
        team_roster_archetypes_path=args.team_roster_archetypes,
        contracts_path=args.contracts,
        results_path=args.results_output,
        rankings_path=args.rankings_output,
        summary_path=args.summary_output,
        target_team=args.target_team,
        start_season=args.start_season,
        end_season=args.end_season,
        top_k=args.top_k,
        random_state=args.random_state,
    )

    print(f"Backtest rows: {result.rows}")
    print(f"Offseasons: {', '.join(result.offseasons)}")
    print(f"Results: {result.results_path}")
    print(f"Rankings: {result.rankings_path}")
    print(f"Summary: {result.summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
