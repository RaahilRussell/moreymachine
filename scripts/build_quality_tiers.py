"""Build regular-season quality tiers for team-season data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.playoff_tiers import TEAM_SEASONS_WITH_TIERS_PATH  # noqa: E402
from moreymachine.features.quality_tiers import build_quality_tiers  # noqa: E402


def main() -> int:
    """CLI entry point for regular-season quality tier builds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=TEAM_SEASONS_WITH_TIERS_PATH)
    parser.add_argument("--output", type=Path, default=TEAM_SEASONS_WITH_TIERS_PATH)
    args = parser.parse_args()

    result = build_quality_tiers(input_path=args.input, output_path=args.output)

    print(f"Built rows: {result.rows}")
    print(f"Seasons: {', '.join(result.seasons)}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
