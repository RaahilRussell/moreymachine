"""Orchestration for the refreshable real-data pipeline.

This is the one place expensive live fetches happen. The Streamlit app never
imports it on a page load - it only reads the cached Parquet files this module
writes. Each step degrades to the previously cached real file on failure (never
to demo data), stamps ``pulled_at`` / ``data_mode`` so provenance is always
present, and the run ends by writing the freshness report.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.fetch_bio_tracking import (
    fetch_player_bio,
    fetch_player_tracking,
)
from moreymachine.data.contracts_loader import build_rich_contracts
from moreymachine.data.fetch_nba import fetch_nba_data, infer_latest_season
from moreymachine.data.freshness import render_freshness_markdown, summarize_freshness
from moreymachine.utils.paths import (
    DATA_FRESHNESS_REPORT_PATH,
    NBA_API_RAW_DIR,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    TEAM_SEASONS_PATH,
)

# Each refreshable table and the data_mode it should carry once written.
RAW_DATA_MODES: dict[Path, str] = {
    TEAM_SEASONS_PATH: "real_api",
    PLAYER_SEASONS_PATH: "real_api",
    PLAYER_BIO_PATH: "real_api",
    PLAYER_TRACKING_PATH: "real_api",
}


@dataclass
class RefreshResult:
    """Outcome of a refresh run."""

    season: str
    statuses: dict[str, str] = field(default_factory=dict)
    freshness_report: Path = DATA_FRESHNESS_REPORT_PATH

    @property
    def failures(self) -> list[str]:
        return [name for name, status in self.statuses.items() if status != "ok"]


def refresh_current_data(
    *,
    season: str = "latest",
    force: bool = False,
    log: Callable[[str], None] = print,
) -> RefreshResult:
    """Refresh every real source for ``season`` and write the freshness report."""
    resolved = infer_latest_season() if season == "latest" else season
    log(f"Refreshing real data for season {resolved} (force={force})\n")

    if force:
        _clear_season_cache(resolved, log=log)

    result = RefreshResult(season=resolved)
    result.statuses["team_player_stats"] = _step(
        "team/player season stats", lambda: fetch_nba_data(latest_season=resolved), log
    )
    result.statuses["player_bio"] = _step(
        "player bio", lambda: fetch_player_bio(season=resolved), log
    )
    result.statuses["player_tracking"] = _step(
        "player tracking", lambda: fetch_player_tracking(season=resolved), log
    )
    result.statuses["contracts"] = _step(
        "contracts", lambda: build_rich_contracts(refresh=True), log
    )

    _stamp_data_modes(log=log)

    summaries = summarize_freshness()
    DATA_FRESHNESS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_FRESHNESS_REPORT_PATH.write_text(
        render_freshness_markdown(summaries), encoding="utf-8"
    )
    log(f"\nWrote freshness report: {DATA_FRESHNESS_REPORT_PATH}")

    if result.failures:
        log(
            "\nWARNING: some refreshes failed; cached real data was kept "
            "(no demo fallback). Re-run with --force when the source is reachable."
        )
    return result


def _stamp_data_modes(*, log: Callable[[str], None]) -> None:
    """Ensure every raw table carries a real-mode ``data_mode`` column."""
    for path, mode in RAW_DATA_MODES.items():
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if "data_mode" in frame.columns and frame["data_mode"].notna().all():
            continue
        frame["data_mode"] = mode
        frame.to_parquet(path, index=False)
        log(f"  [stamp]  data_mode={mode} -> {path.name}")


def _step(label: str, action: Callable[[], object], log: Callable[[str], None]) -> str:
    try:
        action()
        log(f"  [ok]     {label}")
        return "ok"
    except Exception as exc:  # noqa: BLE001 - degrade to cached data, never fake
        log(f"  [FAILED] {label}: {type(exc).__name__}: {str(exc)[:160]}")
        log(f"           keeping cached real data for {label}.")
        return f"failed: {type(exc).__name__}"


def _clear_season_cache(season: str, *, log: Callable[[str], None]) -> None:
    """Delete cached raw JSON for a season so --force re-downloads it."""
    cache = JsonFileCache(NBA_API_RAW_DIR)
    base = Path(cache.base_dir)
    season_slug = season.replace("-", "_")
    removed = 0
    for path in base.rglob(f"*{season_slug}*.json"):
        path.unlink()
        removed += 1
    for path in base.rglob("*.json"):
        if season in path.read_text(encoding="utf-8")[:400]:
            path.unlink()
            removed += 1
    log(f"  cleared {removed} cached raw files for {season}\n")
