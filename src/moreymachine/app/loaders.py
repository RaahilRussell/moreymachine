"""Streamlit-safe loaders for team-scoped artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import ensure_team_output_dirs, normalize_team


def get_team_output_dir(team: str) -> Path:
    """Return the team output directory."""
    return ensure_team_output_dirs(normalize_team(team))["root"]


def load_team_artifact(
    team: str,
    relative_path: str,
    default: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Load a team-scoped Parquet or CSV artifact."""
    path = get_team_output_dir(team) / relative_path
    if not path.exists():
        return pd.DataFrame() if default is None else default
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.DataFrame() if default is None else default


def load_team_json(team: str, relative_path: str, default: Any = None) -> Any:
    """Load a team-scoped JSON artifact."""
    path = get_team_output_dir(team) / relative_path
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_available_teams() -> list[str]:
    """Return teams with generated output directories."""
    root = get_team_output_dir("PHI").parent
    teams = sorted(path.name for path in root.iterdir() if path.is_dir())
    return teams or ["PHI"]


def get_missing_artifact_message(team: str) -> str:
    """Return the command users should run for missing team outputs."""
    normalized = normalize_team(team)
    return (
        f"Missing analysis outputs for {normalized}.\n"
        "Run:\n"
        f"python scripts/run_team_pipeline.py --team {normalized}"
    )
