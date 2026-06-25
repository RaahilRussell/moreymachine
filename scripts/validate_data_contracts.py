"""Validate every core table against its data contract; fail loudly on errors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.contracts import validate_all  # noqa: E402
from moreymachine.utils.paths import REPORTS_DATA_DIR  # noqa: E402

REPORT_PATH = REPORTS_DATA_DIR / "data_contract_validation.md"


def main() -> int:
    """CLI entry point for data-contract validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-provenance",
        action="store_true",
        help="Treat missing provenance columns as errors, not warnings.",
    )
    args = parser.parse_args()

    reports = validate_all()
    lines = ["# Data Contract Validation", ""]
    lines.append("| Table | Present | Errors | Warnings |")
    lines.append("| --- | --- | --- | --- |")

    error_count = 0
    for report in reports:
        errors = list(report.errors)
        warnings = list(report.warnings)
        if args.strict_provenance:
            errors += warnings
            warnings = []
        error_count += len(errors)
        present = "yes" if report.present else "**no**"
        lines.append(
            f"| {report.key} | {present} | "
            f"{'; '.join(errors) if errors else '-'} | "
            f"{'; '.join(warnings) if warnings else '-'} |"
        )
        status = "OK" if not errors else "FAIL"
        detail = "; ".join(errors + warnings) or "clean"
        print(f"[{status}] {report.key}: {detail}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")

    if error_count:
        print(f"\nDATA CONTRACTS FAILED: {error_count} error(s).")
        return 1
    print("\nDATA CONTRACTS PASSED (errors=0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
