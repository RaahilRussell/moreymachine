#!/usr/bin/env python
"""Build the current Sixers roster-world artifact."""

from __future__ import annotations

from moreymachine.context.roster_world import build_roster_world


def main() -> int:
    result = build_roster_world()
    print(f"Roster world rows: {result.rows}")
    print(f"Core players: {result.core_players}")
    print(f"Open slots: {result.open_slots}")
    print(f"Blocked slots: {result.blocked_slots}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

