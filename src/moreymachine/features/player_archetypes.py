"""Cluster rotation players into basketball role archetypes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from moreymachine.utils.paths import (
    FEATURES_DATA_DIR,
    PROCESSED_DATA_DIR,
    REPORTS_DATA_DIR,
)

PLAYER_SEASONS_BASIC_PATH = PROCESSED_DATA_DIR / "player_seasons_basic.parquet"
PLAYER_ARCHETYPES_PATH = FEATURES_DATA_DIR / "player_archetypes.parquet"
PLAYER_ARCHETYPE_SUMMARY_PATH = REPORTS_DATA_DIR / "player_archetype_summary.csv"

IDENTITY_COLUMNS = (
    "season",
    "player_id",
    "player_name",
    "team_id",
    "team_abbreviation",
    "team_abbr",
    "position",
)
DEFAULT_MIN_MINUTES = 500.0
DEFAULT_K = 8
DEFAULT_PCA_COMPONENTS = 3
MIN_PCA_COMPONENTS = 2
MAX_PCA_COMPONENTS = 5

PLAYER_FEATURE_COLUMNS = (
    "age",
    "minutes",
    "usage_rate",
    "shooting_efficiency",
    "three_point_attempt_rate",
    "three_point_percentage",
    "assist_rate",
    "turnover_rate",
    "rebound_rate",
    "steal_rate",
    "block_rate",
    "position_guard",
    "position_wing",
    "position_big",
)


@dataclass(frozen=True)
class PlayerArchetypeBuildResult:
    """Summary of a completed player archetype build."""

    rows: int
    clusters: int
    feature_columns: tuple[str, ...]
    output_path: Path
    summary_path: Path


def build_player_archetypes(
    *,
    input_path: str | Path = PLAYER_SEASONS_BASIC_PATH,
    output_path: str | Path = PLAYER_ARCHETYPES_PATH,
    summary_path: str | Path = PLAYER_ARCHETYPE_SUMMARY_PATH,
    min_minutes: float = DEFAULT_MIN_MINUTES,
    k: int = DEFAULT_K,
    pca_components: int = DEFAULT_PCA_COMPONENTS,
    random_state: int = 42,
) -> PlayerArchetypeBuildResult:
    """Cluster player seasons and save assignments plus summary."""
    player_seasons = pd.read_parquet(input_path)
    assignments, summary = create_player_archetypes(
        player_seasons,
        min_minutes=min_minutes,
        k=k,
        pca_components=pca_components,
        random_state=random_state,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    assignments.to_parquet(output, index=False)

    summary_output = Path(summary_path)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_output, index=False)

    return PlayerArchetypeBuildResult(
        rows=len(assignments),
        clusters=summary["cluster_id"].nunique(),
        feature_columns=tuple(assignments.attrs.get("cluster_feature_columns", ())),
        output_path=output,
        summary_path=summary_output,
    )


def create_player_archetypes(
    player_seasons: pd.DataFrame,
    *,
    min_minutes: float = DEFAULT_MIN_MINUTES,
    k: int = DEFAULT_K,
    pca_components: int = DEFAULT_PCA_COMPONENTS,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return player archetype assignments and a cluster summary."""
    rotation_players = filter_rotation_players(player_seasons, min_minutes=min_minutes)
    feature_frame = select_player_features(rotation_players)
    _validate_clustering_request(feature_frame, k=k, pca_components=pca_components)

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    imputed = imputer.fit_transform(feature_frame)
    scaled = scaler.fit_transform(imputed)

    component_count = _effective_pca_components(
        requested_components=pca_components,
        rows=feature_frame.shape[0],
        features=feature_frame.shape[1],
    )
    pca = PCA(n_components=component_count, random_state=random_state)
    pca_scores = pca.fit_transform(scaled)

    kmeans = KMeans(n_clusters=k, n_init=20, random_state=random_state)
    clusters = kmeans.fit_predict(pca_scores)
    assignments = _assignment_frame(
        rotation_players,
        feature_frame,
        scaled,
        pca_scores,
        clusters,
    )
    summary = summarize_archetypes(assignments, feature_frame.columns)
    assignments = assignments.merge(
        summary.loc[:, ["cluster_id", "archetype_name"]],
        on="cluster_id",
        how="left",
        validate="many_to_one",
    )
    assignments.attrs["cluster_feature_columns"] = tuple(feature_frame.columns)
    return assignments, summary


def filter_rotation_players(
    player_seasons: pd.DataFrame,
    *,
    min_minutes: float = DEFAULT_MIN_MINUTES,
) -> pd.DataFrame:
    """Return players at or above the minutes threshold."""
    minutes = _minutes(player_seasons)
    if minutes.notna().sum() == 0:
        raise ValueError("Player seasons data is missing a usable minutes column")
    result = player_seasons.loc[minutes >= min_minutes].copy()
    result["minutes"] = minutes.loc[result.index].astype("float64")
    if result.empty:
        raise ValueError("No players meet the configured minutes threshold")
    return result


def select_player_features(player_seasons: pd.DataFrame) -> pd.DataFrame:
    """Select and derive numeric player role features."""
    features = pd.DataFrame(index=player_seasons.index)
    features["age"] = _direct_feature(player_seasons, ("age",))
    features["minutes"] = _minutes(player_seasons)
    features["usage_rate"] = _direct_feature(
        player_seasons,
        ("usage_rate", "usage_percentage", "usg_pct", "usg"),
    )
    features["shooting_efficiency"] = _shooting_efficiency(player_seasons)
    features["three_point_attempt_rate"] = _three_point_attempt_rate(player_seasons)
    features["three_point_percentage"] = _direct_feature(
        player_seasons,
        ("three_point_percentage", "three_point_pct", "fg3_pct"),
    )
    features["assist_rate"] = _assist_rate(player_seasons)
    features["turnover_rate"] = _turnover_rate(player_seasons)
    features["rebound_rate"] = _rebound_rate(player_seasons)
    features["steal_rate"] = _event_rate(
        player_seasons, ("steal_rate", "stl_rate"), ("stl", "steals")
    )
    features["block_rate"] = _event_rate(
        player_seasons, ("block_rate", "blk_rate"), ("blk", "blocks")
    )

    position_features = _position_features(player_seasons)
    if not position_features.empty:
        features = pd.concat([features, position_features], axis=1)

    usable_columns = [
        column for column in features.columns if features[column].notna().any()
    ]
    return features.loc[:, usable_columns].astype("float64")


def summarize_archetypes(
    assignments: pd.DataFrame,
    feature_columns: pd.Index | list[str],
) -> pd.DataFrame:
    """Summarize player archetype clusters using feature z-score profiles."""
    rows = []
    for cluster_id, cluster_frame in assignments.groupby("cluster_id"):
        means = cluster_frame.loc[:, _zscore_columns(feature_columns)].mean()
        drivers = _cluster_drivers(means)
        rows.append(
            {
                "cluster_id": int(cluster_id),
                "archetype_name": suggest_archetype_name(means),
                "player_season_count": int(len(cluster_frame)),
                "strongest_positive_features": "; ".join(
                    driver for driver, _ in drivers["positive"]
                ),
                "strongest_negative_features": "; ".join(
                    driver for driver, _ in drivers["negative"]
                ),
                "feature_profile": _feature_profile(means),
            }
        )
    return pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)


def suggest_archetype_name(zscores: pd.Series) -> str:
    """Suggest a basketball role name from feature z-scores."""
    values = zscores.rename(lambda column: column.removesuffix("_zscore"))

    if _value(values, "usage_rate") >= 0.75 and _value(values, "assist_rate") >= 0.35:
        return "High-Usage Creator"
    if _value(values, "block_rate") >= 0.75 and _value(values, "rebound_rate") >= 0.35:
        return "Rim Protector"
    if (
        _value(values, "position_big") >= 0.35
        and _value(values, "three_point_attempt_rate") >= 0.45
    ):
        return "Stretch Big"
    if (
        _value(values, "position_big") >= 0.35
        and _value(values, "rebound_rate") >= 0.65
    ):
        return "Rebounding Big"
    if (
        _value(values, "position_wing") >= 0.25
        and _value(values, "three_point_attempt_rate") >= 0.35
        and (
            _value(values, "steal_rate") >= 0.25 or _value(values, "block_rate") >= 0.25
        )
    ):
        return "3-and-D Wing"
    if (
        _value(values, "usage_rate") <= -0.45
        and _value(values, "three_point_attempt_rate") >= 0.45
    ):
        return "Low-Usage Spacer"
    if (
        _value(values, "position_guard") >= 0.25
        and _value(values, "assist_rate") >= 0.45
        and _value(values, "usage_rate") <= 0.40
    ):
        return "Connector Guard"
    if (
        _value(values, "position_guard") >= 0.25
        and _value(values, "usage_rate") >= 0.45
        and _value(values, "shooting_efficiency") >= 0.20
    ):
        return "Scoring Guard"
    if _value(values, "steal_rate") >= 0.55 or _value(values, "block_rate") >= 0.55:
        return "Defensive Specialist"

    top_feature = values.abs().sort_values(ascending=False).index[0]
    return _fallback_archetype_name(top_feature)


def _assignment_frame(
    player_seasons: pd.DataFrame,
    feature_frame: pd.DataFrame,
    scaled: np.ndarray,
    pca_scores: np.ndarray,
    clusters: np.ndarray,
) -> pd.DataFrame:
    identity_columns = [
        column for column in IDENTITY_COLUMNS if column in player_seasons.columns
    ]
    assignments = player_seasons.loc[:, identity_columns].copy()
    if "minutes" not in assignments.columns:
        assignments["minutes"] = _minutes(player_seasons)
    assignments["cluster_id"] = clusters.astype(int)
    assignments["cluster_distance"] = _cluster_distance(pca_scores, clusters)
    for column_index in range(pca_scores.shape[1]):
        assignments[f"pca_{column_index + 1}"] = pca_scores[:, column_index]
    for column_index, column in enumerate(feature_frame.columns):
        assignments[f"{column}_zscore"] = scaled[:, column_index]
    return assignments


def _validate_clustering_request(
    feature_frame: pd.DataFrame,
    *,
    k: int,
    pca_components: int,
) -> None:
    if feature_frame.shape[1] < 2:
        raise ValueError("At least two usable player clustering features are required")
    if k < 2:
        raise ValueError("k must be at least 2")
    if k > len(feature_frame):
        raise ValueError("k cannot exceed the number of rotation player rows")
    if pca_components < MIN_PCA_COMPONENTS or pca_components > MAX_PCA_COMPONENTS:
        raise ValueError("pca_components must be between 2 and 5")


def _direct_feature(
    player_seasons: pd.DataFrame, aliases: tuple[str, ...]
) -> pd.Series:
    normalized_columns = {column.lower(): column for column in player_seasons.columns}
    for alias in aliases:
        source_column = normalized_columns.get(alias)
        if source_column is None:
            continue
        values = pd.to_numeric(player_seasons[source_column], errors="coerce")
        if values.notna().any():
            return values.astype("float64")
    return _missing_float_series(player_seasons.index)


def _minutes(player_seasons: pd.DataFrame) -> pd.Series:
    return _direct_feature(player_seasons, ("minutes", "min", "mp"))


def _shooting_efficiency(player_seasons: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        player_seasons,
        ("true_shooting_percentage", "true_shooting", "ts_pct", "ts"),
    )
    if direct.notna().any():
        return direct

    points = _direct_feature(player_seasons, ("pts", "points"))
    fga = _direct_feature(player_seasons, ("fga", "field_goals_attempted"))
    fta = _direct_feature(player_seasons, ("fta", "free_throws_attempted"))
    true_shooting = _safe_divide(points, 2 * (fga + (0.44 * fta)))
    if true_shooting.notna().any():
        return true_shooting

    fgm = _direct_feature(player_seasons, ("fgm", "field_goals_made"))
    fg3m = _direct_feature(player_seasons, ("fg3m", "three_pointers_made"))
    efg = _safe_divide(fgm + (0.5 * fg3m), fga)
    if efg.notna().any():
        return efg

    return _direct_feature(player_seasons, ("fg_pct", "field_goal_percentage"))


def _three_point_attempt_rate(player_seasons: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        player_seasons,
        ("three_point_attempt_rate", "three_point_rate", "fg3a_rate"),
    )
    if direct.notna().any():
        return direct
    fg3a = _direct_feature(player_seasons, ("fg3a", "three_pointers_attempted"))
    fga = _direct_feature(player_seasons, ("fga", "field_goals_attempted"))
    return _safe_divide(fg3a, fga)


def _assist_rate(player_seasons: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        player_seasons, ("assist_rate", "assist_percentage", "ast_pct")
    )
    if direct.notna().any():
        return direct
    assists = _direct_feature(player_seasons, ("ast", "assists"))
    return _safe_divide(assists, _minutes(player_seasons))


def _turnover_rate(player_seasons: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        player_seasons,
        ("turnover_rate", "turnover_percentage", "tov_pct"),
    )
    if direct.notna().any():
        return direct
    turnovers = _direct_feature(player_seasons, ("tov", "turnovers"))
    fga = _direct_feature(player_seasons, ("fga", "field_goals_attempted"))
    fta = _direct_feature(player_seasons, ("fta", "free_throws_attempted"))
    denominator = fga + (0.44 * fta) + turnovers
    turnover_rate = _safe_divide(turnovers, denominator)
    if turnover_rate.notna().any():
        return turnover_rate
    return _safe_divide(turnovers, _minutes(player_seasons))


def _rebound_rate(player_seasons: pd.DataFrame) -> pd.Series:
    direct = _direct_feature(
        player_seasons,
        ("rebound_rate", "rebound_percentage", "reb_pct", "trb_pct"),
    )
    if direct.notna().any():
        return direct
    rebounds = _direct_feature(player_seasons, ("reb", "trb", "rebounds"))
    return _safe_divide(rebounds, _minutes(player_seasons))


def _event_rate(
    player_seasons: pd.DataFrame,
    direct_aliases: tuple[str, ...],
    count_aliases: tuple[str, ...],
) -> pd.Series:
    direct = _direct_feature(player_seasons, direct_aliases)
    if direct.notna().any():
        return direct
    counts = _direct_feature(player_seasons, count_aliases)
    return _safe_divide(counts, _minutes(player_seasons))


def _position_features(player_seasons: pd.DataFrame) -> pd.DataFrame:
    normalized_columns = {column.lower(): column for column in player_seasons.columns}
    position_column = None
    for alias in ("position", "player_position", "player_position_abbreviation", "pos"):
        if alias in normalized_columns:
            position_column = normalized_columns[alias]
            break
    if position_column is None:
        return pd.DataFrame(index=player_seasons.index)

    buckets = player_seasons[position_column].map(_position_bucket)
    features = pd.DataFrame(index=player_seasons.index)
    for bucket in ("guard", "wing", "big"):
        values = buckets.map(
            lambda bucket_set, bucket=bucket: float(bucket in bucket_set)
        )
        if values.sum() > 0:
            features[f"position_{bucket}"] = values
    return features


def _position_bucket(value: Any) -> set[str]:
    text = str(value).strip().lower().replace("-", "").replace("/", "")
    if text in {"", "nan", "none"}:
        return set()

    buckets: set[str] = set()
    if "pg" in text or "sg" in text or text == "g":
        buckets.add("guard")
    if "sf" in text or text in {"f", "gf", "fg"}:
        buckets.add("wing")
    if "pf" in text or "c" in text or text in {"fc", "cf"}:
        buckets.add("big")
    if not buckets:
        if "guard" in text:
            buckets.add("guard")
        if "wing" in text or "forward" in text:
            buckets.add("wing")
        if "center" in text or "big" in text:
            buckets.add("big")
    return buckets


def _effective_pca_components(
    *,
    requested_components: int,
    rows: int,
    features: int,
) -> int:
    return min(requested_components, rows, features)


def _cluster_distance(pca_scores: np.ndarray, clusters: np.ndarray) -> np.ndarray:
    distances = np.zeros(len(clusters), dtype=float)
    for cluster_id in np.unique(clusters):
        mask = clusters == cluster_id
        centroid = pca_scores[mask].mean(axis=0)
        distances[mask] = np.linalg.norm(pca_scores[mask] - centroid, axis=1)
    return distances


def _zscore_columns(feature_columns: pd.Index | list[str]) -> list[str]:
    return [f"{column}_zscore" for column in feature_columns]


def _cluster_drivers(
    zscores: pd.Series, *, limit: int = 3
) -> dict[str, list[tuple[str, float]]]:
    renamed = zscores.rename(lambda column: column.removesuffix("_zscore"))
    positive = [
        (str(feature), float(value))
        for feature, value in renamed.sort_values(ascending=False).head(limit).items()
    ]
    negative = [
        (str(feature), float(value))
        for feature, value in renamed.sort_values(ascending=True).head(limit).items()
    ]
    return {"positive": positive, "negative": negative}


def _feature_profile(zscores: pd.Series) -> str:
    renamed = zscores.rename(lambda column: column.removesuffix("_zscore"))
    ordered = renamed.reindex(renamed.abs().sort_values(ascending=False).index)
    return "; ".join(
        f"{feature}={value:.2f}" for feature, value in ordered.head(6).items()
    )


def _value(values: pd.Series, feature: str) -> float:
    if feature not in values.index:
        return 0.0
    value = values.loc[feature]
    if pd.isna(value):
        return 0.0
    return float(value)


def _fallback_archetype_name(feature: Any) -> str:
    feature_name = str(feature)
    if "usage" in feature_name:
        return "Scoring Guard"
    if "assist" in feature_name:
        return "Connector Guard"
    if "rebound" in feature_name:
        return "Rebounding Big"
    if "block" in feature_name or "steal" in feature_name:
        return "Defensive Specialist"
    if "three_point" in feature_name:
        return "Low-Usage Spacer"
    return "Balanced Role Player"


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean_denominator = denominator.mask(denominator == 0)
    return numerator / clean_denominator


def _missing_float_series(index: pd.Index) -> pd.Series:
    return pd.Series(pd.NA, index=index, dtype="Float64")
