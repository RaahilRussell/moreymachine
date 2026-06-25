"""Analyze Sixers roster gaps: statistical + roster-composition diagnosis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.sixers_diagnosis import build_sixers_diagnosis  # noqa: E402


def main() -> int:
    """CLI entry point for the expanded roster diagnosis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-team", "--team", dest="target_team", default="PHI")
    args = parser.parse_args()

    result = build_sixers_diagnosis(team=args.target_team)
    print(f"Diagnosis rows: {result.rows}")
    print(f"Target: {result.target_team} {result.target_season}")
    print(f"Parquet report: {result.output_path}")
    print(f"Markdown report: {result.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
