#!/usr/bin/env python
"""Build candidate-to-current-roster compatibility rows."""

from __future__ import annotations

from moreymachine.features.compatibility_matrix import build_compatibility_matrix


def main() -> int:
    result = build_compatibility_matrix()
    print(f"Rows: {result.rows}")
    print(f"Embiid conflicts: {result.embiid_conflicts}")
    print(f"Maxey conflicts: {result.maxey_conflicts}")
    print(f"George positive rows: {result.george_positive_rows}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
