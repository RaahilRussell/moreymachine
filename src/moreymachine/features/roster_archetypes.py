"""Cluster team-seasons into roster construction archetypes."""

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

from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR, REPORTS_DATA_DIR

TEAM_ROSTER_ARCHETYPES_PATH = FEATURES_DATA_DIR / "team_roster_archetypes.parquet"
ROSTER_ARCHETYPE_SUMMARY_PATH = REPORTS_DATA_DIR / "roster_archetype_summary.csv"

IDENTITY_COLUMNS = ("season", "team_abbr", "team_id", "team_name")
DEFAULT_K = 5
DEFAULT_PCA_COMPONENTS = 3
MIN_PCA_COMPONENTS = 2
MAX_PCA_COMPONENTS = 5

CLUSTER_FEATURE_ALIASES = {
    "net_rating": ("net_rating", "net_rtg"),
    "pace": ("pace", "pace_per_48"),
    "three_point_attempt_rate": (
        "three_point_attempt_rate",
        "three_point_rate",
        "fg3a_rate",
    ),
    "three_point_percentage": (
        "three_point_percentage",
        "three_point_pct",
        "fg3_pct",
    ),
    "assist_rate": ("assist_rate", "assist_percentage", "ast_pct", "ast_ratio"),
    "turnover_rate": ("turnover_rate", "turnover_percentage", "tov_pct"),
    "offensive_rebounding_percentage": (
        "offensive_rebounding_percentage",
        "offensive_rebound_pct",
        "oreb_pct",
    ),
    "defensive_rebounding_percentage": (
        "defensive_rebounding_percentage",
        "defensive_rebound_pct",
        "dreb_pct",
    ),
    "defensive_rating": ("defensive_rating", "def_rating", "def_rtg", "drtg"),
    "free_throw_rate": ("free_throw_rate", "ft_rate", "ftr"),
    "top_usage_concentration": (
        "top_usage_concentration",
        "usage_concentration",
        "top_usage_pct",
    ),
}


@dataclass(frozen=True)
class RosterArchetypeBuildResult:
    """Summary of a completed roster archetype build."""

    rows: int
    clusters: int
    feature_columns: tuple[str, ...]
    output_path: Path
    summary_path: Path


def build_roster_archetypes(
    *,
    input_path: str | Path = TEAM_FINGERPRINTS_PATH,
    output_path: str | Path = TEAM_ROSTER_ARCHETYPES_PATH,
    summary_path: str | Path = ROSTER_ARCHETYPE_SUMMARY_PATH,
    k: int = DEFAULT_K,
    pca_components: int = DEFAULT_PCA_COMPONENTS,
    random_state: int = 42,
) -> RosterArchetypeBuildResult:
    """Cluster team fingerprints and save assignments plus summary."""
    fingerprints = pd.read_parquet(input_path)
    assignments, summary = create_roster_archetypes(
        fingerprints,
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

    return RosterArchetypeBuildResult(
        rows=len(assignments),
        clusters=summary["cluster_id"].nunique(),
        feature_columns=tuple(
            column for column in assignments.attrs.get("cluster_feature_columns", ())
        ),
        output_path=output,
        summary_path=summary_output,
    )


def create_roster_archetypes(
    team_fingerprints: pd.DataFrame,
    *,
    k: int = DEFAULT_K,
    pca_components: int = DEFAULT_PCA_COMPONENTS,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return roster archetype assignments and a cluster summary."""
    feature_frame = select_cluster_features(team_fingerprints)
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
        team_fingerprints,
        feature_frame,
        scaled,
        pca_scores,
        clusters,
    )
    summary = summarize_archetypes(assignments, feature_frame.columns)
    assignments = assignments.merge(
        summary.loc[:, ["cluster_id", "cluster_name"]],
        on="cluster_id",
        how="left",
        validate="many_to_one",
    )
    assignments.attrs["cluster_feature_columns"] = tuple(feature_frame.columns)
    return assignments, summary


def select_cluster_features(team_fingerprints: pd.DataFrame) -> pd.DataFrame:
    """Select available numeric roster construction features."""
    normalized_columns = {
        column.lower(): column for column in team_fingerprints.columns
    }
    features = pd.DataFrame(index=team_fingerprints.index)
    for canonical_name, aliases in CLUSTER_FEATURE_ALIASES.items():
        source_column = _first_available_column(
            team_fingerprints,
            normalized_columns,
            aliases,
        )
        if source_column is None:
            continue
        values = pd.to_numeric(team_fingerprints[source_column], errors="coerce")
        if values.notna().any():
            features[canonical_name] = values.astype("float64")
    return features


def summarize_archetypes(
    assignments: pd.DataFrame,
    feature_columns: pd.Index | list[str],
) -> pd.DataFrame:
    """Summarize clusters using feature z-score profiles."""
    rows = []
    for cluster_id, cluster_frame in assignments.groupby("cluster_id"):
        means = cluster_frame.loc[:, _zscore_columns(feature_columns)].mean()
        drivers = _cluster_drivers(means)
        rows.append(
            {
                "cluster_id": int(cluster_id),
                "cluster_name": suggest_cluster_name(means),
                "team_season_count": int(len(cluster_frame)),
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


def suggest_cluster_name(zscores: pd.Series) -> str:
    """Suggest a cluster name from its strongest z-score signals."""
    values = zscores.rename(lambda column: column.removesuffix("_zscore"))

    if _value(values, "top_usage_concentration") >= 0.75:
        return "Heliocentric Creation Team"
    if (
        _value(values, "defensive_rating") <= -0.60
        and _value(values, "defensive_rebounding_percentage") >= 0.35
    ):
        return "Defense First Team"
    if (
        _value(values, "offensive_rebounding_percentage") >= 0.60
        and _value(values, "pace") <= 0.25
    ):
        return "Big Anchor Profile"
    if (
        _value(values, "three_point_attempt_rate") >= 0.50
        or _value(values, "three_point_percentage") >= 0.50
    ):
        return "Shooting Pressure Team"
    if (
        _value(values, "net_rating") >= 0.30
        and abs(_value(values, "defensive_rating")) <= 0.65
    ):
        return "Balanced Two Way Team"

    top_feature = values.abs().sort_values(ascending=False).index[0]
    return _fallback_cluster_name(top_feature)


def _assignment_frame(
    team_fingerprints: pd.DataFrame,
    feature_frame: pd.DataFrame,
    scaled: np.ndarray,
    pca_scores: np.ndarray,
    clusters: np.ndarray,
) -> pd.DataFrame:
    identity_columns = [
        column for column in IDENTITY_COLUMNS if column in team_fingerprints.columns
    ]
    label_columns = [
        column
        for column in ("playoff_tier", "quality_tier", "deep_playoff")
        if column in team_fingerprints.columns
    ]
    assignments = team_fingerprints.loc[:, [*identity_columns, *label_columns]].copy()
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
    if feature_frame.empty:
        raise ValueError("No usable roster archetype clustering features are available")
    if k < 2:
        raise ValueError("k must be at least 2")
    if k > len(feature_frame):
        raise ValueError("k cannot exceed the number of team-season rows")
    if pca_components < MIN_PCA_COMPONENTS or pca_components > MAX_PCA_COMPONENTS:
        raise ValueError("pca_components must be between 2 and 5")


def _effective_pca_components(
    *,
    requested_components: int,
    rows: int,
    features: int,
) -> int:
    return min(requested_components, rows, features)


def _first_available_column(
    frame: pd.DataFrame,
    normalized_columns: dict[str, str],
    aliases: tuple[str, ...],
) -> str | None:
    for alias in aliases:
        column = normalized_columns.get(alias)
        if column is not None and frame[column].notna().any():
            return column
    return None


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


def _fallback_cluster_name(feature: Any) -> str:
    feature_name = str(feature)
    if "pace" in feature_name:
        return "Tempo Driven Team"
    if "rebounding" in feature_name:
        return "Rebounding Edge Team"
    if "turnover" in feature_name:
        return "Low Mistake Team"
    if "free_throw" in feature_name:
        return "Rim Pressure Team"
    return "Balanced Two Way Team"
