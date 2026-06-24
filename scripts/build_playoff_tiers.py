"""Join manual playoff outcome tiers onto processed team-season data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.playoff_tiers import (  # noqa: E402
    PLAYOFF_TIERS_PATH,
    TEAM_SEASONS_BASIC_PATH,
    TEAM_SEASONS_WITH_TIERS_PATH,
    build_team_seasons_with_tiers,
)


def main() -> int:
    """CLI entry point for building team seasons with playoff tiers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-seasons", type=Path, default=TEAM_SEASONS_BASIC_PATH)
    parser.add_argument("--playoff-tiers", type=Path, default=PLAYOFF_TIERS_PATH)
    parser.add_argument("--output", type=Path, default=TEAM_SEASONS_WITH_TIERS_PATH)
    args = parser.parse_args()

    result = build_team_seasons_with_tiers(
        team_seasons_path=args.team_seasons,
        playoff_tiers_path=args.playoff_tiers,
        output_path=args.output,
    )

    print(f"Built rows: {result.rows}")
    print(f"Seasons: {', '.join(result.seasons)}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
