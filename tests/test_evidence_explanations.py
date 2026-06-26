"""Tests for evidence-backed explanations."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_every_claim_must_link_to_existing_evidence() -> None:
    frames = base_reasoning_frames()
    frames["claims"].loc[0, "evidence_object_ids"] = '["missing_evidence"]'
    result = validate_reasoning_frames(**frames)
    assert "claim_evidence" in gate_names(result)


def test_unsupported_defense_claim_must_be_explicitly_denied() -> None:
    frames = base_reasoning_frames()
    mask = frames["claims"]["claim_type"] == "wing_defense"
    frames["claims"].loc[mask, "claim"] = "adds wing defense."
    result = validate_reasoning_frames(**frames)
    assert "unsupported_wing_defense_claim" in gate_names(result)
