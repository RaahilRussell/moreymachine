#!/usr/bin/env python
"""Build multidimensional player categorization tags."""

from __future__ import annotations

from moreymachine.features.player_categorization import build_player_categorization


def main() -> int:
    result = build_player_categorization()
    print(f"Rows: {result.rows}")
    print(f"Manual review tags: {result.manual_review}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
