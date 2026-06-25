"""Refresh current-season real NBA data, with cached fallback and warnings.

This is the *only* place expensive live fetches happen. The Streamlit app never
calls it on page load; it reads the cached Parquet files this script writes.

Behaviour:

* Refreshes current-season team/player stats, player bio, player tracking, and
  contracts from real sources (nba_api + Basketball-Reference).
* Stamps ``pulled_at`` / ``data_mode`` on every raw table.
* If a live refresh fails, the previously cached real Parquet is kept and a
  clear WARNING is printed. Demo/fake data is never substituted.
* Writes ``data/reports/data_freshness_report.md``.

Usage:
    python scripts/refresh_current_data.py --season latest
    python scripts/refresh_current_data.py --season 2025-26 --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.refresh import refresh_current_data  # noqa: E402


def main() -> int:
    """CLI entry point for the real-data refresh."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        default="latest",
        help="'latest' or an explicit season label like 2025-26.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the raw JSON cache and re-download from source.",
    )
    args = parser.parse_args()

    result = refresh_current_data(season=args.season, force=args.force)
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
