#!/usr/bin/env python
"""Build full player profile artifacts."""

from __future__ import annotations

from moreymachine.models.player_profile_builder import build_player_profiles


def main() -> int:
    result = build_player_profiles()
    print(f"Rows: {result.rows}")
    print(f"Complete/mostly complete: {result.complete_or_mostly_complete}")
    print(f"Profiles: {result.profiles_path}")
    print(f"JSON: {result.json_path}")
    print(f"Index: {result.index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
