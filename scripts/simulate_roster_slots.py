#!/usr/bin/env python
"""Simulate candidate roster slots and minutes contexts."""

from __future__ import annotations

from moreymachine.features.roster_simulation import simulate_roster_slots


def main() -> int:
    result = simulate_roster_slots()
    print(f"Rows: {result.rows}")
    print(f"No clear role: {result.no_clear_role}")
    print(f"Center overlap flags: {result.center_overlap_flags}")
    print(f"Starter possible: {result.starter_possible}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
