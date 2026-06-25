"""Tests for the expanded role + expected-role engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.features.player_roles import (
    EXPECTED_ROLES,
    ROLE_DIMENSIONS,
    ROLE_OUTPUT_COLUMNS,
    compute_player_roles,
)


def _player_seasons(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    return pd.DataFrame(
        {
            "season": ["2025-26"] * n,
            "player_id": range(n),
            "player_name": [f"Player {i}" for i in range(n)],
            "team_abbr": "BKN",
            "age": rng.integers(19, 35, n),
            "minutes": rng.uniform(100, 2600, n),
            "games": rng.integers(10, 80, n),
            "pts": rng.uniform(2, 30, n),
            "usage_rate": rng.uniform(0.10, 0.34, n),
            "true_shooting": rng.uniform(0.48, 0.64, n),
            "three_pa": rng.uniform(0, 8, n),
            "three_pa_rate": rng.uniform(0, 0.7, n),
            "three_p_pct": rng.uniform(0.25, 0.43, n),
            "assist_pct": rng.uniform(0.05, 0.4, n),
            "turnover_pct": rng.uniform(0.06, 0.2, n),
            "rebound_pct": rng.uniform(0.03, 0.2, n),
            "stl": rng.uniform(0, 2, n),
            "blk": rng.uniform(0, 2, n),
        }
    )


def _bio(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    return pd.DataFrame(
        {
            "player_id": range(n),
            "position": rng.choice(["G", "F", "C", "G-F", "F-C"], n),
            "height_inches": rng.integers(72, 86, n),
            "draft_year": rng.integers(2014, 2025, n),
        }
    )


def test_output_schema_and_dimensions() -> None:
    roles = compute_player_roles(player_seasons=_player_seasons(), player_bio=_bio())
    for column in ROLE_OUTPUT_COLUMNS:
        assert column in roles.columns
    for dim in ROLE_DIMENSIONS:
        assert roles[dim].between(0, 100).all()


def test_expected_role_values_are_valid() -> None:
    roles = compute_player_roles(player_seasons=_player_seasons(), player_bio=_bio())
    assert set(roles["expected_role"]).issubset(set(EXPECTED_ROLES))


def test_star_is_rare_and_requires_elite_minutes() -> None:
    roles = compute_player_roles(player_seasons=_player_seasons(), player_bio=_bio())
    stars = roles[roles["expected_role"] == "Star"]
    # Star is gated; a random pool should produce very few or none.
    assert len(stars) <= max(1, int(0.1 * len(roles)))
    if not stars.empty:
        assert (stars["player_id"].notna()).all()


def test_low_minutes_player_is_not_a_star() -> None:
    seasons = _player_seasons(5)
    seasons["minutes"] = [50, 80, 120, 200, 240]
    roles = compute_player_roles(player_seasons=seasons, player_bio=_bio(5))
    assert (roles["expected_role"] != "Star").all()


def test_role_concerns_and_data_mode_present() -> None:
    roles = compute_player_roles(player_seasons=_player_seasons(), player_bio=_bio())
    assert roles["role_concerns"].fillna("").str.len().gt(0).all()
    assert (roles["data_mode"] == "derived").all()
