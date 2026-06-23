"""Fetch NBA team and player season data into local Parquet files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.fetch_nba import fetch_nba_basic_data  # noqa: E402
from moreymachine.utils.config import load_settings  # noqa: E402
from moreymachine.utils.logging import configure_logging, get_logger  # noqa: E402


def main() -> int:
    """CLI entry point for the NBA data fetch."""
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-season", default=settings.nba_start_season)
    parser.add_argument("--latest-season", default=settings.nba_latest_season)
    parser.add_argument("--cache-dir", type=Path, default=settings.nba_api_cache_dir)
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=settings.data_dir / "processed",
    )
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--request-sleep-seconds", type=float, default=0.6)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info(
        "Fetching NBA data from %s through %s",
        args.start_season,
        args.latest_season,
    )

    result = fetch_nba_basic_data(
        start_season=args.start_season,
        latest_season=args.latest_season,
        cache_dir=args.cache_dir,
        processed_dir=args.processed_dir,
        max_retries=args.max_retries,
        request_sleep_seconds=args.request_sleep_seconds,
        retry_sleep_seconds=args.retry_sleep_seconds,
        timeout=args.timeout,
    )

    print(f"Fetched seasons: {', '.join(result.seasons)}")
    print(f"Team rows: {result.team_rows} -> {result.team_path}")
    print(f"Player rows: {result.player_rows} -> {result.player_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
