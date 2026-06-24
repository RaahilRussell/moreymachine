"""Team-season fingerprint feature engineering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.data.playoff_tiers import TEAM_SEASONS_WITH_TIERS_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR

TEAM_FINGERPRINTS_PATH = FEATURES_DATA_DIR / "team_fingerprints.parquet"

IDENTITY_COLUMNS = ("season", "team_abbr", "team_id", "team_name")
FINGERPRINT_FEATURE_COLUMNS = (
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "pace",
    "efg_percentage",
    "turnover_percentage",
    "offensive_rebounding_percentage",
    "defensive_rebounding_percentage",
    "free_throw_rate",
    "three_point_attempt_rate",
    "three_point_percentage",
    "estimated_shooting_pressure",
    "estimated_possession_control",
    "estimated_two_way_balance",
)
LABEL_COLUMNS = (
    "playoff_tier",
    "quality_tier",
    "deep_playoff",
    "finals_team",
    "champion",
)


@dataclass(frozen=True)
class TeamFingerprintBuildResult:
    """Summary of a completed team fingerprint build."""

    rows: int
    seasons: tuple[str, ...]
    output_path: Path


def create_team_fingerprints(team_seasons: pd.DataFrame) -> pd.DataFrame:
    """Create team-season fingerprint features and labels."""
    if "season" not in _normalized_columns(team_seasons):
        raise ValueError("Team seasons data is missing required column: season")

    source = team_seasons.copy()
    fingerprints = _identity_frame(source)

    fingerprints["offensive_rating"] = _offensive_rating(source)
    fingerprints["defensive_rating"] = _direct_feature(
        source,
        ("defensive_rating", "def_rating", "def_rtg", "drtg"),
    )
    fingerprints["net_rating"] = _net_rating(source, fingerprints)
    fingerprints["pace"] = _direct_feature(source, ("pace", "pace_per_48"))
    fingerprints["efg_percentage"] = _efg_percentage(source)
    fingerprints["turnover_percentage"] = _turnover_percentage(source)
    fingerprints["offensive_rebounding_percentage"] = _direct_feature(
        source,
        ("offensive_rebounding_percentage", "offensive_rebound_pct", "oreb_pct"),
    )
    fingerprints["defensive_rebounding_percentage"] = _direct_feature(
        source,
        ("defensive_rebounding_percentage", "defensive_rebound_pct", "dreb_pct"),
    )
    fingerprints["free_throw_rate"] = _free_throw_rate(source)
    fingerprints["three_point_attempt_rate"] = _three_point_attempt_rate(source)
    fingerprints["three_point_percentage"] = _direct_feature(
        source,
        ("three_point_percentage", "three_point_pct", "three_p_pct", "fg3_pct"),
    )

    fingerprints["estimated_shooting_pressure"] = _estimated_shooting_pressure(
        fingerprints
    )
    fingerprints["estimated_possession_control"] = _estimated_possession_control(
        fingerprints
    )
    fingerprints["estimated_two_way_balance"] = _estimated_two_way_balance(fingerprints)

    _add_label_columns(source, fingerprints)
    return fingerprints.loc[:, _output_columns(fingerprints)]


def build_team_fingerprints(
    *,
    input_path: str | Path = TEAM_SEASONS_WITH_TIERS_PATH,
    output_path: str | Path = TEAM_FINGERPRINTS_PATH,
) -> TeamFingerprintBuildResult:
    """Build team fingerprint features and save them as Parquet."""
    team_frame = pd.read_parquet(input_path)
    fingerprints = create_team_fingerprints(team_frame)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fingerprints.to_parquet(output, index=False)
    seasons = tuple(sorted(fingerprints["season"].dropna().unique()))
    return TeamFingerprintBuildResult(
        rows=len(fingerprints),
        seasons=seasons,
        output_path=output,
    )


def _identity_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = _normalized_columns(frame)
    result = pd.DataFrame(index=frame.index)
    for column in IDENTITY_COLUMNS:
        source_column = normalized.get(column)
        if source_column is not None:
            result[column] = frame[source_column]
    return result


def _offensive_rating(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        frame,
        ("offensive_rating", "off_rating", "off_rtg", "ortg"),
    )
    if direct.notna().any():
        return direct

    points = _direct_feature(frame, ("pts", "points"))
    possessions = _possessions(frame)
    return _safe_divide(points * 100, possessions)


def _net_rating(frame: pd.DataFrame, fingerprints: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(frame, ("net_rating", "net_rtg"))
    if direct.notna().any():
        return direct

    offensive = fingerprints["offensive_rating"]
    defensive = fingerprints["defensive_rating"]
    return offensive - defensive


def _efg_percentage(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        frame,
        ("efg_percentage", "effective_fg_pct", "efg_pct", "e_fg_pct"),
    )
    if direct.notna().any():
        return direct

    fgm = _direct_feature(frame, ("fgm", "field_goals_made"))
    fg3m = _direct_feature(frame, ("fg3m", "three_pointers_made"))
    fga = _direct_feature(frame, ("fga", "field_goals_attempted"))
    return _safe_divide(fgm + (0.5 * fg3m), fga)


def _turnover_percentage(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(frame, ("turnover_percentage", "turnover_pct", "tov_pct"))
    if direct.notna().any():
        return direct

    turnovers = _direct_feature(frame, ("tov", "turnovers"))
    fga = _direct_feature(frame, ("fga", "field_goals_attempted"))
    fta = _direct_feature(frame, ("fta", "free_throws_attempted"))
    denominator = fga + (0.44 * fta) + turnovers
    return _safe_divide(turnovers, denominator)


def _free_throw_rate(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        frame,
        ("free_throw_rate", "ft_rate", "fta_rate", "ftr"),
    )
    if direct.notna().any():
        return direct

    free_throw_attempts = _direct_feature(frame, ("fta", "free_throws_attempted"))
    field_goal_attempts = _direct_feature(frame, ("fga", "field_goals_attempted"))
    return _safe_divide(free_throw_attempts, field_goal_attempts)


def _three_point_attempt_rate(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        frame,
        (
            "three_point_attempt_rate",
            "three_pa_rate",
            "three_point_rate",
            "fg3a_rate",
            "threepar",
        ),
    )
    if direct.notna().any():
        return direct

    three_point_attempts = _direct_feature(frame, ("fg3a", "three_pointers_attempted"))
    field_goal_attempts = _direct_feature(frame, ("fga", "field_goals_attempted"))
    return _safe_divide(three_point_attempts, field_goal_attempts)


def _estimated_shooting_pressure(fingerprints: pd.DataFrame) -> pd.Series:
    components = (
        _season_percentile(fingerprints, "efg_percentage"),
        _season_percentile(fingerprints, "three_point_attempt_rate"),
        _season_percentile(fingerprints, "three_point_percentage"),
        _season_percentile(fingerprints, "free_throw_rate"),
    )
    return _mean_available(components, index=fingerprints.index)


def _estimated_possession_control(fingerprints: pd.DataFrame) -> pd.Series:
    components = (
        _season_percentile(fingerprints, "turnover_percentage", higher_is_better=False),
        _season_percentile(fingerprints, "offensive_rebounding_percentage"),
        _season_percentile(fingerprints, "defensive_rebounding_percentage"),
    )
    return _mean_available(components, index=fingerprints.index)


def _estimated_two_way_balance(fingerprints: pd.DataFrame) -> pd.Series:
    offensive_strength = _season_percentile(fingerprints, "offensive_rating")
    defensive_strength = _season_percentile(
        fingerprints,
        "defensive_rating",
        higher_is_better=False,
    )
    net_strength = _season_percentile(fingerprints, "net_rating")
    balance = 1 - (offensive_strength - defensive_strength).abs()
    components = (net_strength, offensive_strength, defensive_strength, balance)
    return _mean_available(components, index=fingerprints.index)


def _add_label_columns(source: pd.DataFrame, fingerprints: pd.DataFrame) -> None:
    playoff_tier = _label_integer(source, "playoff_tier")
    quality_tier = _label_integer(source, "quality_tier")
    fingerprints["playoff_tier"] = playoff_tier
    fingerprints["quality_tier"] = quality_tier
    fingerprints["deep_playoff"] = _nullable_bool(playoff_tier.ge(3), playoff_tier)
    fingerprints["finals_team"] = _nullable_bool(playoff_tier.ge(4), playoff_tier)
    fingerprints["champion"] = _nullable_bool(playoff_tier.eq(5), playoff_tier)


def _direct_feature(frame: pd.DataFrame, aliases: tuple[str, ...]) -> pd.Series:
    normalized = _normalized_columns(frame)
    for alias in aliases:
        source_column = normalized.get(alias)
        if source_column is None:
            continue
        values = pd.to_numeric(frame[source_column], errors="coerce")
        if values.notna().any():
            return values.astype("float64")
    return _missing_float_series(frame.index)


def _label_integer(frame: pd.DataFrame, column: str) -> pd.Series:
    normalized = _normalized_columns(frame)
    source_column = normalized.get(column)
    if source_column is None:
        return pd.Series(pd.NA, index=frame.index, dtype="Int64")
    return pd.to_numeric(frame[source_column], errors="coerce").astype("Int64")


def _possessions(frame: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(frame, ("possessions", "poss"))
    if direct.notna().any():
        return direct

    fga = _direct_feature(frame, ("fga", "field_goals_attempted"))
    fta = _direct_feature(frame, ("fta", "free_throws_attempted"))
    offensive_rebounds = _direct_feature(frame, ("oreb", "offensive_rebounds"))
    turnovers = _direct_feature(frame, ("tov", "turnovers"))
    return fga + (0.44 * fta) - offensive_rebounds + turnovers


def _season_percentile(
    frame: pd.DataFrame,
    column: str,
    *,
    higher_is_better: bool = True,
) -> pd.Series:
    if column not in frame.columns:
        return _missing_float_series(frame.index)
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.notna().sum() == 0:
        return _missing_float_series(frame.index)
    return values.groupby(frame["season"]).rank(
        method="average",
        pct=True,
        ascending=higher_is_better,
    )


def _mean_available(components: tuple[pd.Series, ...], *, index: pd.Index) -> pd.Series:
    if not components:
        return _missing_float_series(index)
    component_frame = pd.concat(components, axis=1)
    return component_frame.mean(axis=1, skipna=True)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean_denominator = denominator.mask(denominator == 0)
    return numerator / clean_denominator


def _nullable_bool(values: pd.Series, source: pd.Series) -> pd.Series:
    result = values.astype("boolean")
    return result.mask(source.isna(), pd.NA)


def _output_columns(frame: pd.DataFrame) -> list[str]:
    identity_columns = [
        column for column in IDENTITY_COLUMNS if column in frame.columns
    ]
    return [*identity_columns, *FINGERPRINT_FEATURE_COLUMNS, *LABEL_COLUMNS]


def _normalized_columns(frame: pd.DataFrame) -> dict[str, str]:
    return {column.lower(): column for column in frame.columns}


def _missing_float_series(index: pd.Index) -> pd.Series:
    return pd.Series(pd.NA, index=index, dtype="Float64")
