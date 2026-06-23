"""Offline tests for the NBA data fetching layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.fetch_nba import (
    BASE_STAT_COLUMNS,
    PLAYER_DATASET_NAME,
    TEAM_DATASET_NAME,
    fetch_nba_basic_data,
    fetch_team_season_stats,
    season_range,
)


class FakeTeamEndpoint:
    """Fake nba_api team endpoint that records live calls."""

    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.params = kwargs
        self.__class__.calls.append(kwargs)

    def get_normalized_dict(self) -> dict[str, object]:
        return {TEAM_DATASET_NAME: [_team_row()]}


class FakePlayerEndpoint:
    """Fake nba_api player endpoint that records live calls."""

    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.params = kwargs
        self.__class__.calls.append(kwargs)

    def get_normalized_dict(self) -> dict[str, object]:
        return {PLAYER_DATASET_NAME: [_player_row()]}


class FlakyTeamEndpoint(FakeTeamEndpoint):
    """Fake endpoint that fails once before returning toy data."""

    calls: list[dict[str, object]] = []

    def get_normalized_dict(self) -> dict[str, object]:
        if len(self.__class__.calls) == 1:
            raise RuntimeError("temporary NBA API failure")
        return {TEAM_DATASET_NAME: [_team_row(team_id=2, team_name="Boston Celtics")]}


class MissingSchemaTeamEndpoint(FakeTeamEndpoint):
    """Fake endpoint with an invalid dataset schema."""

    calls: list[dict[str, object]] = []

    def get_normalized_dict(self) -> dict[str, object]:
        return {TEAM_DATASET_NAME: [{"TEAM_ID": 1}]}


def test_season_range_is_inclusive() -> None:
    assert season_range("2015-16", "2017-18") == (
        "2015-16",
        "2016-17",
        "2017-18",
    )


def test_fetch_team_stats_uses_cache_on_repeated_runs(tmp_path: Path) -> None:
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

    assert len(FakeTeamEndpoint.calls) == 1
    pd.testing.assert_frame_equal(first, second)
    assert first.loc[0, "season"] == "2015-16"
    assert first.loc[0, "team_name"] == "Philadelphia 76ers"
    assert list((tmp_path / "raw" / "nba_api").rglob("*.json"))


def test_fetch_nba_basic_data_writes_processed_parquet(tmp_path: Path) -> None:
    FakeTeamEndpoint.calls = []
    FakePlayerEndpoint.calls = []

    result = fetch_nba_basic_data(
        start_season="2015-16",
        latest_season="2016-17",
        cache_dir=tmp_path / "raw" / "nba_api",
        processed_dir=tmp_path / "processed",
        team_endpoint_cls=FakeTeamEndpoint,
        player_endpoint_cls=FakePlayerEndpoint,
        request_sleep_seconds=0,
        retry_sleep_seconds=0,
    )

    assert result.seasons == ("2015-16", "2016-17")
    assert result.team_rows == 2
    assert result.player_rows == 2
    assert result.team_path.name == "team_seasons_basic.parquet"
    assert result.player_path.name == "player_seasons_basic.parquet"

    team_frame = pd.read_parquet(result.team_path)
    player_frame = pd.read_parquet(result.player_path)
    assert {"season", "team_id", "team_name", "pts"}.issubset(team_frame.columns)
    assert {
        "season",
        "player_id",
        "player_name",
        "team_abbreviation",
        "pts",
    }.issubset(player_frame.columns)
    assert len(FakeTeamEndpoint.calls) == 2
    assert len(FakePlayerEndpoint.calls) == 2


def test_fetch_team_stats_retries_temporary_failures(tmp_path: Path) -> None:
    FlakyTeamEndpoint.calls = []

    frame = fetch_team_season_stats(
        seasons=("2015-16",),
        cache=JsonFileCache(tmp_path / "raw" / "nba_api"),
        endpoint_cls=FlakyTeamEndpoint,
        max_retries=2,
        request_sleep_seconds=0,
        retry_sleep_seconds=0,
    )

    assert len(FlakyTeamEndpoint.calls) == 2
    assert frame.loc[0, "team_name"] == "Boston Celtics"


def test_fetch_team_stats_validates_raw_schema(tmp_path: Path) -> None:
    MissingSchemaTeamEndpoint.calls = []

    with pytest.raises(ValueError, match="missing required columns"):
        fetch_team_season_stats(
            seasons=("2015-16",),
            cache=JsonFileCache(tmp_path / "raw" / "nba_api"),
            endpoint_cls=MissingSchemaTeamEndpoint,
            request_sleep_seconds=0,
            retry_sleep_seconds=0,
        )


def _team_row(
    *,
    team_id: int = 1610612755,
    team_name: str = "Philadelphia 76ers",
) -> dict[str, object]:
    row = _base_stats()
    row.update({"TEAM_ID": team_id, "TEAM_NAME": team_name})
    return row


def _player_row() -> dict[str, object]:
    row = _base_stats()
    row.update(
        {
            "PLAYER_ID": 203954,
            "PLAYER_NAME": "Joel Embiid",
            "TEAM_ID": 1610612755,
            "TEAM_ABBREVIATION": "PHI",
            "AGE": 31,
        }
    )
    return row


def _base_stats() -> dict[str, object]:
    values: dict[str, object] = {column: 1 for column in BASE_STAT_COLUMNS}
    values.update(
        {
            "W_PCT": 0.5,
            "MIN": 240,
            "FG_PCT": 0.45,
            "FG3_PCT": 0.35,
            "FT_PCT": 0.8,
            "PTS": 100,
            "PLUS_MINUS": 5,
        }
    )
    return values
