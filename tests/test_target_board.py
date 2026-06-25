"""Tests for target board explanations and capped recommendations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.models.candidate_scoring import score_candidates
from moreymachine.models.target_board import (
    MAX_PRIORITY_TARGETS,
    _assign_recommendations,
    _attach_explanations,
)

REQUIRED_EXPLANATION_COLUMNS = (
    "why_fit",
    "concerns",
    "role_on_sixers",
    "acquisition_feasibility",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "data_sources",
    "explanation_confidence",
)


def _scored() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    n = 80
    frame = pd.DataFrame(
        {
            "player_id": range(n),
            "player_name": [f"Player {i}" for i in range(n)],
            "current_team": "BKN",
            "position": "F",
            "role_archetype": "3-and-D Wing",
            "role_confidence": "high",
            "candidate_type": ["realistic_trade_target"] * 60
            + ["star_unrealistic"] * 12
            + ["missing_contract_status"] * 8,
            "quality_percentile": rng.uniform(0, 1, n),
            "salary_millions": rng.uniform(1, 30, n),
            "contract_status": "under_contract",
            "minutes": rng.uniform(200, 2400, n),
            "age": rng.integers(19, 36, n),
            "three_pa": rng.uniform(0, 600, n),
            "turnover_pct": rng.uniform(0.06, 0.2, n),
            "years_remaining": rng.integers(0, 4, n),
            "catch_shoot_fg3a": rng.uniform(0, 400, n),
            "missing_data_flags": "none",
        }
    )
    for dim in (
        "creation_score",
        "spacing_score",
        "movement_shooting_score",
        "rim_pressure_score",
        "connector_score",
        "wing_defense_proxy",
        "rim_protection_proxy",
        "rebounding_score",
        "usage_dependency",
        "low_usage_fit",
        "sample_reliability",
    ):
        frame[dim] = rng.uniform(20, 90, n)
    scored = score_candidates(frame)
    return scored.rename(
        columns={"acquisition_feasibility": "acquisition_feasibility_score"}
    )


def test_attach_explanations_fills_required_columns() -> None:
    board = _attach_explanations(_scored())
    for column in REQUIRED_EXPLANATION_COLUMNS:
        assert column in board.columns
        assert board[column].fillna("").astype(str).str.len().gt(0).all()


def test_priority_targets_are_capped_and_realistic_only() -> None:
    board = _assign_recommendations(_attach_explanations(_scored()))
    priority = board[board["recommendation"] == "Priority target"]
    assert len(priority) <= MAX_PRIORITY_TARGETS
    # Every Priority target is a realistic candidate.
    assert priority["candidate_type"].eq("realistic_trade_target").all()


def test_stars_and_missing_contracts_never_recommended() -> None:
    board = _assign_recommendations(_attach_explanations(_scored()))
    stars = board[board["candidate_type"] == "star_unrealistic"]
    missing = board[board["candidate_type"] == "missing_contract_status"]
    assert stars["recommendation"].eq("Unrealistic / unavailable").all()
    assert missing["recommendation"].eq("Missing data / cannot evaluate").all()
