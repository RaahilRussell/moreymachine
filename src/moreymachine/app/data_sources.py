"""Central registry of MoreyMachine datasets with provenance.

This module is the single place that knows where every dataset lives, what it
is (real / manual / demo), and where it came from. It powers both the app's
"Data Sources" panel and the REAL_DATA_MODE loading guards, so the app can never
silently show demo data or a number without provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_FREE_AGENTS_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_RANKINGS_TRADE_TARGETS_PATH,
    CANDIDATE_RANKINGS_WATCHLIST_PATH,
    CANDIDATE_UNIVERSE_PATH,
    CANDIDATES_PATH,
    CONTRACTS_PATH,
    CURRENT_ROSTER_REFERENCE_PATH,
    FEATURES_DATA_DIR,
    PLAYER_BIO_PATH,
    PLAYER_ROLE_EXPLANATIONS_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    PLAYOFF_TIERS_PATH,
    REPORTS_DATA_DIR,
    TEAM_SEASONS_PATH,
    TEAM_SEASONS_WITH_TIERS_PATH,
)
from moreymachine.utils.real_data import fix_hint

Status = Literal["real", "manual", "demo"]


@dataclass(frozen=True)
class Dataset:
    """A registered dataset and how to describe its provenance."""

    key: str
    label: str
    path: Path
    status: Status
    source: str
    fix_table: str
    season_column: str | None = "season"


REGISTRY: tuple[Dataset, ...] = (
    Dataset(
        "team_seasons",
        "Team seasons (advanced)",
        TEAM_SEASONS_PATH,
        "real",
        "nba_api LeagueDashTeamStats (NBA.com Stats): Base + Advanced + Four Factors",
        "team_seasons",
    ),
    Dataset(
        "player_seasons",
        "Player seasons (advanced)",
        PLAYER_SEASONS_PATH,
        "real",
        "nba_api LeagueDashPlayerStats (NBA.com Stats): Base + Advanced",
        "player_seasons",
    ),
    Dataset(
        "playoff_tiers",
        "Playoff tiers",
        PLAYOFF_TIERS_PATH,
        "manual",
        "Hand-verified NBA.com / BBRef playoff results (2015-16..2024-25)",
        "playoff_tiers",
    ),
    Dataset(
        "team_seasons_with_tiers",
        "Team seasons + tiers",
        TEAM_SEASONS_WITH_TIERS_PATH,
        "real",
        "Join of real team_seasons with manual playoff tiers + quality tiers",
        "team_seasons_with_tiers",
    ),
    Dataset(
        "team_fingerprints",
        "Team fingerprints",
        FEATURES_DATA_DIR / "team_fingerprints.parquet",
        "real",
        "Engineered from real team_seasons_with_tiers",
        "team_fingerprints",
    ),
    Dataset(
        "team_roster_archetypes",
        "Team roster archetypes",
        FEATURES_DATA_DIR / "team_roster_archetypes.parquet",
        "real",
        "KMeans clustering of real team fingerprints",
        "team_roster_archetypes",
    ),
    Dataset(
        "player_archetypes",
        "Player archetypes",
        FEATURES_DATA_DIR / "player_archetypes.parquet",
        "real",
        "KMeans clustering of real player_seasons",
        "player_archetypes",
    ),
    Dataset(
        "phi_roster_gaps",
        "Roster gap report",
        REPORTS_DATA_DIR / "phi_roster_gaps.parquet",
        "real",
        "PHI fingerprint vs contender baselines",
        "roster_gaps",
        season_column="target_season",
    ),
    Dataset(
        "candidates",
        "Candidate watchlist",
        CANDIDATES_PATH,
        "manual",
        "Real nba_api players + Basketball-Reference salaries (manual/online import)",
        "candidates",
        season_column=None,
    ),
    Dataset(
        "player_bio",
        "Player bio (position/height/draft)",
        PLAYER_BIO_PATH,
        "real",
        "nba_api PlayerIndex (NBA.com Stats)",
        "player_bio",
        season_column=None,
    ),
    Dataset(
        "player_tracking",
        "Player tracking (catch-shoot/drives/rim defense)",
        PLAYER_TRACKING_PATH,
        "real",
        "nba_api LeagueDashPtStats (NBA.com Stats)",
        "player_tracking",
        season_column=None,
    ),
    Dataset(
        "contracts",
        "Player contracts",
        CONTRACTS_PATH,
        "real",
        "Basketball-Reference contracts (scraped, id-matched to nba_api)",
        "contracts",
        season_column=None,
    ),
    Dataset(
        "player_roles",
        "Player roles & archetypes",
        PLAYER_ROLE_EXPLANATIONS_PATH,
        "real",
        "Role engine over real bio + tracking + season stats",
        "player_roles",
    ),
    Dataset(
        "candidate_universe",
        "Candidate universe (typed)",
        CANDIDATE_UNIVERSE_PATH,
        "real",
        "One candidate_type per real player from contracts/bio/quality",
        "candidate_universe",
    ),
    Dataset(
        "current_roster_reference",
        "Current Sixers roster reference",
        CURRENT_ROSTER_REFERENCE_PATH,
        "real",
        "PHI 2025-26 roster split out of the acquisition board",
        "candidate_universe",
    ),
    Dataset(
        "candidate_fit_rankings_all",
        "Target board - all candidates",
        CANDIDATE_RANKINGS_ALL_PATH,
        "real",
        "Explanation-first fit scores over the full candidate universe",
        "candidate_rankings",
    ),
    Dataset(
        "candidate_fit_rankings_realistic",
        "Target board - realistic",
        CANDIDATE_RANKINGS_REALISTIC_PATH,
        "real",
        "Realistic free-agent and trade targets (no stars / missing contracts)",
        "candidate_rankings",
    ),
    Dataset(
        "candidate_fit_rankings_free_agents",
        "Target board - free agents",
        CANDIDATE_RANKINGS_FREE_AGENTS_PATH,
        "real",
        "Free-agent / minimum / MLE candidates only",
        "candidate_rankings",
    ),
    Dataset(
        "candidate_fit_rankings_trade_targets",
        "Target board - trade targets",
        CANDIDATE_RANKINGS_TRADE_TARGETS_PATH,
        "real",
        "Realistic / expensive / rookie-scale trade targets only",
        "candidate_rankings",
    ),
    Dataset(
        "candidate_fit_rankings_watchlist",
        "Target board - unrealistic watchlist",
        CANDIDATE_RANKINGS_WATCHLIST_PATH,
        "real",
        "Theoretical fit only - stars, untouchable core, missing contracts",
        "candidate_rankings",
    ),
    Dataset(
        "contender_predictions",
        "Contender model predictions",
        REPORTS_DATA_DIR / "contender_model_predictions.parquet",
        "real",
        "Chronologically validated deep-playoff model",
        "contender_model",
    ),
    Dataset(
        "backtest_rankings",
        "Backtest rankings",
        REPORTS_DATA_DIR / "backtest_rankings.parquet",
        "real",
        "Historical fit rankings vs next-season outcomes",
        "backtest",
        season_column="offseason",
    ),
)

REGISTRY_BY_KEY: dict[str, Dataset] = {dataset.key: dataset for dataset in REGISTRY}

# Datasets that must exist before the app is meaningful in REAL_DATA_MODE.
REQUIRED_KEYS: tuple[str, ...] = (
    "team_seasons",
    "player_seasons",
    "team_fingerprints",
    "phi_roster_gaps",
    "candidate_universe",
    "candidate_fit_rankings_realistic",
)


def dataset_status_row(dataset: Dataset) -> dict[str, object]:
    """Build one Data Sources panel row for a dataset (rows/seasons/updated)."""
    exists = dataset.path.exists()
    row: dict[str, object] = {
        "table": dataset.label,
        "status": dataset.status,
        "source": dataset.source,
        "path": _relative_path(dataset.path),
        "present": exists,
        "rows": 0,
        "seasons": "",
        "last_updated": "",
    }
    if not exists:
        row["last_updated"] = "MISSING"
        row["seasons"] = f"missing - {fix_hint(dataset.fix_table)}"
        return row

    frame = _safe_read(dataset.path)
    row["rows"] = 0 if frame is None else len(frame)
    row["last_updated"] = _last_updated(dataset, frame)
    row["seasons"] = _season_span(dataset, frame)
    return row


def data_source_table() -> pd.DataFrame:
    """Return the full Data Sources panel as a DataFrame."""
    return pd.DataFrame(dataset_status_row(dataset) for dataset in REGISTRY)


def _safe_read(path: Path) -> pd.DataFrame | None:
    try:
        if path.suffix == ".csv":
            return pd.read_csv(path)
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".json":
            return pd.DataFrame([json.loads(path.read_text(encoding="utf-8"))])
    except Exception:  # noqa: BLE001 - panel must never crash the app
        return None
    return None


def _last_updated(dataset: Dataset, frame: pd.DataFrame | None) -> str:
    if frame is not None and "pulled_at" in frame.columns and not frame.empty:
        values = frame["pulled_at"].dropna().astype(str)
        if not values.empty:
            return f"{values.max()} (pulled_at)"
    mtime = datetime.fromtimestamp(dataset.path.stat().st_mtime, tz=UTC)
    return f"{mtime.date().isoformat()} (file)"


def _season_span(dataset: Dataset, frame: pd.DataFrame | None) -> str:
    column = dataset.season_column
    if frame is None or column is None or column not in frame.columns:
        return "n/a"
    seasons = sorted(frame[column].dropna().astype(str).unique())
    if not seasons:
        return "n/a"
    if len(seasons) == 1:
        return seasons[0]
    return f"{seasons[0]} .. {seasons[-1]} ({len(seasons)})"


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
