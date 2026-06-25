"""Tests for the data-contract validation machinery."""

from __future__ import annotations

import pandas as pd

from moreymachine.data.contracts import (
    ALLOWED_DATA_MODES,
    CONTRACTS_BY_KEY,
    TableContract,
    validate_frame,
)


def _contract() -> TableContract:
    return TableContract(
        key="toy",
        path=CONTRACTS_BY_KEY["team_seasons"].path,
        required_columns=("player_id", "salary"),
        provenance_columns=("source", "pulled_at", "data_mode"),
        non_null_columns=("player_id",),
        season_or_date_columns=("season",),
    )


def test_clean_frame_passes_with_no_errors() -> None:
    frame = pd.DataFrame(
        {
            "player_id": [1, 2],
            "salary": [10, 20],
            "source": "nba_api",
            "pulled_at": "2026-06-25",
            "data_mode": "real_api",
            "season": "2025-26",
        }
    )
    report = validate_frame(frame, _contract())
    assert report.passed
    assert not report.warnings


def test_missing_required_column_is_an_error() -> None:
    frame = pd.DataFrame({"player_id": [1], "data_mode": ["real_api"]})
    report = validate_frame(frame, _contract())
    assert not report.passed
    assert any("required" in e for e in report.errors)


def test_null_in_non_null_column_is_an_error() -> None:
    frame = pd.DataFrame({"player_id": [1, None], "salary": [10, 20]})
    report = validate_frame(frame, _contract())
    assert any("null" in e for e in report.errors)


def test_demo_data_mode_is_rejected() -> None:
    frame = pd.DataFrame(
        {"player_id": [1], "salary": [10], "data_mode": ["demo"]}
    )
    report = validate_frame(frame, _contract())
    assert any("data_mode" in e for e in report.errors)
    assert "demo" not in ALLOWED_DATA_MODES


def test_missing_provenance_is_a_warning_not_error() -> None:
    frame = pd.DataFrame({"player_id": [1], "salary": [10], "season": ["2025-26"]})
    report = validate_frame(frame, _contract())
    assert report.passed  # no hard errors
    assert any("provenance" in w for w in report.warnings)
