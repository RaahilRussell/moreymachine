"""Regular-season quality tiers for team-season data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.data.playoff_tiers import TEAM_SEASONS_WITH_TIERS_PATH

QUALITY_TIER_DEFINITIONS = {
    0: "bottom 10 team",
    1: "below average",
    2: "average / play-in level",
    3: "playoff-level",
    4: "top-10 net rating",
    5: "top-5 net rating / elite",
}
QUALITY_COLUMNS = (
    "quality_tier",
    "quality_metric",
    "quality_metric_source",
    "quality_rank",
    "quality_percentile",
    "quality_tier_reason",
)


@dataclass(frozen=True)
class QualityTierBuildResult:
    """Summary of a completed regular-season quality tier build."""

    rows: int
    seasons: tuple[str, ...]
    output_path: Path


def add_quality_tiers(team_seasons: pd.DataFrame) -> pd.DataFrame:
    """Add season-relative regular-season quality tiers to team seasons."""
    if "season" not in team_seasons.columns:
        raise ValueError("Team seasons data is missing required column: season")
    if team_seasons.empty:
        return _empty_with_quality_columns(team_seasons)

    result = team_seasons.copy()
    metric, source = _regular_season_strength_metric(result)
    if metric.isna().any():
        missing_rows = result.loc[metric.isna(), ["season"]]
        raise ValueError(
            "Quality metric contains missing values for: "
            f"{_format_missing_seasons(missing_rows)}"
        )

    result["quality_metric"] = metric.astype(float)
    result["quality_metric_source"] = source
    result["quality_rank"] = (
        result.groupby("season")["quality_metric"]
        .rank(method="min", ascending=False)
        .astype("int64")
    )
    result["quality_percentile"] = result.groupby("season")["quality_metric"].rank(
        method="max", pct=True, ascending=True
    )
    result["quality_tier"] = result["quality_percentile"].map(_tier_from_percentile)
    result["quality_tier"] = result["quality_tier"].astype("int64")
    result["quality_tier_reason"] = result.apply(_quality_tier_reason, axis=1)

    return result


def build_quality_tiers(
    *,
    input_path: str | Path = TEAM_SEASONS_WITH_TIERS_PATH,
    output_path: str | Path = TEAM_SEASONS_WITH_TIERS_PATH,
) -> QualityTierBuildResult:
    """Build quality tiers and save them into team_seasons_with_tiers.parquet."""
    team_frame = pd.read_parquet(input_path)
    result = add_quality_tiers(team_frame)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    seasons = tuple(sorted(result["season"].dropna().unique()))
    return QualityTierBuildResult(rows=len(result), seasons=seasons, output_path=output)


def _regular_season_strength_metric(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    net_rating_column = _first_available_column(frame, ("net_rating", "net_rtg"))
    if net_rating_column is not None:
        return _numeric(frame[net_rating_column]), net_rating_column

    offensive_column = _first_available_column(
        frame,
        ("offensive_rating", "off_rating", "off_rtg"),
    )
    defensive_column = _first_available_column(
        frame,
        ("defensive_rating", "def_rating", "def_rtg"),
    )
    if offensive_column is not None and defensive_column is not None:
        metric = _numeric(frame[offensive_column]) - _numeric(frame[defensive_column])
        return metric, f"{offensive_column}_minus_{defensive_column}"

    point_diff_column = _first_available_column(
        frame,
        ("point_differential", "point_diff", "plus_minus", "net_points"),
    )
    if point_diff_column is not None:
        metric = _numeric(frame[point_diff_column])
        games_column = _first_available_column(frame, ("games", "gp"))
        if games_column is not None:
            games = _numeric(frame[games_column]).replace(0, pd.NA)
            return metric / games, f"{point_diff_column}_per_game"
        return metric, point_diff_column

    win_pct_column = _first_available_column(frame, ("win_pct", "w_pct"))
    if win_pct_column is not None:
        return _numeric(frame[win_pct_column]), win_pct_column

    wins_column = _first_available_column(frame, ("wins", "w"))
    if wins_column is not None:
        return _numeric(frame[wins_column]), wins_column

    raise ValueError(
        "Team seasons data needs one regular-season strength column: "
        "net_rating, offensive/defensive ratings, point differential, or wins"
    )


def _first_available_column(
    frame: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str | None:
    normalized_columns = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        column = normalized_columns.get(candidate)
        if column is not None and frame[column].notna().any():
            return column
    return None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _tier_from_percentile(percentile: float) -> int:
    if percentile > 25 / 30:
        return 5
    if percentile > 20 / 30:
        return 4
    if percentile > 17 / 30:
        return 3
    if percentile > 14 / 30:
        return 2
    if percentile > 10 / 30:
        return 1
    return 0


def _quality_tier_reason(row: pd.Series) -> str:
    tier_label = QUALITY_TIER_DEFINITIONS[int(row["quality_tier"])]
    percentile = float(row["quality_percentile"])
    rank = int(row["quality_rank"])
    return (
        f"{tier_label}; {row['quality_metric_source']} rank {rank} "
        f"with season percentile {percentile:.3f}"
    )


def _empty_with_quality_columns(team_seasons: pd.DataFrame) -> pd.DataFrame:
    result = team_seasons.copy()
    for column in QUALITY_COLUMNS:
        result[column] = pd.Series(dtype="object")
    return result


def _format_missing_seasons(frame: pd.DataFrame) -> str:
    seasons = sorted(str(season) for season in frame["season"].dropna().unique())
    return ", ".join(seasons)
