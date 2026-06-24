"""Tests for team-season fingerprint feature creation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from moreymachine.features.team_fingerprints import (
    FINGERPRINT_FEATURE_COLUMNS,
    LABEL_COLUMNS,
    build_team_fingerprints,
    create_team_fingerprints,
)


def test_create_team_fingerprints_includes_features_and_labels() -> None:
    fingerprints = create_team_fingerprints(_full_team_season_data())

    for column in (*FINGERPRINT_FEATURE_COLUMNS, *LABEL_COLUMNS):
        assert column in fingerprints.columns
    assert fingerprints.loc[0, "offensive_rating"] == 120.0
    assert fingerprints.loc[0, "defensive_rating"] == 110.0
    assert fingerprints.loc[0, "net_rating"] == 10.0
    assert fingerprints.loc[0, "deep_playoff"]
    assert fingerprints.loc[0, "finals_team"]
    assert fingerprints.loc[0, "champion"]
    assert not fingerprints.loc[1, "deep_playoff"]
    assert not fingerprints.loc[1, "finals_team"]
    assert not fingerprints.loc[1, "champion"]


def test_create_team_fingerprints_derives_rate_features() -> None:
    frame = pd.DataFrame(
        {
            "season": ["2015-16"],
            "team_abbr": ["PHI"],
            "pts": [110],
            "fgm": [40],
            "fg3m": [10],
            "fga": [100],
            "fg3a": [35],
            "fta": [25],
            "oreb": [10],
            "tov": [12],
            "playoff_tier": [0],
            "quality_tier": [1],
        }
    )

    fingerprints = create_team_fingerprints(frame)
    expected_possessions = 100 + (0.44 * 25) - 10 + 12

    assert fingerprints.loc[0, "offensive_rating"] == 110 / expected_possessions * 100
    assert fingerprints.loc[0, "efg_percentage"] == 0.45
    assert fingerprints.loc[0, "turnover_percentage"] == 12 / (100 + 0.44 * 25 + 12)
    assert fingerprints.loc[0, "free_throw_rate"] == 0.25
    assert fingerprints.loc[0, "three_point_attempt_rate"] == 0.35


def test_create_team_fingerprints_handles_missing_columns_gracefully() -> None:
    fingerprints = create_team_fingerprints(
        pd.DataFrame({"season": ["2015-16"], "team_abbr": ["PHI"]})
    )

    assert set(FINGERPRINT_FEATURE_COLUMNS).issubset(fingerprints.columns)
    assert set(LABEL_COLUMNS).issubset(fingerprints.columns)
    assert fingerprints.loc[0, "net_rating"] is pd.NA
    assert fingerprints.loc[0, "estimated_shooting_pressure"] is pd.NA
    assert fingerprints.loc[0, "deep_playoff"] is pd.NA


def test_estimated_features_are_season_relative() -> None:
    fingerprints = create_team_fingerprints(_full_team_season_data())

    stronger = fingerprints[fingerprints["team_abbr"] == "A"].iloc[0]
    weaker = fingerprints[fingerprints["team_abbr"] == "B"].iloc[0]

    assert (
        stronger["estimated_shooting_pressure"] > weaker["estimated_shooting_pressure"]
    )
    assert (
        stronger["estimated_possession_control"]
        > weaker["estimated_possession_control"]
    )
    assert stronger["estimated_two_way_balance"] > weaker["estimated_two_way_balance"]


def test_build_team_fingerprints_writes_parquet(tmp_path: Path) -> None:
    input_path = tmp_path / "team_seasons_with_tiers.parquet"
    output_path = tmp_path / "team_fingerprints.parquet"
    _full_team_season_data().to_parquet(input_path, index=False)

    result = build_team_fingerprints(input_path=input_path, output_path=output_path)

    assert result.rows == 2
    assert result.seasons == ("2015-16",)
    assert result.output_path == output_path
    saved = pd.read_parquet(output_path)
    assert set(FINGERPRINT_FEATURE_COLUMNS).issubset(saved.columns)
    assert set(LABEL_COLUMNS).issubset(saved.columns)


def _full_team_season_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["2015-16", "2015-16"],
            "team_abbr": ["A", "B"],
            "team_id": [1, 2],
            "team_name": ["Team A", "Team B"],
            "off_rating": [120.0, 100.0],
            "def_rating": [110.0, 115.0],
            "net_rtg": [10.0, -15.0],
            "pace": [99.0, 94.0],
            "efg_pct": [0.56, 0.49],
            "tov_pct": [0.11, 0.15],
            "oreb_pct": [0.31, 0.23],
            "dreb_pct": [0.77, 0.70],
            "free_throw_rate": [0.25, 0.18],
            "fg3a_rate": [0.42, 0.31],
            "fg3_pct": [0.38, 0.33],
            "playoff_tier": [5, 1],
            "quality_tier": [5, 2],
        }
    )
