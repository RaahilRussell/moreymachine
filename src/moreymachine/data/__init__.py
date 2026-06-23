"""Data access and ingestion utilities for MoreyMachine."""

from __future__ import annotations

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.fetch_nba import (
    FetchResult,
    fetch_nba_basic_data,
    fetch_player_season_stats,
    fetch_team_season_stats,
    infer_latest_season,
    season_range,
)

__all__ = [
    "FetchResult",
    "JsonFileCache",
    "fetch_nba_basic_data",
    "fetch_player_season_stats",
    "fetch_team_season_stats",
    "infer_latest_season",
    "season_range",
]
