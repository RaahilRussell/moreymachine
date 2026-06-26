#!/usr/bin/env python
"""Build evidence-backed player skill profiles."""

from __future__ import annotations

from moreymachine.features.player_skill_profiles import build_player_skill_profiles


def main() -> int:
    result = build_player_skill_profiles()
    print(f"Rows: {result.rows}")
    print(f"Spacing claims allowed: {result.spacing_claims_allowed}")
    print(f"Defense claims allowed: {result.defense_claims_allowed}")
    print(f"Rim claims allowed: {result.rim_claims_allowed}")
    print(f"Output: {result.output_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
