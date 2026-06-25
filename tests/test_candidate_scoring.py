"""Tests for the saturation-free candidate scoring engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.models.candidate_scoring import SCORE_COLUMNS, score_candidates


def _candidates(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    role_dims = {
        dim: rng.uniform(10, 90, n)
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
        )
    }
    return pd.DataFrame(
        {
            "player_id": range(n),
            "player_name": [f"Player {i}" for i in range(n)],
            "candidate_type": rng.choice(
                ["realistic_trade_target", "minimum_candidate", "mle_candidate"], n
            ),
            "quality_percentile": rng.uniform(0, 1, n),
            "salary_millions": rng.uniform(1, 30, n),
            "minutes": rng.uniform(200, 2400, n),
            "age": rng.integers(19, 36, n),
            "usage_rate": rng.uniform(0.1, 0.32, n),
            "three_pa": rng.uniform(0, 600, n),
            "turnover_pct": rng.uniform(0.06, 0.2, n),
            "years_remaining": rng.integers(0, 4, n),
            "catch_shoot_fg3a": rng.uniform(0, 400, n),
            "role_confidence": rng.choice(["low", "medium", "high"], n),
            "missing_data_flags": "none",
            **role_dims,
        }
    )


def test_score_columns_present() -> None:
    scored = score_candidates(_candidates())
    for column in SCORE_COLUMNS:
        assert column in scored.columns


def test_contract_value_and_portability_are_not_saturated() -> None:
    scored = score_candidates(_candidates())
    assert (scored["contract_value"] >= 99.95).mean() <= 0.10
    assert (scored["portability"] >= 99.95).mean() <= 0.10


def test_risk_is_not_a_single_constant() -> None:
    scored = score_candidates(_candidates())
    share = scored["risk_score"].round(0).value_counts(normalize=True).iloc[0]
    assert share < 0.50
    assert scored["risk_tier"].nunique() >= 2


def test_contender_gain_is_minutes_aware() -> None:
    # A bench-minutes player cannot out-score an otherwise identical starter.
    base = {
        "player_id": [1, 2],
        "player_name": ["Bench", "Starter"],
        "candidate_type": ["realistic_trade_target", "realistic_trade_target"],
        "quality_percentile": [0.30, 0.85],
        "salary_millions": [5.0, 5.0],
        "minutes": [300, 2200],
        "age": [25, 25],
        "three_pa": [100, 100],
        "turnover_pct": [0.12, 0.12],
        "years_remaining": [2, 2],
        "role_confidence": ["high", "high"],
        "missing_data_flags": ["none", "none"],
    }
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
        base[dim] = [60, 60]
    scored = score_candidates(pd.DataFrame(base))
    bench = scored[scored["player_name"] == "Bench"]["contender_gain"].iloc[0]
    starter = scored[scored["player_name"] == "Starter"]["contender_gain"].iloc[0]
    assert bench < starter


def test_empty_input_returns_score_columns() -> None:
    scored = score_candidates(pd.DataFrame())
    for column in SCORE_COLUMNS:
        assert column in scored.columns
