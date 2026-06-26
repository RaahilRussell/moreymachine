#!/usr/bin/env python
"""Export markdown scouting reports."""

from __future__ import annotations

from moreymachine.reports.scouting_report import export_scouting_reports


def main() -> int:
    result = export_scouting_reports()
    print(f"Reports: {result.reports}")
    print(f"Output dir: {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
