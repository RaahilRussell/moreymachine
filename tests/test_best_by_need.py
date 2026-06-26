"""Tests for best-by-need validation."""

from __future__ import annotations

from industry_v2_helpers import base_reasoning_frames, gate_names
from moreymachine.models.reasoning_validation_v2 import validate_reasoning_frames


def test_best_by_need_requires_top_players_column() -> None:
    frames = base_reasoning_frames()
    frames["best_by_need"] = frames["best_by_need"].drop(columns=["top_players"])
    result = validate_reasoning_frames(**frames)
    assert "best_by_need_schema" in gate_names(result)
