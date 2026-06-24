"""Rank free agent or trade candidate fits for the target team."""

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
from moreymachine.features.roster_gaps import ROSTER_GAPS_PATH  # noqa: E402
from moreymachine.models.contender_model import CONTENDER_MODEL_PATH  # noqa: E402
from moreymachine.models.fit_model import (  # noqa: E402
    CANDIDATE_FIT_RANKINGS_PATH,
    build_candidate_rankings,
)
from moreymachine.utils.paths import CANDIDATES_PATH  # noqa: E402


def main() -> int:
    """CLI entry point for candidate fit ranking."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI", help="Target team (context only).")
    parser.add_argument("--players", type=Path, default=PLAYER_SEASONS_BASIC_PATH)
    parser.add_argument("--roster-gaps", type=Path, default=ROSTER_GAPS_PATH)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=CANDIDATES_PATH,
        help="Real candidate watchlist (player+salary). Restricts the pool.",
    )
    parser.add_argument(
        "--player-archetypes",
        type=Path,
        default=PLAYER_ARCHETYPES_PATH,
        help="Optional player archetype assignments.",
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        help="Optional CSV or Parquet with salary or contract estimates.",
    )
    parser.add_argument(
        "--contender-model",
        type=Path,
        default=CONTENDER_MODEL_PATH,
        help="Optional trained contender model artifact for context.",
    )
    parser.add_argument("--season", help="Season to rank; defaults to latest row.")
    parser.add_argument("--top-n", type=int, help="Save only the top N candidates.")
    parser.add_argument("--output", type=Path, default=CANDIDATE_FIT_RANKINGS_PATH)
    args = parser.parse_args()

    candidates_path = args.candidates if args.candidates.exists() else None
    result = build_candidate_rankings(
        player_stats_path=args.players,
        roster_gaps_path=args.roster_gaps,
        player_archetypes_path=args.player_archetypes,
        contracts_path=args.contracts,
        candidates_path=candidates_path,
        contender_model_path=args.contender_model,
        output_path=args.output,
        season=args.season,
        top_n=args.top_n,
    )

    print(f"Ranked candidates: {result.rows}")
    if result.top_candidate is not None:
        print(f"Top candidate: {result.top_candidate}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
