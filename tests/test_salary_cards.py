"""Tests for salary-card validation."""

from __future__ import annotations

import pandas as pd

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_missing_cap_hit_must_be_flagged_on_salary_card() -> None:
    frames = base_reasoning_frames()
    frames["salary_cards"].loc[0, "cap_hit_millions"] = pd.NA
    frames["salary_cards"].loc[0, "missing_data_flags"] = "none"
    frames["salary_cards"].loc[0, "salary_warning_flags"] = "[]"
    result = validate_reasoning_frames(**frames)
    assert "salary_cap_hit_missing_not_flagged" in gate_names(result)


def test_ambiguous_salary_millions_field_fails() -> None:
    frames = base_reasoning_frames()
    frames["salary_cards"]["salary_millions"] = 5.0
    result = validate_reasoning_frames(**frames)
    assert "ambiguous_salary_field" in gate_names(result)
