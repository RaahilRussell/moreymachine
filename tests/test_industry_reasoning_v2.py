"""Tests for cross-artifact reasoning validation v2."""

from __future__ import annotations

import json

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_valid_minimal_reasoning_frames_pass() -> None:
    frames = base_reasoning_frames()
    result = validate_reasoning_frames(**frames)
    assert result.passed, result.to_markdown()


def test_priority_requires_feasibility_and_current_status() -> None:
    frames = base_reasoning_frames()
    rankings = frames["rankings"]
    rankings.loc[0, "recommendation"] = "Priority Target"
    rankings.loc[0, "acquisition_feasibility_score"] = 35.0
    frames["candidate_universe"].loc[0, "candidate_status_freshness"] = (
        "manual_verification_required"
    )
    result = validate_reasoning_frames(**frames)
    assert "priority_low_feasibility" in gate_names(result)
    assert "priority_unknown_or_stale_status" in gate_names(result)


def test_gap_credit_requires_skill_permission() -> None:
    frames = base_reasoning_frames()
    frames["rankings"].loc[0, "gaps_addressed"] = json.dumps(
        ["Rim protection without Embiid"]
    )
    result = validate_reasoning_frames(**frames)
    assert "gap_without_skill_permission" in gate_names(result)
