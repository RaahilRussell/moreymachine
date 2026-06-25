"""Build the explanation-first Sixers target boards split by feasibility."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.models.target_board import build_target_boards  # noqa: E402


def main() -> int:
    """CLI entry point for the target board build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI", help="Target team (context only).")
    args = parser.parse_args()

    result = build_target_boards()
    print(f"Target board for {args.team}:")
    print(f"  All candidates:        {result.all_rows}")
    print(f"  Realistic board:       {result.realistic_rows}")
    print(f"  Priority targets:      {result.priority_targets} (cap 10)")
    for key, path in result.outputs.items():
        print(f"  {key:>22}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
