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
PLAYER_BIO_PATH = PROCESSED_DATA_DIR / "player_bio.parquet"
PLAYER_TRACKING_PATH = PROCESSED_DATA_DIR / "player_tracking.parquet"
LINEUP_ON_OFF_PATH = PROCESSED_DATA_DIR / "lineup_on_off.parquet"
CONTRACTS_PATH = PROCESSED_DATA_DIR / "contracts.parquet"
RAW_CONTRACTS_PATH = PROCESSED_DATA_DIR / "contracts_raw.parquet"
PLAYOFF_TIERS_PATH = MANUAL_DATA_DIR / "playoff_tiers.csv"
CANDIDATES_PATH = MANUAL_DATA_DIR / "candidates.csv"
MANUAL_CONTRACTS_PATH = MANUAL_DATA_DIR / "contracts.csv"

# Candidate board outputs split by acquisition feasibility.
CANDIDATE_RANKINGS_ALL_PATH = REPORTS_DATA_DIR / "candidate_fit_rankings_all.parquet"
CANDIDATE_RANKINGS_REALISTIC_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_realistic.parquet"
)
CANDIDATE_RANKINGS_FREE_AGENTS_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_free_agents.parquet"
)
CANDIDATE_RANKINGS_TRADE_TARGETS_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_trade_targets.parquet"
)
CANDIDATE_RANKINGS_WATCHLIST_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_unrealistic_watchlist.parquet"
)
PLAYER_ROLES_PATH = FEATURES_DATA_DIR / "player_roles.parquet"
PLAYER_ROLE_EXPLANATIONS_PATH = REPORTS_DATA_DIR / "player_role_explanations.parquet"
CURRENT_ROSTER_REFERENCE_PATH = REPORTS_DATA_DIR / "current_roster_reference.parquet"
CANDIDATE_UNIVERSE_PATH = FEATURES_DATA_DIR / "candidate_universe.parquet"
CANDIDATE_UNIVERSE_SUMMARY_PATH = REPORTS_DATA_DIR / "candidate_universe_summary.md"
TARGET_BOARD_VALIDATION_PATH = REPORTS_DATA_DIR / "target_board_validation.md"
DATA_FRESHNESS_REPORT_PATH = REPORTS_DATA_DIR / "data_freshness_report.md"

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
