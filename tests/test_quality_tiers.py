"""Tests for regular-season quality tiers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.features.quality_tiers import add_quality_tiers, build_quality_tiers


def test_add_quality_tiers_uses_season_percentiles() -> None:
    result = add_quality_tiers(_toy_net_rating_data(team_count=30))

    first_season = result[result["season"] == "2015-16"].sort_values("net_rating")
    assert first_season["quality_tier"].tolist() == (
        [0] * 10 + [1] * 4 + [2] * 3 + [3] * 3 + [4] * 5 + [5] * 5
    )
    assert first_season["quality_rank"].tolist() == list(range(30, 0, -1))
    assert first_season["quality_metric_source"].unique().tolist() == ["net_rating"]
    assert first_season["quality_tier_reason"].str.contains("season percentile").all()


def test_quality_tiers_are_computed_within_each_season() -> None:
    data = pd.concat(
        [
            _toy_net_rating_data("2015-16", start=-5),
            _toy_net_rating_data("2016-17", start=95),
        ],
        ignore_index=True,
    )

    result = add_quality_tiers(data)

    for _, season_frame in result.groupby("season"):
        ranked = season_frame.sort_values("net_rating")["quality_tier"].tolist()
        assert ranked == [0, 0, 2, 3, 4, 5]


def test_add_quality_tiers_falls_back_to_plus_minus_per_game() -> None:
    frame = pd.DataFrame(
        {
            "season": ["2015-16", "2015-16", "2015-16"],
            "team_abbr": ["A", "B", "C"],
            "plus_minus": [-82, 0, 82],
            "gp": [82, 82, 82],
        }
    )

    result = add_quality_tiers(frame)

    assert result.sort_values("quality_metric")["quality_metric"].tolist() == [
        -1.0,
        0.0,
        1.0,
    ]
    assert result["quality_metric_source"].unique().tolist() == ["plus_minus_per_game"]


def test_add_quality_tiers_uses_rating_margin_when_net_rating_is_absent() -> None:
    frame = pd.DataFrame(
        {
            "season": ["2015-16", "2015-16", "2015-16"],
            "team_abbr": ["A", "B", "C"],
            "offensive_rating": [100, 110, 105],
            "defensive_rating": [105, 100, 105],
        }
    )

    result = add_quality_tiers(frame)

    assert result.sort_values("quality_metric")["quality_metric"].tolist() == [
        -5,
        0,
        10,
    ]
    assert result["quality_metric_source"].unique().tolist() == [
        "offensive_rating_minus_defensive_rating"
    ]


def test_add_quality_tiers_requires_strength_metric() -> None:
    frame = pd.DataFrame({"season": ["2015-16"], "team_abbr": ["PHI"]})

    with pytest.raises(ValueError, match="regular-season strength column"):
        add_quality_tiers(frame)


def test_build_quality_tiers_overwrites_output_parquet(tmp_path: Path) -> None:
    input_path = tmp_path / "team_seasons_with_tiers.parquet"
    output_path = tmp_path / "team_seasons_with_tiers.parquet"
    _toy_net_rating_data().to_parquet(input_path, index=False)

    result = build_quality_tiers(input_path=input_path, output_path=output_path)

    assert result.rows == 6
    assert result.seasons == ("2015-16",)
    assert result.output_path == output_path
    saved = pd.read_parquet(output_path)
    assert {
        "quality_tier",
        "quality_metric",
        "quality_metric_source",
        "quality_rank",
        "quality_percentile",
        "quality_tier_reason",
    }.issubset(saved.columns)


def _toy_net_rating_data(
    season: str = "2015-16",
    start: int = -5,
    team_count: int = 6,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [season] * team_count,
            "team_abbr": [f"T{value:02d}" for value in range(team_count)],
            "net_rating": [start + value for value in range(team_count)],
        }
    )
