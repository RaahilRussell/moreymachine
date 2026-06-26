#!/usr/bin/env python
"""Build structural contender blueprint artifacts."""

from __future__ import annotations

from moreymachine.features.contender_blueprints import build_contender_blueprints


def main() -> int:
    result = build_contender_blueprints()
    print(f"Blueprints: {result.blueprints}")
    print(f"Team archetypes: {result.team_archetypes}")
    print(f"Blueprint output: {result.blueprint_path}")
    print(f"Archetype output: {result.archetype_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

