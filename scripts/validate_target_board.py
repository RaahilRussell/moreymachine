"""Validate the target boards against hard quality gates; fail loudly on regress."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.models.board_validation import validate_boards  # noqa: E402
from moreymachine.utils.paths import TARGET_BOARD_VALIDATION_PATH  # noqa: E402


def main() -> int:
    """CLI entry point for target board validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI", help="Target team (context only).")
    parser.add_argument(
        "--report",
        type=Path,
        default=TARGET_BOARD_VALIDATION_PATH,
        help="Where to write the Markdown validation report.",
    )
    args = parser.parse_args()

    report = validate_boards()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.to_markdown(), encoding="utf-8")

    for gate in report.gates:
        status = "PASS" if gate.passed else "FAIL"
        print(f"[{status}] {gate.name}: {gate.detail}")
    print(f"\nReport: {args.report}")

    if not report.passed:
        print(f"\nVALIDATION FAILED: {len(report.failures)} gate(s) tripped.")
        return 1
    print("\nVALIDATION PASSED: all gates green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
