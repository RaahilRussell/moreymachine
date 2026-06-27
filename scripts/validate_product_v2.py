#!/usr/bin/env python
"""Validate the GM operating-system product artifacts."""

from __future__ import annotations

import argparse

from moreymachine.product_validation import validate_team_product


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_team_product(team=args.team)
    print(result.to_markdown())
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
