"""Refresh current-season real NBA data, with cached fallback and warnings.

This is the *only* place expensive live fetches happen. The Streamlit app never
calls it on page load; it reads the cached Parquet files this script writes.

Behaviour:

* Refreshes current-season team/player stats, player bio, player tracking, and
  contracts from real sources (nba_api + Basketball-Reference).
* If a live refresh fails, the previously cached real Parquet is kept and a
  clear WARNING is printed. Demo/fake data is never substituted.
* Writes ``data/reports/data_freshness_report.md`` and stamps ``pulled_at``.

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

from moreymachine.data.cache import JsonFileCache  # noqa: E402
from moreymachine.data.fetch_bio_tracking import (  # noqa: E402
    fetch_player_bio,
    fetch_player_tracking,
)
from moreymachine.data.fetch_contracts import build_contracts  # noqa: E402
from moreymachine.data.fetch_nba import (  # noqa: E402
    fetch_nba_data,
    infer_latest_season,
)
from moreymachine.data.freshness import (  # noqa: E402
    render_freshness_markdown,
    summarize_freshness,
)
from moreymachine.utils.paths import (  # noqa: E402
    DATA_FRESHNESS_REPORT_PATH,
    NBA_API_RAW_DIR,
)


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

    season = infer_latest_season() if args.season == "latest" else args.season
    print(f"Refreshing real data for season {season} (force={args.force})\n")

    if args.force:
        _clear_season_cache(season)

    statuses: list[str] = []

    statuses.append(
        _step(
            "team/player season stats",
            lambda: _refresh_stats(season),
        )
    )
    statuses.append(_step("player bio", lambda: fetch_player_bio(season=season)))
    statuses.append(
        _step("player tracking", lambda: fetch_player_tracking(season=season))
    )
    statuses.append(
        _step("contracts", lambda: build_contracts(refresh=True))
    )

    summaries = summarize_freshness()
    markdown = render_freshness_markdown(summaries)
    DATA_FRESHNESS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_FRESHNESS_REPORT_PATH.write_text(markdown, encoding="utf-8")
    print(f"\nWrote freshness report: {DATA_FRESHNESS_REPORT_PATH}")

    failures = [s for s in statuses if s.startswith("FAILED")]
    if failures:
        print(
            "\nWARNING: some refreshes failed; cached real data was kept "
            "(no demo fallback). Re-run with --force when the source is reachable."
        )
    return 0


def _refresh_stats(season: str) -> object:
    return fetch_nba_data(latest_season=season)


def _step(label: str, action) -> str:
    try:
        action()
        print(f"  [ok]     {label}")
        return f"OK {label}"
    except Exception as exc:  # noqa: BLE001 - degrade to cached data, never fake
        print(f"  [FAILED] {label}: {type(exc).__name__}: {str(exc)[:160]}")
        print(f"           keeping cached real data for {label}.")
        return f"FAILED {label}"


def _clear_season_cache(season: str) -> None:
    """Delete cached raw JSON for a season so --force re-downloads it."""
    cache = JsonFileCache(NBA_API_RAW_DIR)
    base = Path(cache.base_dir)
    season_slug = season.replace("-", "_")
    removed = 0
    for path in base.rglob(f"*{season_slug}*.json"):
        path.unlink()
        removed += 1
    # playerindex / tracking cache files are keyed on season too.
    for path in base.rglob("*.json"):
        if season in path.read_text(encoding="utf-8")[:400]:
            path.unlink()
            removed += 1
    print(f"  cleared {removed} cached raw files for {season}\n")


if __name__ == "__main__":
    raise SystemExit(main())
