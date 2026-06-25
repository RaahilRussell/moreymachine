"""Tests for the expanded Sixers roster diagnosis."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.features.player_roles import ROLE_DIMENSIONS
from moreymachine.features.sixers_diagnosis import (
    COMPOSITION_GAPS,
    DIAGNOSIS_COLUMNS,
    _composition_gaps,
    _gap_tier,
)


def _roster(n: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    frame = pd.DataFrame(
        {
            "player_name": [f"PHI Player {i}" for i in range(n)],
            "role_archetype": rng.choice(
                ["3-and-D Wing", "Rim Protector", "Creator", "Shooter"],
                n,
            ),
            "height_inches": rng.integers(74, 84, n),
            "sample_reliability": rng.uniform(20, 95, n),
        }
    )
    for dim in ROLE_DIMENSIONS:
        frame[dim] = rng.uniform(20, 90, n)
    return frame


def test_composition_gaps_have_full_schema() -> None:
    gaps = _composition_gaps(_roster(), team="PHI", season="2025-26")
    assert len(gaps) == len(COMPOSITION_GAPS)
    for column in DIAGNOSIS_COLUMNS:
        assert column in gaps.columns
    assert gaps["gap_kind"].eq("composition").all()


def test_every_gap_carries_explanations() -> None:
    gaps = _composition_gaps(_roster(), team="PHI", season="2025-26")
    for column in (
        "what_it_means",
        "why_it_matters_in_playoffs",
        "what_kind_of_player_fixes_it",
        "data_sources",
    ):
        assert gaps[column].fillna("").str.len().gt(0).all()


def test_severity_non_negative_and_tiers_valid() -> None:
    gaps = _composition_gaps(_roster(), team="PHI", season="2025-26")
    assert (gaps["severity_score"] >= 0).all()
    valid = {"Critical", "Significant", "Moderate", "Minor", "Strength", "Unknown"}
    assert set(gaps["gap_tier"]).issubset(valid)


def test_gap_tier_thresholds() -> None:
    assert _gap_tier(40) == "Critical"
    assert _gap_tier(25) == "Significant"
    assert _gap_tier(12) == "Moderate"
    assert _gap_tier(3) == "Minor"
    assert _gap_tier(0) == "Strength"


def test_empty_roster_returns_empty_frame() -> None:
    gaps = _composition_gaps(pd.DataFrame(), team="PHI", season="2025-26")
    assert gaps.empty
