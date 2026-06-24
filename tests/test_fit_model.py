"""Tests for candidate fit scoring."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.models.fit_model import (
    REQUIRED_OUTPUT_COLUMNS,
    build_candidate_rankings,
    calculate_gm_fit_score,
    need_category_weights,
    rank_candidates,
)


def test_calculate_gm_fit_score_uses_requested_formula() -> None:
    score = calculate_gm_fit_score(
        contender_similarity_gain_normalized=70,
        need_match=80,
        playoff_portability=90,
        contract_value=60,
        risk_score=25,
    )

    assert score == pytest.approx(69.5)


def test_rank_candidates_outputs_required_columns_and_order() -> None:
    rankings = rank_candidates(
        _toy_players(),
        roster_gaps=_toy_roster_gaps(),
        player_archetypes=_toy_archetypes(),
        contracts=_toy_contracts(),
    )

    required = list(REQUIRED_OUTPUT_COLUMNS)
    assert rankings.columns.tolist()[: len(required)] == required
    assert {"data_sources", "missing_data_flags"}.issubset(rankings.columns)
    assert rankings.loc[0, "player_name"] == "Portable Spacer"
    assert rankings.loc[0, "fit_score"] > rankings.loc[1, "fit_score"]
    assert rankings.loc[0, "need_match"] > 70
    assert rankings.loc[0, "recommendation"] in {
        "Priority target",
        "Strong fit if affordable",
    }
    assert rankings.loc[1, "recommendation"] in {"Only if cheap", "Avoid"}
    assert "Need match" in rankings.loc[0, "why_fit"]
    assert rankings.loc[1, "concerns"]


def test_need_category_weights_use_positive_gap_severity() -> None:
    weights = need_category_weights(_toy_roster_gaps())

    assert weights["shooting_pressure"] > weights["rebounding"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_build_candidate_rankings_writes_output(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    gaps_path = tmp_path / "gaps.parquet"
    archetypes_path = tmp_path / "archetypes.parquet"
    contracts_path = tmp_path / "contracts.csv"
    output_path = tmp_path / "candidate_fit_rankings.parquet"
    _toy_players().to_parquet(players_path, index=False)
    _toy_roster_gaps().to_parquet(gaps_path, index=False)
    _toy_archetypes().to_parquet(archetypes_path, index=False)
    _toy_contracts().to_csv(contracts_path, index=False)

    result = build_candidate_rankings(
        player_stats_path=players_path,
        roster_gaps_path=gaps_path,
        player_archetypes_path=archetypes_path,
        contracts_path=contracts_path,
        contender_model_path=None,
        output_path=output_path,
    )

    assert result.rows == 2
    assert result.top_candidate == "Portable Spacer"
    saved = pd.read_parquet(output_path)
    assert saved.loc[0, "player_name"] == "Portable Spacer"


def _toy_roster_gaps() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "category_key": "shooting_pressure",
                "gap_size": 0.10,
                "severity_score": 80,
            },
            {
                "category_key": "role_player_shooting",
                "gap_size": 0.08,
                "severity_score": 70,
            },
            {"category_key": "defense", "gap_size": 2.5, "severity_score": 45},
            {"category_key": "rebounding", "gap_size": 0.01, "severity_score": 20},
            {
                "category_key": "turnover_control",
                "gap_size": -0.01,
                "severity_score": 60,
            },
        ]
    )


def _toy_players() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": "2025-26",
                "player_id": 1,
                "player_name": "Portable Spacer",
                "team_abbreviation": "BKN",
                "position": "SG",
                "age": 28,
                "minutes": 1900,
                "usage_rate": 0.15,
                "true_shooting_percentage": 0.61,
                "three_point_attempt_rate": 0.52,
                "three_point_percentage": 0.39,
                "turnover_rate": 0.08,
                "assist_rate": 0.13,
                "rebound_rate": 0.08,
                "steal_rate": 0.017,
                "block_rate": 0.004,
                "defensive_box_plus_minus": 0.3,
            },
            {
                "season": "2025-26",
                "player_id": 2,
                "player_name": "Tough Shot Scorer",
                "team_abbreviation": "WAS",
                "position": "PG",
                "age": 29,
                "minutes": 1700,
                "usage_rate": 0.33,
                "true_shooting_percentage": 0.50,
                "three_point_attempt_rate": 0.27,
                "three_point_percentage": 0.31,
                "turnover_rate": 0.18,
                "assist_rate": 0.09,
                "rebound_rate": 0.04,
                "steal_rate": 0.006,
                "block_rate": 0.001,
                "defensive_box_plus_minus": -1.4,
            },
        ]
    )


def _toy_archetypes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": "2025-26",
                "player_id": 1,
                "archetype_name": "Low-Usage Spacer",
            },
            {
                "season": "2025-26",
                "player_id": 2,
                "archetype_name": "Scoring Guard",
            },
        ]
    )


def _toy_contracts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player_id": 1, "estimated_salary_millions": 14},
            {"player_id": 2, "estimated_salary_millions": 28},
        ]
    )
