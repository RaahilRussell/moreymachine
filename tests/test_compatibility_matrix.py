"""Tests for core-compatibility validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_player_cannot_claim_core_fit_without_compatibility_text() -> None:
    frames = base_reasoning_frames()
    frames["rankings"].loc[0, "fit_with_embiid"] = "not evaluated"
    result = validate_reasoning_frames(**frames)
    assert "core_compatibility_missing" in gate_names(result)


def test_core_compatibility_rows_need_evidence() -> None:
    frames = base_reasoning_frames()
    frames["compatibility"].loc[0, "evidence"] = ""
    result = validate_reasoning_frames(**frames)
    assert "core_compatibility_missing_evidence" in gate_names(result)
