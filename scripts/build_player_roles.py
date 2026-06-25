"""Build player role dimensions and archetypes from real bio + tracking data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.player_roles import build_player_roles  # noqa: E402


def main() -> int:
    """CLI entry point for the player roles build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", help="Season to build; defaults to latest.")
    args = parser.parse_args()

    result = build_player_roles(season=args.season)
    print(f"Player roles built for {result.season}: {result.rows} players")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
