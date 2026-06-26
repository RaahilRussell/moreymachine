#!/usr/bin/env python
"""Validate the v2 reasoning system across generated artifacts."""

from __future__ import annotations

from moreymachine.models.reasoning_validation_v2 import (
    REASONING_VALIDATION_REPORT_PATH,
    validate_reasoning_v2,
)


def main() -> int:
    """Run v2 reasoning validation and write a Markdown report."""
    result = validate_reasoning_v2()
    REASONING_VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REASONING_VALIDATION_REPORT_PATH.write_text(
        result.to_markdown(), encoding="utf-8"
    )
    print(
        "Reasoning validation v2: "
        f"errors={len(result.errors)} warnings={len(result.warnings)}"
    )
    print(f"Report: {REASONING_VALIDATION_REPORT_PATH}")
    if result.errors:
        for issue in result.errors[:20]:
            who = f" [{issue.player_name}]" if issue.player_name else ""
            print(f"FAIL {issue.gate}{who}: {issue.message}")
        return 1
    print("REASONING VALIDATION V2 PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
