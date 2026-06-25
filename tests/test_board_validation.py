"""Tests for the target board validation gates."""

from __future__ import annotations

import pandas as pd

from moreymachine.features.candidate_universe import PHI_ROSTER_2025_26
from moreymachine.models.board_validation import (
    REQUIRED_EXPLANATION_COLUMNS,
    validate_board_frames,
)


def _good_board(n: int = 30) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "player_name": [f"Player {i}" for i in range(n)],
            "candidate_type": "realistic_trade_target",
            "recommendation": ["Priority target"] * 8
            + ["Role-player target"] * (n - 8),
            "contract_value": [50 + i for i in range(n)],
            "portability": [40 + i for i in range(n)],
            "risk_score": [10 + i for i in range(n)],
            "data_sources": "Stats: nba_api",
            "why_fit": "Answers gaps.",
            "role_on_sixers": "Projected Rotation minutes.",
        }
    )
    for column in REQUIRED_EXPLANATION_COLUMNS:
        if column not in frame.columns:
            frame[column] = "filled"
    return frame


def test_clean_boards_pass_all_gates() -> None:
    board = _good_board()
    report = validate_board_frames(board, board, pd.DataFrame())
    assert report.passed, report.to_markdown()


def test_too_many_priority_targets_fails() -> None:
    board = _good_board()
    board["recommendation"] = "Priority target"
    report = validate_board_frames(board, board, pd.DataFrame())
    assert not report.passed
    assert any(g.name == "priority_cap" for g in report.failures)


def test_saturated_contract_value_fails() -> None:
    board = _good_board()
    board["contract_value"] = 100.0
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "contract_value_saturation" for g in report.failures)


def test_current_sixer_on_board_fails() -> None:
    board = _good_board()
    board.loc[0, "player_name"] = next(iter(PHI_ROSTER_2025_26))
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "no_current_sixers" for g in report.failures)


def test_star_on_realistic_board_fails() -> None:
    realistic = _good_board()
    realistic.loc[0, "candidate_type"] = "star_unrealistic"
    report = validate_board_frames(realistic, realistic, pd.DataFrame())
    assert any(g.name == "no_star_in_realistic" for g in report.failures)


def test_identical_risk_fails_diversity_gate() -> None:
    board = _good_board()
    board["risk_score"] = 15.0
    report = validate_board_frames(board, board, pd.DataFrame())
    assert any(g.name == "risk_diversity" for g in report.failures)
