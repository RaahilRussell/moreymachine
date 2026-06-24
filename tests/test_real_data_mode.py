"""Tests that fake/demo data cannot enter REAL_DATA_MODE."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from moreymachine.app.data_sources import REGISTRY
from moreymachine.utils.config import load_settings
from moreymachine.utils.paths import DEMO_DATA_DIR, TEAM_SEASONS_PATH
from moreymachine.utils.real_data import (
    DemoDataInRealModeError,
    MissingRealDataError,
    guard_against_demo,
    is_demo_path,
    require_real_file,
)


def _real_settings():
    return load_settings(environ={"REAL_DATA_MODE": "true"})


def _demo_settings():
    return load_settings(environ={"REAL_DATA_MODE": "false"})


def test_real_data_mode_is_on_by_default() -> None:
    assert load_settings(environ={}).real_data_mode is True


def test_is_demo_path_detects_demo_directory() -> None:
    assert is_demo_path(DEMO_DATA_DIR / "anything.parquet") is True
    assert is_demo_path(TEAM_SEASONS_PATH) is False


def test_guard_rejects_demo_path_in_real_mode() -> None:
    with pytest.raises(DemoDataInRealModeError):
        guard_against_demo(DEMO_DATA_DIR / "x.parquet", settings=_real_settings())


def test_guard_allows_demo_path_when_real_mode_off() -> None:
    path = DEMO_DATA_DIR / "x.parquet"
    assert guard_against_demo(path, settings=_demo_settings()) == path


def test_require_real_file_raises_on_missing_in_real_mode(tmp_path: Path) -> None:
    missing = tmp_path / "nope.parquet"
    with pytest.raises(MissingRealDataError) as info:
        require_real_file(
            missing,
            table="team_seasons",
            how_to_fix="run fetch",
            settings=_real_settings(),
        )
    assert "team_seasons" in str(info.value)


def test_require_real_file_returns_path_when_present(tmp_path: Path) -> None:
    present = tmp_path / "ok.parquet"
    present.write_text("data", encoding="utf-8")
    assert (
        require_real_file(present, table="t", how_to_fix="x", settings=_real_settings())
        == present
    )


def test_dataset_registry_has_no_demo_entries() -> None:
    # The app must never register a demo dataset as a source of rankings.
    assert all(dataset.status != "demo" for dataset in REGISTRY)
    assert all(not is_demo_path(dataset.path) for dataset in REGISTRY)


def test_app_load_never_returns_demo_data(monkeypatch) -> None:
    app = importlib.import_module("moreymachine.app.streamlit_app")
    # Even if a registry path were pointed at demo data, load() refuses it.
    dataset = app.REGISTRY_BY_KEY["team_seasons"]
    object.__setattr__(dataset, "path", DEMO_DATA_DIR / "team_fingerprints.parquet")
    try:
        assert app.load("team_seasons").empty
    finally:
        importlib.reload(app)
