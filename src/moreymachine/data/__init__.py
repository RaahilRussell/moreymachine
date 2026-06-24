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
from moreymachine.data.playoff_tiers import (
    PLAYOFF_TIER_DEFINITIONS,
    PlayoffTierBuildResult,
    build_team_seasons_with_tiers,
    join_playoff_tiers,
    load_playoff_tiers,
    validate_all_teams_have_tiers,
    validate_playoff_tiers,
)

__all__ = [
    "FetchResult",
    "JsonFileCache",
    "PLAYOFF_TIER_DEFINITIONS",
    "PlayoffTierBuildResult",
    "build_team_seasons_with_tiers",
    "fetch_nba_basic_data",
    "fetch_player_season_stats",
    "fetch_team_season_stats",
    "infer_latest_season",
    "join_playoff_tiers",
    "load_playoff_tiers",
    "season_range",
    "validate_all_teams_have_tiers",
    "validate_playoff_tiers",
]
