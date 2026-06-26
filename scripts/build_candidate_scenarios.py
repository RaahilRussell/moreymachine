#!/usr/bin/env python
"""Build scenario rows for every candidate."""

from __future__ import annotations

from moreymachine.models.scenario_engine import build_candidate_scenarios


def main() -> int:
    result = build_candidate_scenarios()
    print(f"Rows: {result.rows}")
    print(f"Candidates: {result.candidates}")
    print(f"Manual review scenarios: {result.manual_review_scenarios}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
