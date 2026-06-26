#!/usr/bin/env python
"""Build best-by-need rankings."""

from __future__ import annotations

from moreymachine.models.best_by_need import build_best_by_need


def main() -> int:
    result = build_best_by_need()
    print(f"Rows: {result.rows}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
