#!/usr/bin/env python
"""Build player help-impact summaries."""

from __future__ import annotations

from moreymachine.models.help_impact import build_help_impact


def main() -> int:
    result = build_help_impact()
    print(f"Rows: {result.rows}")
    print(f"Players with help areas: {result.players_with_help}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
