"""Canonical entity resolution helpers.

This module centralizes player/team normalization so downstream reasoning code
does not do ad hoc string matching. It does not invent identities: unresolved
players stay unresolved and should be surfaced as missing data.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.utils.paths import (
    CANDIDATES_PATH,
    CONTRACTS_PATH,
    PLAYER_SEASONS_PATH,
    TRANSACTIONS_PATH,
)

TEAM_ABBR_ALIASES = {
    "BRK": "BKN",
    "BRO": "BKN",
    "CHA": "CHA",
    "CHO": "CHA",
    "GS": "GSW",
    "GSW": "GSW",
    "LA": "LAL",
    "LAC": "LAC",
    "LAL": "LAL",
    "NO": "NOP",
    "NOK": "NOP",
    "NOH": "NOP",
    "NOP": "NOP",
    "NY": "NYK",
    "NYK": "NYK",
    "PHI": "PHI",
    "PHILA": "PHI",
    "PHX": "PHX",
    "PHO": "PHX",
    "SA": "SAS",
    "SAS": "SAS",
    "UTA": "UTA",
    "UTH": "UTA",
}


@dataclass(frozen=True)
class EntityResolutionReport:
    """Summary from building a player identity map."""

    rows: int
    resolved_players: int
    duplicate_name_keys: int
    unresolved_rows: int


def normalize_player_name(value: object) -> str:
    """Normalize a player name for cross-source matching."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("'", "").replace(".", "").replace("-", " ")
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_team_abbr(value: object) -> str:
    """Normalize team abbreviations while preserving unknown blanks."""
    if value is None or pd.isna(value):
        return ""
    abbr = str(value).strip().upper()
    return TEAM_ABBR_ALIASES.get(abbr, abbr)


def build_player_identity_map(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    contracts_path: str | Path = CONTRACTS_PATH,
    transactions_path: str | Path = TRANSACTIONS_PATH,
    candidates_path: str | Path = CANDIDATES_PATH,
) -> tuple[pd.DataFrame, EntityResolutionReport]:
    """Build a canonical player identity map from available real sources."""
    frames = []
    for source_name, path, reader in (
        ("player_seasons", Path(player_seasons_path), pd.read_parquet),
        ("contracts", Path(contracts_path), pd.read_parquet),
        ("transactions", Path(transactions_path), pd.read_parquet),
        ("manual_candidates", Path(candidates_path), pd.read_csv),
    ):
        if not path.exists():
            continue
        frame = reader(path)
        if "player_name" not in frame.columns:
            continue
        out = pd.DataFrame(
            {
                "player_id": frame.get("player_id"),
                "player_name": frame["player_name"],
                "current_team": frame.get("current_team", frame.get("team_abbr")),
                "source": source_name,
            }
        )
        frames.append(out)
    if not frames:
        empty = pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "normalized_name",
                "current_team",
                "sources",
            ]
        )
        return empty, EntityResolutionReport(0, 0, 0, 0)

    raw = pd.concat(frames, ignore_index=True)
    raw["normalized_name"] = raw["player_name"].map(normalize_player_name)
    raw["current_team"] = raw["current_team"].map(normalize_team_abbr)
    raw["player_id"] = pd.to_numeric(raw["player_id"], errors="coerce")

    grouped = (
        raw.sort_values(["normalized_name", "source"])
        .groupby("normalized_name", dropna=False)
        .agg(
            player_id=("player_id", _first_not_null),
            player_name=("player_name", _first_not_empty),
            current_team=("current_team", _first_not_empty),
            sources=("source", lambda s: "; ".join(sorted(set(map(str, s))))),
            source_row_count=("source", "size"),
            distinct_ids=("player_id", lambda s: len(set(s.dropna().astype(int)))),
        )
        .reset_index()
    )
    grouped["player_id"] = grouped["player_id"].astype("Int64")
    duplicate_names = int((grouped["distinct_ids"] > 1).sum())
    unresolved = int(grouped["player_id"].isna().sum())
    report = EntityResolutionReport(
        rows=len(raw),
        resolved_players=int(grouped["player_id"].notna().sum()),
        duplicate_name_keys=duplicate_names,
        unresolved_rows=unresolved,
    )
    return grouped, report


def detect_duplicate_players(identity_map: pd.DataFrame) -> pd.DataFrame:
    """Return normalized-name keys mapped to multiple canonical IDs."""
    if identity_map.empty or "distinct_ids" not in identity_map.columns:
        return pd.DataFrame()
    return identity_map[identity_map["distinct_ids"] > 1].copy()


def resolve_player_ids(
    frame: pd.DataFrame,
    identity_map: pd.DataFrame,
    *,
    name_column: str = "player_name",
) -> pd.DataFrame:
    """Attach canonical player IDs to a frame without overwriting known IDs."""
    if frame.empty or name_column not in frame.columns or identity_map.empty:
        return frame.copy()
    out = frame.copy()
    out["_normalized_name"] = out[name_column].map(normalize_player_name)
    lookup = identity_map[["normalized_name", "player_id"]].drop_duplicates(
        "normalized_name"
    )
    out = out.merge(
        lookup,
        left_on="_normalized_name",
        right_on="normalized_name",
        how="left",
        suffixes=("", "_canonical"),
    )
    if "player_id" in out.columns:
        out["player_id"] = out["player_id"].combine_first(out["player_id_canonical"])
        out = out.drop(columns=["player_id_canonical"], errors="ignore")
    else:
        out = out.rename(columns={"player_id_canonical": "player_id"})
    return out.drop(columns=["_normalized_name", "normalized_name"], errors="ignore")


def source_priority(source_name: str) -> int:
    """Return a deterministic priority for source conflict resolution."""
    priorities = {
        "player_seasons": 100,
        "contracts": 80,
        "transactions": 70,
        "manual_candidates": 60,
        "manual": 90,
    }
    return priorities.get(source_name, 10)


def _first_not_null(values: pd.Series):
    clean = values.dropna()
    if clean.empty:
        return pd.NA
    return clean.iloc[0]


def _first_not_empty(values: pd.Series) -> str:
    for value in values:
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value)
    return ""

