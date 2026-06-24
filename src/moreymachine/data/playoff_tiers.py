"""Manual playoff outcome tiers for team-season training data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.data.team_lookup import TEAM_ID_TO_ABBR, TEAM_NAME_TO_ABBR
from moreymachine.utils.paths import (
    PLAYOFF_TIERS_PATH,
    TEAM_SEASONS_PATH,
    TEAM_SEASONS_WITH_TIERS_PATH,
)

# Re-exported for callers that imported these names from this module.
TEAM_SEASONS_BASIC_PATH = TEAM_SEASONS_PATH

PLAYOFF_TIER_DEFINITIONS = {
    0: "missed playoffs",
    1: "lost first round",
    2: "lost second round",
    3: "lost conference finals",
    4: "lost finals",
    5: "champion",
}
REQUIRED_TIER_COLUMNS = ("season", "team_abbr", "playoff_tier", "playoff_result")


@dataclass(frozen=True)
class PlayoffTierBuildResult:
    """Summary of a completed playoff tier build."""

    rows: int
    seasons: tuple[str, ...]
    output_path: Path


def load_playoff_tiers(path: str | Path = PLAYOFF_TIERS_PATH) -> pd.DataFrame:
    """Load and validate the manual playoff tier CSV."""
    tier_frame = pd.read_csv(path, dtype={"season": "string", "team_abbr": "string"})
    tier_frame.columns = [column.strip().lower() for column in tier_frame.columns]
    _validate_tier_columns(tier_frame)

    keep_columns = list(REQUIRED_TIER_COLUMNS)
    if "source_note" in tier_frame.columns:
        keep_columns.append("source_note")
    tier_frame = tier_frame.loc[:, keep_columns].copy()
    tier_frame["season"] = tier_frame["season"].str.strip()
    tier_frame["team_abbr"] = tier_frame["team_abbr"].str.strip().str.upper()
    tier_frame["playoff_result"] = (
        tier_frame["playoff_result"].astype("string").str.strip()
    )
    tier_frame["playoff_tier"] = pd.to_numeric(
        tier_frame["playoff_tier"],
        errors="coerce",
    ).astype("Int64")

    validate_playoff_tiers(tier_frame)
    return tier_frame


def validate_playoff_tiers(tier_frame: pd.DataFrame) -> None:
    """Validate playoff tier values and key uniqueness."""
    _validate_tier_columns(tier_frame)
    if tier_frame.empty:
        return

    null_columns = [
        column for column in REQUIRED_TIER_COLUMNS if tier_frame[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"Playoff tiers contain null values in: {null_columns}")

    invalid_tiers = sorted(
        set(tier_frame["playoff_tier"].astype(int)) - set(PLAYOFF_TIER_DEFINITIONS)
    )
    if invalid_tiers:
        raise ValueError(f"Invalid playoff_tier values: {invalid_tiers}")

    duplicates = tier_frame[tier_frame.duplicated(["season", "team_abbr"], keep=False)]
    if not duplicates.empty:
        duplicate_keys = _format_pairs(duplicates[["season", "team_abbr"]])
        raise ValueError(f"Duplicate playoff tier rows: {duplicate_keys}")


def validate_all_teams_have_tiers(
    team_seasons: pd.DataFrame,
    playoff_tiers: pd.DataFrame,
) -> None:
    """Validate each team-season has exactly one manual playoff tier row."""
    teams = add_team_abbr(team_seasons)
    validate_playoff_tiers(playoff_tiers)

    team_keys = _season_team_keys(teams)
    tier_keys = _season_team_keys(playoff_tiers)

    missing = team_keys - tier_keys
    if missing:
        raise ValueError(f"Missing playoff tiers: {_format_key_set(missing)}")

    unexpected = tier_keys - team_keys
    if unexpected:
        raise ValueError(f"Unexpected playoff tier rows: {_format_key_set(unexpected)}")


def add_team_abbr(team_seasons: pd.DataFrame) -> pd.DataFrame:
    """Return team seasons with a normalized team_abbr column."""
    teams = team_seasons.copy()
    if "season" not in teams.columns:
        raise ValueError("Team seasons data is missing required column: season")

    if "team_abbr" in teams.columns:
        teams["team_abbr"] = teams["team_abbr"].astype("string").str.strip().str.upper()
    elif "team_id" in teams.columns:
        team_ids = pd.to_numeric(teams["team_id"], errors="coerce").astype("Int64")
        teams["team_abbr"] = team_ids.map(TEAM_ID_TO_ABBR)
    elif "team_name" in teams.columns:
        team_names = teams["team_name"].astype("string").str.strip().str.lower()
        teams["team_abbr"] = team_names.map(TEAM_NAME_TO_ABBR)
    else:
        raise ValueError(
            "Team seasons data must include team_abbr, team_id, or team_name"
        )

    missing_abbr = teams[teams["team_abbr"].isna()]
    if not missing_abbr.empty:
        keys = _format_pairs(missing_abbr[["season"]].assign(team_abbr="<unknown>"))
        raise ValueError(f"Unable to resolve team abbreviations for: {keys}")

    teams["team_abbr"] = teams["team_abbr"].astype("string")
    return teams


def join_playoff_tiers(
    team_seasons: pd.DataFrame,
    playoff_tiers: pd.DataFrame,
) -> pd.DataFrame:
    """Join validated playoff tiers onto team-season data."""
    teams = add_team_abbr(team_seasons)
    validate_all_teams_have_tiers(teams, playoff_tiers)

    merged = teams.merge(
        playoff_tiers.loc[:, REQUIRED_TIER_COLUMNS],
        on=["season", "team_abbr"],
        how="left",
        validate="one_to_one",
    )
    if merged["playoff_tier"].isna().any():
        raise ValueError("Joined team seasons contain missing playoff tiers")
    merged["playoff_tier"] = merged["playoff_tier"].astype("int64")
    return merged


def build_team_seasons_with_tiers(
    *,
    team_seasons_path: str | Path = TEAM_SEASONS_BASIC_PATH,
    playoff_tiers_path: str | Path = PLAYOFF_TIERS_PATH,
    output_path: str | Path = TEAM_SEASONS_WITH_TIERS_PATH,
) -> PlayoffTierBuildResult:
    """Build the processed team-season table with playoff outcome tiers."""
    team_frame = pd.read_parquet(team_seasons_path)
    tier_frame = load_playoff_tiers(playoff_tiers_path)
    result = join_playoff_tiers(team_frame, tier_frame)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    seasons = tuple(sorted(result["season"].dropna().unique()))
    return PlayoffTierBuildResult(rows=len(result), seasons=seasons, output_path=output)


def _validate_tier_columns(tier_frame: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_TIER_COLUMNS) - set(tier_frame.columns))
    if missing:
        raise ValueError(f"Playoff tiers are missing required columns: {missing}")


def _season_team_keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    return {
        (str(row.season), str(row.team_abbr))
        for row in frame.loc[:, ["season", "team_abbr"]].drop_duplicates().itertuples()
    }


def _format_pairs(frame: pd.DataFrame) -> str:
    pairs = _season_team_keys(frame)
    return _format_key_set(pairs)


def _format_key_set(keys: set[tuple[str, str]]) -> str:
    return ", ".join(f"{season}/{team_abbr}" for season, team_abbr in sorted(keys))
