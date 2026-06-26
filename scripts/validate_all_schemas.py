#!/usr/bin/env python
"""Validate all registered MoreyMachine artifact schemas."""

from __future__ import annotations

from moreymachine.schemas.common import summarize_results
from moreymachine.schemas.validation import failed_results, validate_all_schemas
from moreymachine.utils.paths import REPORTS_DATA_DIR

REPORT_PATH = REPORTS_DATA_DIR / "schema_validation.md"


def main() -> int:
    """Run schema validation and write a Markdown report."""
    results = validate_all_schemas()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(summarize_results(results))

    for result in results:
        if result.errors:
            status = "FAIL"
        elif result.present:
            status = "PASS"
        else:
            status = "SKIP"
        print(
            f"[{status}] {result.schema_name}: "
            f"errors={len(result.errors)} warnings={len(result.warnings)}"
        )

    failures = failed_results(results)
    print(f"\nReport: {REPORT_PATH}")
    if failures:
        print(f"SCHEMA VALIDATION FAILED (failed={len(failures)}).")
        return 1
    print("SCHEMA VALIDATION PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

