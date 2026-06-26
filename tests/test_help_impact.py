"""Tests for help-impact profile validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_profile_requires_top_help_areas() -> None:
    frames = base_reasoning_frames()
    frames["profiles"].loc[0, "top_gaps_helped"] = ""
    result = validate_reasoning_frames(**frames)
    assert "profile_missing_top_help_areas" in gate_names(result)


def test_profile_missing_help_impact_artifact_row_fails() -> None:
    frames = base_reasoning_frames()
    frames["help_impact"] = frames["help_impact"].iloc[0:0].copy()
    result = validate_reasoning_frames(**frames)
    assert "profile_missing_help_impact" in gate_names(result)
