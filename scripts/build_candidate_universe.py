"""Classify the acquisition candidate universe and split out the Sixers roster."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.candidate_universe import (  # noqa: E402
    build_candidate_universe,
)


def main() -> int:
    """CLI entry point for the candidate universe build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--team", default="PHI", help="Target team (PHI roster excluded)."
    )
    parser.add_argument("--season", help="Season to classify; defaults to latest.")
    args = parser.parse_args()

    result = build_candidate_universe(season=args.season, team=args.team)
    print(f"Candidate universe: {result.universe_rows} acquisition candidates")
    print(f"Current roster reference: {result.roster_rows} players")
    print("Candidate type counts:")
    for candidate_type, count in sorted(result.type_counts.items()):
        print(f"  {candidate_type}: {count}")
    print(f"Universe: {result.universe_path}")
    print(f"Roster:   {result.roster_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
