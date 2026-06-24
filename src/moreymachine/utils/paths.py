"""Filesystem paths used across the MoreyMachine project."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
NBA_API_RAW_DIR = RAW_DATA_DIR / "nba_api"
MANUAL_DATA_DIR = DATA_DIR / "manual"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
FEATURES_DATA_DIR = DATA_DIR / "features"
MODELS_DATA_DIR = DATA_DIR / "models"
REPORTS_DATA_DIR = DATA_DIR / "reports"

DEMO_DATA_DIR = DATA_DIR / "demo"

# Canonical processed/manual data files (single source of truth for paths).
TEAM_SEASONS_PATH = PROCESSED_DATA_DIR / "team_seasons.parquet"
PLAYER_SEASONS_PATH = PROCESSED_DATA_DIR / "player_seasons.parquet"
TEAM_SEASONS_WITH_TIERS_PATH = PROCESSED_DATA_DIR / "team_seasons_with_tiers.parquet"
PLAYOFF_TIERS_PATH = MANUAL_DATA_DIR / "playoff_tiers.csv"
CANDIDATES_PATH = MANUAL_DATA_DIR / "candidates.csv"

NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"

REQUIRED_PROJECT_DIRS = (
    DATA_DIR,
    RAW_DATA_DIR,
    NBA_API_RAW_DIR,
    MANUAL_DATA_DIR,
    PROCESSED_DATA_DIR,
    FEATURES_DATA_DIR,
    MODELS_DATA_DIR,
    REPORTS_DATA_DIR,
    NOTEBOOKS_DIR,
    SCRIPTS_DIR,
    TESTS_DIR,
)


def project_path(*parts: str | Path) -> Path:
    """Return an absolute path under the repository root."""
    return PROJECT_ROOT.joinpath(*parts)


def data_path(*parts: str | Path) -> Path:
    """Return an absolute path under the project data directory."""
    return DATA_DIR.joinpath(*parts)


def ensure_directories(
    paths: Iterable[Path] = REQUIRED_PROJECT_DIRS,
) -> tuple[Path, ...]:
    """Create project directories if they do not already exist."""
    directories = tuple(paths)
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return directories
