"""Refresh recent NBA transactions into data/processed/transactions.parquet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.transactions import refresh_transactions  # noqa: E402


def main() -> int:
    """CLI entry point for transaction refresh."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End date, YYYY-MM-DD.")
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use cached Spotrac HTML if available.",
    )
    args = parser.parse_args()

    result = refresh_transactions(
        start_date=args.start_date,
        end_date=args.end_date,
        refresh=not args.no_refresh,
    )
    print(f"Transactions: {result.rows}")
    print(f"Range: {result.start_date} .. {result.end_date}")
    print(f"Source: {result.source_url}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
