"""Tests for the initial MoreyMachine project infrastructure."""

from __future__ import annotations

import importlib
from pathlib import Path

from moreymachine.utils.config import load_settings
from moreymachine.utils.logging import get_logger
from moreymachine.utils.paths import (
    DATA_DIR,
    PROJECT_ROOT,
    REQUIRED_PROJECT_DIRS,
    data_path,
    project_path,
)


def test_required_directories_exist() -> None:
    """The repo should include the expected initial project directories."""
    assert PROJECT_ROOT.is_dir()
    for directory in REQUIRED_PROJECT_DIRS:
        assert directory.is_dir(), f"Missing required directory: {directory}"


def test_package_imports_work() -> None:
    """Core package modules should import from the repo root."""
    for module_name in (
        "moreymachine",
        "moreymachine.utils",
        "moreymachine.utils.paths",
        "moreymachine.utils.logging",
        "moreymachine.utils.config",
        "moreymachine.data.playoff_tiers",
        "moreymachine.features.quality_tiers",
    ):
        assert importlib.import_module(module_name)


def test_path_helpers_resolve_under_project_root() -> None:
    """Path helpers should produce absolute paths under expected roots."""
    assert project_path("README.md") == PROJECT_ROOT / "README.md"
    assert data_path("raw") == DATA_DIR / "raw"
    assert project_path("src", "moreymachine").is_dir()


def test_load_settings_allows_environment_overrides(tmp_path: Path) -> None:
    """Environment mappings should override default settings without side effects."""
    settings = load_settings(
        environ={
            "MOREYMACHINE_ENV": "test",
            "MOREYMACHINE_DATA_DIR": str(tmp_path / "data"),
            "MOREYMACHINE_LOG_LEVEL": "debug",
        }
    )

    assert settings.environment == "test"
    assert settings.data_dir == tmp_path / "data"
    assert settings.nba_api_cache_dir == tmp_path / "data" / "raw" / "nba_api"
    assert settings.nba_start_season == "2015-16"
    assert settings.log_level == "DEBUG"


def test_get_logger_uses_project_namespace() -> None:
    """The default logger should use the project namespace."""
    assert get_logger().name == "moreymachine"
