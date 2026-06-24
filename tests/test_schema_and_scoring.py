"""Tests for required schema fields, the scoring formula, and missing-data flags."""

from __future__ import annotations

import importlib

from moreymachine.data.fetch_nba import PLAYER_OUTPUT_COLUMNS, TEAM_OUTPUT_COLUMNS
from moreymachine.models.fit_model import (
    OUTPUT_COLUMNS,
    _candidate_missing_data_flags,
    calculate_gm_fit_score,
)

# The exact fields the spec requires on the processed tables.
REQUIRED_TEAM_FIELDS = {
    "season",
    "team_id",
    "team_abbr",
    "wins",
    "losses",
    "off_rating",
    "def_rating",
    "net_rating",
    "pace",
    "efg_pct",
    "tov_pct",
    "oreb_pct",
    "dreb_pct",
    "fta_rate",
    "three_pa_rate",
    "three_p_pct",
    "source",
    "pulled_at",
}
REQUIRED_PLAYER_FIELDS = {
    "season",
    "player_id",
    "player_name",
    "team_abbr",
    "minutes",
    "games",
    "pts",
    "reb",
    "ast",
    "usage_rate",
    "true_shooting",
    "three_p_pct",
    "assist_pct",
    "turnover_pct",
    "rebound_pct",
    "source",
    "pulled_at",
}


def test_team_schema_has_required_fields() -> None:
    assert REQUIRED_TEAM_FIELDS.issubset(set(TEAM_OUTPUT_COLUMNS))


def test_player_schema_has_required_fields() -> None:
    assert REQUIRED_PLAYER_FIELDS.issubset(set(PLAYER_OUTPUT_COLUMNS))


def test_candidate_output_includes_provenance_columns() -> None:
    assert {"data_sources", "missing_data_flags"}.issubset(set(OUTPUT_COLUMNS))


def test_gm_fit_score_matches_formula() -> None:
    # 0.35*g + 0.25*n + 0.20*p + 0.20*c - 0.20*r
    score = calculate_gm_fit_score(
        contender_similarity_gain_normalized=80,
        need_match=80,
        playoff_portability=80,
        contract_value=80,
        risk_score=0,
    )
    assert score == 80.0

    penalized = calculate_gm_fit_score(
        contender_similarity_gain_normalized=80,
        need_match=80,
        playoff_portability=80,
        contract_value=80,
        risk_score=50,
    )
    assert penalized == 70.0


def test_gm_fit_score_is_clipped_to_unit_range() -> None:
    assert (
        calculate_gm_fit_score(
            contender_similarity_gain_normalized=200,
            need_match=200,
            playoff_portability=200,
            contract_value=200,
            risk_score=0,
        )
        == 100.0
    )
    assert (
        calculate_gm_fit_score(
            contender_similarity_gain_normalized=0,
            need_match=0,
            playoff_portability=0,
            contract_value=0,
            risk_score=100,
        )
        == 0.0
    )


def test_missing_data_flags_report_missing_salary_and_position() -> None:
    candidate = {"player_name": "No Salary", "minutes": 1500}
    flags = _candidate_missing_data_flags(candidate)
    assert "salary missing" in flags
    assert "position not provided" in flags


def test_missing_data_flags_none_when_complete() -> None:
    candidate = {
        "player_name": "Complete",
        "minutes": 2000,
        "expected_salary": 12_000_000,
        "usage_rate": 0.2,
        "three_p_pct": 0.38,
        "position": "G",
    }
    assert _candidate_missing_data_flags(candidate) == "none"


def test_app_package_imports() -> None:
    module = importlib.import_module("moreymachine.app.streamlit_app")
    assert hasattr(module, "main")
    assert callable(module.main)
