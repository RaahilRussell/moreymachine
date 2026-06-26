#!/usr/bin/env python
"""Validate generated player-profile artifacts."""

from __future__ import annotations

from moreymachine.models.reasoning_validation_v2 import (
    PLAYER_PROFILE_VALIDATION_REPORT_PATH,
    validate_player_profile_artifacts,
)


def main() -> int:
    """Run player-profile validation and write a Markdown report."""
    result = validate_player_profile_artifacts()
    PLAYER_PROFILE_VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAYER_PROFILE_VALIDATION_REPORT_PATH.write_text(
        result.to_markdown(), encoding="utf-8"
    )
    print(
        "Player profile validation: "
        f"errors={len(result.errors)} warnings={len(result.warnings)}"
    )
    print(f"Report: {PLAYER_PROFILE_VALIDATION_REPORT_PATH}")
    if result.errors:
        for issue in result.errors[:20]:
            who = f" [{issue.player_name}]" if issue.player_name else ""
            print(f"FAIL {issue.gate}{who}: {issue.message}")
        return 1
    print("PLAYER PROFILE VALIDATION PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
