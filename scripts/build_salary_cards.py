#!/usr/bin/env python
"""Build salary and acquisition cards."""

from __future__ import annotations

from moreymachine.models.salary_cards import build_salary_cards


def main() -> int:
    result = build_salary_cards()
    print(f"Rows: {result.rows}")
    print(f"Manual review: {result.manual_review}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
