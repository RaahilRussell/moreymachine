"""Runtime configuration loading for MoreyMachine."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from moreymachine.utils.paths import DATA_DIR, NBA_API_RAW_DIR, PROJECT_ROOT


@dataclass(frozen=True)
class Settings:
    """Project settings loaded from defaults, .env, and environment variables."""

    environment: str
    project_root: Path
    data_dir: Path
    nba_api_cache_dir: Path
    nba_start_season: str
    nba_latest_season: str
    log_level: str
    real_data_mode: bool


def load_settings(
    env_file: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load settings from defaults, an optional .env file, and the environment."""
    dotenv_values = _read_dotenv(env_file)
    environment_values = dict(os.environ if environ is None else environ)
    values = {**dotenv_values, **environment_values}

    data_dir = _resolve_path(values.get("MOREYMACHINE_DATA_DIR"), default=DATA_DIR)
    nba_api_cache_dir = _resolve_path(
        values.get("MOREYMACHINE_NBA_API_CACHE_DIR"),
        default=(
            NBA_API_RAW_DIR if data_dir == DATA_DIR else data_dir / "raw" / "nba_api"
        ),
    )

    return Settings(
        environment=values.get("MOREYMACHINE_ENV", "development"),
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        nba_api_cache_dir=nba_api_cache_dir,
        nba_start_season=values.get("MOREYMACHINE_NBA_START_SEASON", "2015-16"),
        nba_latest_season=values.get(
            "MOREYMACHINE_NBA_LATEST_SEASON",
            _default_latest_nba_season(),
        ),
        log_level=values.get("MOREYMACHINE_LOG_LEVEL", "INFO").upper(),
        real_data_mode=_parse_bool(values.get("REAL_DATA_MODE"), default=True),
    )


def _parse_bool(value: str | None, *, default: bool) -> bool:
    """Parse a truthy/falsey string, falling back to ``default`` when unset."""
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_dotenv(env_file: str | Path | None) -> dict[str, str]:
    path = Path(env_file) if env_file is not None else PROJECT_ROOT / ".env"
    if not path.exists():
        return {}

    try:
        from dotenv import dotenv_values
    except ImportError:
        return {}

    return {
        key: value for key, value in dotenv_values(path).items() if value is not None
    }


def _resolve_path(value: str | None, *, default: Path) -> Path:
    if value is None or value == "":
        return default

    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _default_latest_nba_season(today: date | None = None) -> str:
    current_date = date.today() if today is None else today
    start_year = current_date.year if current_date.month >= 7 else current_date.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"
