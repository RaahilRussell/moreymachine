#!/usr/bin/env python
"""Build the blueprint-driven Sixers gap model."""

from __future__ import annotations

from moreymachine.features.gap_model import build_gap_model


def main() -> int:
    result = build_gap_model()
    print(f"Gaps: {result.gaps}")
    print(f"Critical/significant gaps: {result.critical_or_significant}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
