"""Tests for manual playoff tier validation and joins."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.data.playoff_tiers import (
    build_team_seasons_with_tiers,
    join_playoff_tiers,
    load_playoff_tiers,
    validate_all_teams_have_tiers,
    validate_playoff_tiers,
)


def test_load_playoff_tiers_normalizes_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "tiers.csv"
    csv_path.write_text(
        "season,team_abbr,playoff_tier,playoff_result\n" "2015-16, phi ,5,Champion\n",
        encoding="utf-8",
    )

    tiers = load_playoff_tiers(csv_path)

    assert tiers.loc[0, "season"] == "2015-16"
    assert tiers.loc[0, "team_abbr"] == "PHI"
    assert tiers.loc[0, "playoff_tier"] == 5
    assert tiers.loc[0, "playoff_result"] == "Champion"


def test_validate_playoff_tiers_rejects_invalid_tier() -> None:
    tiers = pd.DataFrame(
        {
            "season": ["2015-16"],
            "team_abbr": ["PHI"],
            "playoff_tier": [6],
            "playoff_result": ["invalid"],
        }
    )

    with pytest.raises(ValueError, match="Invalid playoff_tier"):
        validate_playoff_tiers(tiers)


def test_validate_all_teams_have_tiers_reports_missing_team() -> None:
    team_seasons = _team_seasons()
    tiers = pd.DataFrame(
        {
            "season": ["2015-16"],
            "team_abbr": ["PHI"],
            "playoff_tier": [0],
            "playoff_result": ["missed playoffs"],
        }
    )

    with pytest.raises(ValueError, match="Missing playoff tiers.*2015-16/BOS"):
        validate_all_teams_have_tiers(team_seasons, tiers)


def test_validate_all_teams_have_tiers_reports_unexpected_team() -> None:
    team_seasons = _team_seasons().iloc[[0]]
    tiers = pd.DataFrame(
        {
            "season": ["2015-16", "2015-16"],
            "team_abbr": ["PHI", "BOS"],
            "playoff_tier": [0, 1],
            "playoff_result": ["missed playoffs", "lost first round"],
        }
    )

    with pytest.raises(ValueError, match="Unexpected playoff tier rows: 2015-16/BOS"):
        validate_all_teams_have_tiers(team_seasons, tiers)


def test_join_playoff_tiers_adds_tier_columns() -> None:
    result = join_playoff_tiers(_team_seasons(), _complete_tiers())

    assert result["team_abbr"].tolist() == ["PHI", "BOS"]
    assert result["playoff_tier"].tolist() == [0, 1]
    assert result["playoff_result"].tolist() == ["missed playoffs", "lost first round"]


def test_build_team_seasons_with_tiers_writes_parquet(tmp_path: Path) -> None:
    team_path = tmp_path / "team_seasons_basic.parquet"
    tier_path = tmp_path / "playoff_tiers.csv"
    output_path = tmp_path / "team_seasons_with_tiers.parquet"
    _team_seasons().to_parquet(team_path, index=False)
    _complete_tiers().to_csv(tier_path, index=False)

    result = build_team_seasons_with_tiers(
        team_seasons_path=team_path,
        playoff_tiers_path=tier_path,
        output_path=output_path,
    )

    assert result.rows == 2
    assert result.seasons == ("2015-16",)
    assert result.output_path == output_path
    saved = pd.read_parquet(output_path)
    assert {"team_abbr", "playoff_tier", "playoff_result"}.issubset(saved.columns)


def _team_seasons() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["2015-16", "2015-16"],
            "team_id": [1610612755, 1610612738],
            "team_name": ["Philadelphia 76ers", "Boston Celtics"],
            "wins": [10, 48],
        }
    )


def _complete_tiers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["2015-16", "2015-16"],
            "team_abbr": ["PHI", "BOS"],
            "playoff_tier": [0, 1],
            "playoff_result": ["missed playoffs", "lost first round"],
        }
    )
