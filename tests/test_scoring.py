"""Tests for the max-rebuild scoring engine (models/scoring.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.features.player_roles import ROLE_DIMENSIONS
from moreymachine.models.scoring import (
    MINUTES_SHARE_BY_ROLE,
    SCORE_COLUMNS,
    score_candidates,
)


def _candidates(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(13)
    frame = pd.DataFrame(
        {
            "player_id": range(n),
            "player_name": [f"Player {i}" for i in range(n)],
            "candidate_type": rng.choice(
                ["realistic_trade_target", "minimum_candidate", "mle_candidate"], n
            ),
            "expected_role": rng.choice(list(MINUTES_SHARE_BY_ROLE), n),
            "role_confidence": rng.choice(["low", "medium", "high"], n),
            "quality_percentile": rng.uniform(0, 1, n),
            "cap_hit_millions": rng.uniform(1, 35, n),
            "acquisition_feasibility": rng.uniform(10, 90, n),
            "minutes": rng.uniform(200, 2500, n),
            "age": rng.integers(19, 36, n),
            "three_pa": rng.uniform(0, 8, n),
            "turnover_pct": rng.uniform(0.06, 0.2, n),
            "years_remaining": rng.integers(0, 4, n),
            "catch_shoot_fg3a": rng.uniform(0, 6, n),
            "missing_data_flags": "none",
        }
    )
    for dim in ROLE_DIMENSIONS:
        frame[dim] = rng.uniform(15, 92, n)
    return frame


def _gaps() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "category_key": ["shooting_pressure", "defense", "rebounding"],
            "severity_score": [45.0, 40.0, 20.0],
        }
    )


def test_all_score_columns_present() -> None:
    scored = score_candidates(_candidates(), roster_gaps=_gaps())
    for column in SCORE_COLUMNS:
        assert column in scored.columns


def test_portability_95_is_rare() -> None:
    scored = score_candidates(_candidates(), roster_gaps=_gaps())
    assert (scored["portability"] >= 95).mean() <= 0.05


def test_contract_value_95_is_rare() -> None:
    scored = score_candidates(_candidates(), roster_gaps=_gaps())
    assert (scored["contract_value"] >= 95).mean() <= 0.10


def test_risk_distribution_does_not_collapse() -> None:
    scored = score_candidates(_candidates(), roster_gaps=_gaps())
    share = scored["risk_score"].round(0).value_counts(normalize=True).iloc[0]
    assert share < 0.50


def test_contender_gain_is_minutes_share_aware() -> None:
    base = {
        "player_id": [1, 2],
        "player_name": ["Bench", "Star"],
        "candidate_type": ["realistic_trade_target"] * 2,
        "expected_role": ["Fringe", "Star"],
        "role_confidence": ["high", "high"],
        "quality_percentile": [0.6, 0.6],
        "cap_hit_millions": [5.0, 5.0],
        "acquisition_feasibility": [60.0, 60.0],
        "minutes": [300, 2400],
        "age": [25, 25],
        "three_pa": [3, 3],
        "turnover_pct": [0.12, 0.12],
        "years_remaining": [2, 2],
        "catch_shoot_fg3a": [3, 3],
        "missing_data_flags": ["none", "none"],
    }
    for dim in ROLE_DIMENSIONS:
        base[dim] = [60, 60]
    scored = score_candidates(pd.DataFrame(base), roster_gaps=_gaps())
    bench = scored.set_index("player_name").loc["Bench", "contender_gain"]
    star = scored.set_index("player_name").loc["Star", "contender_gain"]
    assert bench < star


def test_minimum_player_low_quality_is_not_a_steal() -> None:
    base = {
        "player_id": [1],
        "player_name": ["Idle Min"],
        "candidate_type": ["minimum_candidate"],
        "expected_role": ["Fringe"],
        "role_confidence": ["low"],
        "quality_percentile": [0.10],
        "cap_hit_millions": [2.0],
        "acquisition_feasibility": [88.0],
        "minutes": [250],
        "age": [29],
        "three_pa": [1],
        "turnover_pct": [0.14],
        "years_remaining": [1],
        "catch_shoot_fg3a": [1],
        "missing_data_flags": ["none"],
    }
    for dim in ROLE_DIMENSIONS:
        base[dim] = [40]
    scored = score_candidates(pd.DataFrame(base), roster_gaps=_gaps())
    assert scored["contract_value"].iloc[0] < 75
    assert scored["surplus_or_overpay_label"].iloc[0] != "Steal"
