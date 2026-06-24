"""Offline tests for the multi-measure NBA data fetching layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.fetch_nba import (
    PLAYER_DATASET_NAME,
    PLAYER_OUTPUT_COLUMNS,
    TEAM_DATASET_NAME,
    TEAM_MEASURE_TYPES,
    TEAM_OUTPUT_COLUMNS,
    fetch_nba_data,
    fetch_team_season_stats,
    season_range,
)

PHI_ID = 1610612755
BOS_ID = 1610612738


def _team_measure_row(measure: str, *, team_id: int, team_name: str) -> dict:
    """Return the columns a given team measure_type would expose."""
    base = {"TEAM_ID": team_id, "TEAM_NAME": team_name}
    if measure == "Base":
        base.update({"W": 50, "L": 32, "FGA": 7000, "FG3A": 2500, "FG3_PCT": 0.37})
    elif measure == "Advanced":
        base.update(
            {
                "OFF_RATING": 115.0,
                "DEF_RATING": 110.0,
                "NET_RATING": 5.0,
                "PACE": 99.0,
                "EFG_PCT": 0.54,
                "TM_TOV_PCT": 0.13,
                "OREB_PCT": 0.25,
                "DREB_PCT": 0.77,
            }
        )
    elif measure == "Four Factors":
        base.update({"FTA_RATE": 0.26})
    return base


def _player_measure_row(measure: str) -> dict:
    if measure == "Base":
        return {
            "PLAYER_ID": 203954,
            "PLAYER_NAME": "Joel Embiid",
            "TEAM_ABBREVIATION": "PHI",
            "AGE": 31,
            "GP": 60,
            "MIN": 2000,
            "PTS": 1500,
            "REB": 600,
            "AST": 250,
            "FGA": 1000,
            "FG3A": 100,
            "FG3_PCT": 0.35,
            "STL": 60,
            "BLK": 90,
            "TOV": 200,
        }
    return {
        "PLAYER_ID": 203954,
        "PLAYER_NAME": "Joel Embiid",
        "USG_PCT": 0.36,
        "TS_PCT": 0.63,
        "AST_PCT": 0.30,
        "TM_TOV_PCT": 0.12,
        "REB_PCT": 0.18,
    }


class FakeTeamEndpoint:
    """Fake team endpoint that returns per-measure-type data and records calls."""

    calls: list[dict] = []

    def __init__(self, **kwargs: object) -> None:
        self.params = kwargs
        self.__class__.calls.append(kwargs)

    def get_normalized_dict(self) -> dict:
        measure = str(self.params["measure_type_detailed_defense"])
        return {
            TEAM_DATASET_NAME: [
                _team_measure_row(
                    measure, team_id=PHI_ID, team_name="Philadelphia 76ers"
                )
            ]
        }


class FakePlayerEndpoint:
    calls: list[dict] = []

    def __init__(self, **kwargs: object) -> None:
        self.params = kwargs
        self.__class__.calls.append(kwargs)

    def get_normalized_dict(self) -> dict:
        measure = str(self.params["measure_type_detailed_defense"])
        return {PLAYER_DATASET_NAME: [_player_measure_row(measure)]}


def test_season_range_is_inclusive() -> None:
    assert season_range("2015-16", "2017-18") == ("2015-16", "2016-17", "2017-18")


def test_fetch_team_stats_builds_advanced_schema_and_caches(tmp_path: Path) -> None:
    FakeTeamEndpoint.calls = []
    cache = JsonFileCache(tmp_path / "raw" / "nba_api")

    first = fetch_team_season_stats(
        seasons=("2015-16",),
        cache=cache,
        endpoint_cls=FakeTeamEndpoint,
        request_sleep_seconds=0,
        retry_sleep_seconds=0,
    )
    second = fetch_team_season_stats(
        seasons=("2015-16",),
        cache=cache,
        endpoint_cls=FakeTeamEndpoint,
        request_sleep_seconds=0,
        retry_sleep_seconds=0,
    )

    # one call per measure type on the first run, fully cached on the second
    assert len(FakeTeamEndpoint.calls) == len(TEAM_MEASURE_TYPES)
    pd.testing.assert_frame_equal(first, second)
    assert set(TEAM_OUTPUT_COLUMNS).issubset(first.columns)
    assert first.loc[0, "team_abbr"] == "PHI"
    assert first.loc[0, "net_rating"] == 5.0
    assert first.loc[0, "source"].startswith("nba_api:leaguedashteamstats")
    assert first.loc[0, "pulled_at"]


def test_fetch_nba_data_writes_spec_named_parquet(tmp_path: Path) -> None:
    FakeTeamEndpoint.calls = []
    FakePlayerEndpoint.calls = []

    result = fetch_nba_data(
        start_season="2015-16",
        latest_season="2015-16",
        cache_dir=tmp_path / "raw" / "nba_api",
        processed_dir=tmp_path / "processed",
        team_endpoint_cls=FakeTeamEndpoint,
        player_endpoint_cls=FakePlayerEndpoint,
        request_sleep_seconds=0,
        retry_sleep_seconds=0,
    )

    assert result.team_path.name == "team_seasons.parquet"
    assert result.player_path.name == "player_seasons.parquet"

    team_frame = pd.read_parquet(result.team_path)
    player_frame = pd.read_parquet(result.player_path)
    assert set(TEAM_OUTPUT_COLUMNS).issubset(team_frame.columns)
    assert set(PLAYER_OUTPUT_COLUMNS).issubset(player_frame.columns)
    # provenance is always present
    assert (team_frame["source"] != "").all()
    assert (player_frame["pulled_at"] != "").all()
    assert player_frame.loc[0, "usage_rate"] == 0.36
