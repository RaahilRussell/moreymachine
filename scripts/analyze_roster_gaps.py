"""Analyze target-team roster gaps against successful team baselines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.roster_archetypes import (  # noqa: E402
    TEAM_ROSTER_ARCHETYPES_PATH,
)
from moreymachine.features.roster_gaps import (  # noqa: E402
    DEFAULT_TARGET_TEAM,
    ROSTER_GAPS_MARKDOWN_PATH,
    ROSTER_GAPS_PATH,
    build_roster_gaps,
)
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH  # noqa: E402


def main() -> int:
    """CLI entry point for roster gap analysis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=TEAM_FINGERPRINTS_PATH)
    parser.add_argument(
        "--roster-archetypes",
        type=Path,
        default=TEAM_ROSTER_ARCHETYPES_PATH,
        help="Optional roster archetype assignments used for same-archetype baselines.",
    )
    parser.add_argument("--target-team", default=DEFAULT_TARGET_TEAM)
    parser.add_argument("--target-season")
    parser.add_argument("--output", type=Path, default=ROSTER_GAPS_PATH)
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=ROSTER_GAPS_MARKDOWN_PATH,
    )
    args = parser.parse_args()

    result = build_roster_gaps(
        input_path=args.input,
        roster_archetypes_path=args.roster_archetypes,
        output_path=args.output,
        markdown_path=args.markdown_output,
        target_team=args.target_team,
        target_season=args.target_season,
    )

    print(f"Built rows: {result.rows}")
    print(f"Target: {result.target_team} {result.target_season}")
    print(f"Parquet report: {result.output_path}")
    print(f"Markdown report: {result.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
