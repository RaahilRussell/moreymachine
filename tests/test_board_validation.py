"""Tests for the expanded target board validation gates."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from moreymachine.features.candidate_universe import PHI_ROSTER_2025_26
from moreymachine.models.board_validation import (
    REQUIRED_EXPLANATION_COLUMNS,
    REQUIRED_SALARY_COLUMNS,
    validate_board_frames,
)
from moreymachine.utils.paths import DEMO_DATA_DIR
from moreymachine.utils.real_data import DemoDataInRealModeError, guard_against_demo


def _good_board(n: int = 30) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "player_name": [f"Player {i}" for i in range(n)],
            "candidate_type": "realistic_trade_target",
            "expected_role": "Rotation Player",
            "recommendation": ["Priority Target"] * 8
            + ["Role-Player Target"] * (n - 8),
            "contract_value": [50 + i * 0.5 for i in range(n)],
            "portability": [40 + i for i in range(n)],
            "risk_score": [10 + i for i in range(n)],
            "risk_tier": "Low",
            "data_sources": "Stats: nba_api",
        }
    )
    for column in REQUIRED_EXPLANATION_COLUMNS:
        frame[column] = "filled explanation text"
    for column in REQUIRED_SALARY_COLUMNS:
        frame[column] = 5.0
    frame["salary_bucket"] = "Cheap"
    frame["missing_data_flags"] = "none"
    frame["why_fit"] = "Answers gaps."
    frame["role_on_sixers"] = "Projected Rotation minutes."
    frame["risk_summary"] = "Low risk."
    return frame


def test_clean_boards_pass_all_gates() -> None:
    board = _good_board()
    report = validate_board_frames(board, board, pd.DataFrame(), csv_path=None)
    assert report.passed, report.to_markdown()


def test_too_many_priority_targets_fails() -> None:
    board = _good_board()
    board["recommendation"] = "Priority Target"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "priority_cap" for g in report.failures)


def test_saturated_contract_value_fails() -> None:
    board = _good_board()
    board["contract_value"] = 100.0
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "contract_value_saturation" for g in report.failures)


def test_saturated_portability_fails() -> None:
    board = _good_board()
    board["portability"] = 99.0
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "portability_saturation" for g in report.failures)


def test_current_sixer_on_board_fails() -> None:
    board = _good_board()
    board.loc[0, "player_name"] = next(iter(PHI_ROSTER_2025_26))
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_current_sixers" for g in report.failures)


def test_no_demo_data_in_real_mode() -> None:
    with pytest.raises(DemoDataInRealModeError):
        guard_against_demo(DEMO_DATA_DIR / "candidate_fit_rankings.parquet")


def test_star_on_realistic_board_fails() -> None:
    board = _good_board()
    board.loc[0, "candidate_type"] = "star_unrealistic"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_star_in_realistic" for g in report.failures)


def test_unrealistic_player_cannot_be_priority_target() -> None:
    board = _good_board()
    board.loc[0, "candidate_type"] = "star_unrealistic"
    board.loc[0, "recommendation"] = "Priority Target"
    report = validate_board_frames(board, pd.DataFrame(), pd.DataFrame())
    assert any(g.name == "no_unrealistic_priority" for g in report.failures)


def test_missing_contract_priority_fails() -> None:
    board = _good_board()
    board.loc[0, "candidate_type"] = "missing_contract_status"
    board.loc[0, "recommendation"] = "Priority Target"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_missing_contract_priority" for g in report.failures)


def test_unknown_role_priority_fails() -> None:
    board = _good_board()
    board.loc[0, "expected_role"] = "Unknown"
    board.loc[0, "recommendation"] = "Priority Target"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_unknown_role_priority" for g in report.failures)


def test_severe_risk_priority_fails() -> None:
    board = _good_board()
    board.loc[0, "risk_tier"] = "Severe"
    board.loc[0, "recommendation"] = "Priority Target"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_severe_risk_priority" for g in report.failures)


def test_ambiguous_salary_fails() -> None:
    board = _good_board().drop(columns=["base_salary_millions"])
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "salary_unambiguous" for g in report.failures)


def test_missing_cap_hit_must_be_flagged() -> None:
    board = _good_board()
    board.loc[0, "cap_hit_millions"] = pd.NA
    board.loc[0, "missing_data_flags"] = "none"
    board.loc[0, "salary_context"] = "$0.0M cap hit"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "salary_unambiguous" for g in report.failures)


def test_identical_risk_fails_diversity_gate() -> None:
    board = _good_board()
    board["risk_score"] = 15.0
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "risk_diversity" for g in report.failures)


def test_missing_candidate_type_fails() -> None:
    board = _good_board().drop(columns=["candidate_type"])
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "candidate_type_present" for g in report.failures)


def test_missing_provenance_fails() -> None:
    board = _good_board()
    board.loc[0, "data_sources"] = ""
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "recommendation_provenance" for g in report.failures)


def test_missing_explanation_columns_fails() -> None:
    board = _good_board().drop(columns=["why_fit"])
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "explanation_present" for g in report.failures)


def test_realistic_board_excludes_watchlist_players() -> None:
    board = _good_board()
    realistic = _good_board()
    realistic.loc[0, "candidate_type"] = "manual_watchlist"
    report = validate_board_frames(board, realistic, pd.DataFrame())
    assert any(g.name == "no_star_in_realistic" for g in report.failures)


def test_csv_export_requires_explanation_columns(tmp_path: Path) -> None:
    board = _good_board()
    csv_path = tmp_path / "candidate_fit_rankings.csv"
    board.drop(columns=["why_fit"]).to_csv(csv_path, index=False)
    report = validate_board_frames(board, board, pd.DataFrame(), csv_path=csv_path)
    assert any(g.name == "csv_explanations" for g in report.failures)
