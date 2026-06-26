"""Tests for player-profile validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_every_board_player_needs_clickable_profile_id() -> None:
    frames = base_reasoning_frames()
    frames["profiles"].loc[0, "player_profile_id"] = ""
    result = validate_reasoning_frames(**frames)
    assert "clickable_row_missing_profile_id" in gate_names(result)


def test_profile_missing_salary_card_fails() -> None:
    frames = base_reasoning_frames()
    frames["salary_cards"] = frames["salary_cards"].iloc[0:0].copy()
    result = validate_reasoning_frames(**frames)
    assert "profile_missing_salary_card" in gate_names(result)
