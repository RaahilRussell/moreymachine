"""Tests for the refresh result + freshness reporting additions."""

from __future__ import annotations

from pathlib import Path

from moreymachine.data.freshness import (
    TableFreshness,
    render_freshness_markdown,
)
from moreymachine.data.refresh import RefreshResult


def test_refresh_result_reports_failures() -> None:
    result = RefreshResult(
        season="2025-26",
        statuses={"player_bio": "ok", "contracts": "failed: HTTPError"},
    )
    assert result.failures == ["contracts"]


def test_clean_refresh_has_no_failures() -> None:
    result = RefreshResult(season="2025-26", statuses={"a": "ok", "b": "ok"})
    assert result.failures == []


def test_freshness_markdown_has_age_and_status_columns() -> None:
    summary = TableFreshness(
        name="player_seasons",
        path=Path("data/processed/player_seasons.parquet"),
        exists=True,
        rows=100,
        seasons="2025-26",
        source="nba_api",
        pulled_at="2026-06-25",
        data_mode="real_api",
        data_age_days="0d",
        refresh_status="fresh",
    )
    markdown = render_freshness_markdown([summary])
    assert "Age" in markdown
    assert "Status" in markdown
    assert "fresh" in markdown
    assert "0d" in markdown
