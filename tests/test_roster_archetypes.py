"""Tests for roster archetype clustering."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.features.roster_archetypes import (
    build_roster_archetypes,
    create_roster_archetypes,
    select_cluster_features,
    suggest_cluster_name,
)


def test_select_cluster_features_uses_available_aliases() -> None:
    features = select_cluster_features(
        pd.DataFrame(
            {
                "NET_RTG": [5.0, -2.0],
                "fg3a_rate": [0.42, 0.30],
                "ast_pct": [0.64, 0.55],
                "unused_text": ["a", "b"],
            }
        )
    )

    assert features.columns.tolist() == [
        "net_rating",
        "three_point_attempt_rate",
        "assist_rate",
    ]
    assert features["net_rating"].tolist() == [5.0, -2.0]


def test_create_roster_archetypes_returns_assignments_and_summary() -> None:
    assignments, summary = create_roster_archetypes(
        _toy_fingerprints(),
        k=3,
        pca_components=2,
        random_state=7,
    )

    assert len(assignments) == 12
    assert assignments["cluster_id"].nunique() == 3
    assert {
        "season",
        "team_abbr",
        "cluster_id",
        "cluster_name",
        "cluster_distance",
        "pca_1",
        "pca_2",
        "net_rating_zscore",
    }.issubset(assignments.columns)
    assert summary["cluster_id"].nunique() == 3
    assert {
        "cluster_id",
        "cluster_name",
        "team_season_count",
        "strongest_positive_features",
        "strongest_negative_features",
        "feature_profile",
    }.issubset(summary.columns)
    assert set(summary["team_season_count"]) == {4}


def test_suggest_cluster_name_uses_feature_zscores() -> None:
    assert (
        suggest_cluster_name(
            pd.Series(
                {
                    "three_point_attempt_rate_zscore": 1.2,
                    "three_point_percentage_zscore": 0.8,
                }
            )
        )
        == "Shooting Pressure Team"
    )
    assert (
        suggest_cluster_name(
            pd.Series(
                {
                    "defensive_rating_zscore": -1.1,
                    "defensive_rebounding_percentage_zscore": 0.6,
                }
            )
        )
        == "Defense First Team"
    )
    assert (
        suggest_cluster_name(pd.Series({"top_usage_concentration_zscore": 1.0}))
        == "Heliocentric Creation Team"
    )


def test_create_roster_archetypes_validates_k() -> None:
    with pytest.raises(ValueError, match="k cannot exceed"):
        create_roster_archetypes(
            _toy_fingerprints().head(3),
            k=4,
            pca_components=2,
        )


def test_build_roster_archetypes_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "team_fingerprints.parquet"
    output_path = tmp_path / "team_roster_archetypes.parquet"
    summary_path = tmp_path / "roster_archetype_summary.csv"
    _toy_fingerprints().to_parquet(input_path, index=False)

    result = build_roster_archetypes(
        input_path=input_path,
        output_path=output_path,
        summary_path=summary_path,
        k=3,
        pca_components=2,
        random_state=7,
    )

    assert result.rows == 12
    assert result.clusters == 3
    assert "net_rating" in result.feature_columns
    assert result.output_path == output_path
    assert result.summary_path == summary_path
    saved = pd.read_parquet(output_path)
    summary = pd.read_csv(summary_path)
    assert saved["cluster_id"].nunique() == 3
    assert summary["cluster_id"].nunique() == 3


def _toy_fingerprints() -> pd.DataFrame:
    rows = []
    archetypes = [
        {
            "prefix": "SP",
            "net_rating": 4.0,
            "pace": 100.0,
            "three_point_attempt_rate": 0.48,
            "three_point_percentage": 0.39,
            "assist_rate": 0.66,
            "turnover_rate": 0.12,
            "offensive_rebounding_percentage": 0.23,
            "defensive_rebounding_percentage": 0.72,
            "defensive_rating": 113.0,
            "free_throw_rate": 0.19,
            "top_usage_concentration": 0.29,
        },
        {
            "prefix": "DF",
            "net_rating": 2.0,
            "pace": 95.0,
            "three_point_attempt_rate": 0.33,
            "three_point_percentage": 0.34,
            "assist_rate": 0.58,
            "turnover_rate": 0.14,
            "offensive_rebounding_percentage": 0.29,
            "defensive_rebounding_percentage": 0.78,
            "defensive_rating": 104.0,
            "free_throw_rate": 0.21,
            "top_usage_concentration": 0.31,
        },
        {
            "prefix": "HC",
            "net_rating": 1.0,
            "pace": 97.0,
            "three_point_attempt_rate": 0.39,
            "three_point_percentage": 0.36,
            "assist_rate": 0.50,
            "turnover_rate": 0.13,
            "offensive_rebounding_percentage": 0.24,
            "defensive_rebounding_percentage": 0.71,
            "defensive_rating": 111.0,
            "free_throw_rate": 0.27,
            "top_usage_concentration": 0.55,
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
                        "team_abbr": f"{archetype['prefix']}{index}",
                        "team_id": len(rows),
                        "team_name": f"{archetype['prefix']} Team {index}",
                        "playoff_tier": 3,
                        "quality_tier": 4,
                        "deep_playoff": True,
                    }
                )
                rows.append(row)
    return pd.DataFrame(rows)
