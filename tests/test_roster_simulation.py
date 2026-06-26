"""Tests for roster-slot reasoning validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_vucevic_like_center_cannot_be_starter_without_two_big_evidence() -> None:
    frames = base_reasoning_frames()
    for frame_name in ("rankings", "profiles", "roster_simulation"):
        frames[frame_name].loc[0, "position"] = "C"
        frames[frame_name].loc[0, "starter_possible"] = True
        frames[frame_name].loc[0, "two_big_compatible"] = False
    result = validate_reasoning_frames(**frames)
    assert "center_starter_conflict_with_embiid" in gate_names(result)


def test_true_stretch_big_can_clear_starter_gate_when_two_big_supported() -> None:
    frames = base_reasoning_frames()
    for frame_name in ("rankings", "profiles", "roster_simulation"):
        frames[frame_name].loc[0, "position"] = "C"
        frames[frame_name].loc[0, "starter_possible"] = True
        frames[frame_name].loc[0, "two_big_compatible"] = True
    result = validate_reasoning_frames(**frames)
    assert "center_starter_conflict_with_embiid" not in gate_names(result)
