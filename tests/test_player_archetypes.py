"""Tests for player archetype clustering."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.features.player_archetypes import (
    build_player_archetypes,
    create_player_archetypes,
    filter_rotation_players,
    select_player_features,
    suggest_archetype_name,
)


def test_filter_rotation_players_uses_minutes_threshold() -> None:
    players = pd.DataFrame(
        {
            "player_name": ["Rotation", "Bench"],
            "min": [900, 120],
        }
    )

    result = filter_rotation_players(players, min_minutes=500)

    assert result["player_name"].tolist() == ["Rotation"]
    assert result["minutes"].tolist() == [900.0]


def test_select_player_features_derives_rates_and_position_features() -> None:
    features = select_player_features(
        pd.DataFrame(
            {
                "age": [25],
                "min": [1000],
                "pts": [600],
                "fga": [500],
                "fgm": [250],
                "fg3a": [200],
                "fg3m": [80],
                "fta": [100],
                "ast": [150],
                "tov": [75],
                "reb": [220],
                "stl": [45],
                "blk": [20],
                "position": ["SG"],
            }
        )
    )

    assert features.loc[0, "minutes"] == 1000.0
    assert features.loc[0, "shooting_efficiency"] == 600 / (2 * (500 + 0.44 * 100))
    assert features.loc[0, "three_point_attempt_rate"] == 0.4
    assert features.loc[0, "assist_rate"] == 0.15
    assert features.loc[0, "turnover_rate"] == 75 / (500 + 0.44 * 100 + 75)
    assert features.loc[0, "rebound_rate"] == 0.22
    assert features.loc[0, "steal_rate"] == 0.045
    assert features.loc[0, "block_rate"] == 0.02
    assert features.loc[0, "position_guard"] == 1.0


def test_create_player_archetypes_returns_assignments_and_summary() -> None:
    assignments, summary = create_player_archetypes(
        _toy_players(),
        min_minutes=500,
        k=3,
        pca_components=2,
        random_state=7,
    )

    assert len(assignments) == 12
    assert assignments["cluster_id"].nunique() == 3
    assert {
        "season",
        "player_name",
        "cluster_id",
        "archetype_name",
        "cluster_distance",
        "pca_1",
        "pca_2",
        "usage_rate_zscore",
    }.issubset(assignments.columns)
    assert summary["cluster_id"].nunique() == 3
    assert {
        "cluster_id",
        "archetype_name",
        "player_season_count",
        "strongest_positive_features",
        "strongest_negative_features",
        "feature_profile",
    }.issubset(summary.columns)
    assert set(summary["player_season_count"]) == {4}


def test_suggest_archetype_name_uses_feature_zscores() -> None:
    assert (
        suggest_archetype_name(
            pd.Series({"usage_rate_zscore": 1.0, "assist_rate_zscore": 0.6})
        )
        == "High-Usage Creator"
    )
    assert (
        suggest_archetype_name(
            pd.Series({"block_rate_zscore": 1.0, "rebound_rate_zscore": 0.7})
        )
        == "Rim Protector"
    )
    assert (
        suggest_archetype_name(
            pd.Series(
                {
                    "position_big_zscore": 0.8,
                    "three_point_attempt_rate_zscore": 0.7,
                }
            )
        )
        == "Stretch Big"
    )


def test_create_player_archetypes_validates_k() -> None:
    with pytest.raises(ValueError, match="k cannot exceed"):
        create_player_archetypes(
            _toy_players().head(3),
            min_minutes=500,
            k=4,
            pca_components=2,
        )


def test_build_player_archetypes_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "player_seasons_basic.parquet"
    output_path = tmp_path / "player_archetypes.parquet"
    summary_path = tmp_path / "player_archetype_summary.csv"
    _toy_players().to_parquet(input_path, index=False)

    result = build_player_archetypes(
        input_path=input_path,
        output_path=output_path,
        summary_path=summary_path,
        min_minutes=500,
        k=3,
        pca_components=2,
        random_state=7,
    )

    assert result.rows == 12
    assert result.clusters == 3
    assert "usage_rate" in result.feature_columns
    assert result.output_path == output_path
    assert result.summary_path == summary_path
    saved = pd.read_parquet(output_path)
    summary = pd.read_csv(summary_path)
    assert saved["cluster_id"].nunique() == 3
    assert summary["cluster_id"].nunique() == 3


def _toy_players() -> pd.DataFrame:
    rows = []
    archetypes = [
        {
            "prefix": "CRE",
            "position": "PG",
            "usage_rate": 0.31,
            "shooting_efficiency": 0.58,
            "three_point_attempt_rate": 0.39,
            "three_point_percentage": 0.36,
            "assist_rate": 0.34,
            "turnover_rate": 0.13,
            "rebound_rate": 0.08,
            "steal_rate": 0.020,
            "block_rate": 0.004,
        },
        {
            "prefix": "RIM",
            "position": "C",
            "usage_rate": 0.18,
            "shooting_efficiency": 0.63,
            "three_point_attempt_rate": 0.04,
            "three_point_percentage": 0.20,
            "assist_rate": 0.08,
            "turnover_rate": 0.12,
            "rebound_rate": 0.25,
            "steal_rate": 0.013,
            "block_rate": 0.060,
        },
        {
            "prefix": "SPC",
            "position": "SF",
            "usage_rate": 0.14,
            "shooting_efficiency": 0.60,
            "three_point_attempt_rate": 0.58,
            "three_point_percentage": 0.40,
            "assist_rate": 0.11,
            "turnover_rate": 0.08,
            "rebound_rate": 0.10,
            "steal_rate": 0.026,
            "block_rate": 0.010,
        },
    ]
    for season in ("2019-20", "2020-21"):
        for archetype in archetypes:
            for index in range(2):
                row = {
                    key: value for key, value in archetype.items() if key != "prefix"
                }
                row.update(
                    {
                        "season": season,
                        "player_id": len(rows),
                        "player_name": f"{archetype['prefix']} Player {index}",
                        "team_abbreviation": f"T{index}",
                        "minutes": 900 + index,
                        "age": 25 + index,
                    }
                )
                rows.append(row)
    return pd.DataFrame(rows)
