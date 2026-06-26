"""Tests for fit-breakdown validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_profile_missing_fit_breakdown_fails() -> None:
    frames = base_reasoning_frames()
    frames["fit_breakdowns"] = frames["fit_breakdowns"].iloc[0:0].copy()
    result = validate_reasoning_frames(**frames)
    assert "profile_missing_fit_breakdown" in gate_names(result)
