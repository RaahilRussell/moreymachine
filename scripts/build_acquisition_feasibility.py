#!/usr/bin/env python
"""Build acquisition and contract feasibility artifacts."""

from __future__ import annotations

from moreymachine.features.acquisition_feasibility import (
    build_acquisition_feasibility,
)


def main() -> int:
    result = build_acquisition_feasibility()
    print(f"Rows: {result.rows}")
    print(f"Manual review required: {result.manual_review_required}")
    print(f"Unknown paths: {result.unknown_paths}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
