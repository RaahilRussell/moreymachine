"""Tests for target board explanations and capped recommendations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.features.player_roles import ROLE_DIMENSIONS
from moreymachine.models.scoring import score_candidates
from moreymachine.models.target_board import (
    BOARD_COLUMNS,
    MAX_PRIORITY_TARGETS,
    _assign_recommendations,
    _attach_explanations,
)

REQUIRED_EXPLANATION_COLUMNS = (
    "why_fit",
    "concerns",
    "role_on_sixers",
    "acquisition_summary",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "data_sources",
    "explanation_confidence",
    "board_type",
)


def _scored() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    n = 90
    frame = pd.DataFrame(
        {
            "player_id": range(n),
            "player_name": [f"Player {i}" for i in range(n)],
            "current_team": "BKN",
            "position": "F",
            "role_archetype": "3-and-D Wing",
            "role_confidence": "high",
            "role_concerns": "no major role concerns",
            "expected_role": rng.choice(
                ["Starter", "Rotation Player", "Bench Specialist"], n
            ),
            "candidate_type": ["realistic_trade_target"] * 60
            + ["star_unrealistic"] * 18
            + ["missing_contract_status"] * 12,
            "feasibility_tier": "Possible",
            "acquisition_feasibility": rng.uniform(20, 80, n),
            "acquisition_reason": "Movable in a trade.",
            "quality_percentile": rng.uniform(0, 1, n),
            "cap_hit_millions": rng.uniform(1, 30, n),
            "contract_status": "signed_long_term",
            "salary_source": "bbref",
            "minutes": rng.uniform(200, 2400, n),
            "age": rng.integers(19, 36, n),
            "three_pa": rng.uniform(0, 8, n),
            "turnover_pct": rng.uniform(0.06, 0.2, n),
            "years_remaining": rng.integers(0, 4, n),
            "catch_shoot_fg3a": rng.uniform(0, 6, n),
            "missing_data_flags": "none",
        }
    )
    for dim in ROLE_DIMENSIONS:
        frame[dim] = rng.uniform(20, 90, n)
    gaps = pd.DataFrame(
        {
            "category_key": ["shooting_pressure", "defense"],
            "severity_score": [45.0, 40.0],
        }
    )
    return score_candidates(frame, roster_gaps=gaps)


def test_attach_explanations_fills_required_columns() -> None:
    board = _attach_explanations(_scored())
    for column in REQUIRED_EXPLANATION_COLUMNS:
        assert column in board.columns
        assert board[column].fillna("").astype(str).str.len().gt(0).all()


def test_priority_targets_capped_and_realistic_only() -> None:
    board = _assign_recommendations(_attach_explanations(_scored()))
    priority = board[board["recommendation"] == "Priority Target"]
    assert len(priority) <= MAX_PRIORITY_TARGETS
    assert priority["candidate_type"].eq("realistic_trade_target").all()


def test_stars_and_missing_contracts_never_recommended() -> None:
    board = _assign_recommendations(_attach_explanations(_scored()))
    stars = board[board["candidate_type"] == "star_unrealistic"]
    missing = board[board["candidate_type"] == "missing_contract_status"]
    assert stars["recommendation"].eq("Unrealistic / Unavailable").all()
    assert missing["recommendation"].eq("Missing Data / Cannot Evaluate").all()


def test_board_columns_are_a_superset_of_required() -> None:
    board = _assign_recommendations(_attach_explanations(_scored()))
    present = [c for c in BOARD_COLUMNS if c in board.columns]
    # The full schema should be available to slice the board with.
    assert len(present) >= 40
