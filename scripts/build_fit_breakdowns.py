#!/usr/bin/env python
"""Build player fit-score breakdown artifacts."""

from __future__ import annotations

from moreymachine.models.fit_breakdown import build_fit_breakdowns


def main() -> int:
    result = build_fit_breakdowns()
    print(f"Rows: {result.rows}")
    print(f"Parquet: {result.parquet_path}")
    print(f"JSON: {result.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
