"""Train and evaluate models that predict deep playoff teams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from moreymachine.features.team_fingerprints import (
    FINGERPRINT_FEATURE_COLUMNS,
    TEAM_FINGERPRINTS_PATH,
)
from moreymachine.utils.paths import MODELS_DATA_DIR, REPORTS_DATA_DIR

TARGET_COLUMN = "deep_playoff"
DEFAULT_FEATURE_COLUMNS = (*FINGERPRINT_FEATURE_COLUMNS, "quality_tier")
IDENTIFIER_COLUMNS = ("season", "team_abbr", "team_id", "team_name")

CONTENDER_MODEL_PATH = MODELS_DATA_DIR / "contender_model.joblib"
CONTENDER_METRICS_PATH = REPORTS_DATA_DIR / "contender_model_metrics.json"
CONTENDER_PREDICTIONS_PATH = REPORTS_DATA_DIR / "contender_model_predictions.parquet"


@dataclass(frozen=True)
class ContenderModelTrainResult:
    """Summary of a completed contender model training run."""

    selected_model_name: str
    train_seasons: tuple[str, ...]
    test_seasons: tuple[str, ...]
    feature_columns: tuple[str, ...]
    model_path: Path
    metrics_path: Path
    predictions_path: Path


def train_contender_model(
    *,
    input_path: str | Path = TEAM_FINGERPRINTS_PATH,
    model_path: str | Path = CONTENDER_MODEL_PATH,
    metrics_path: str | Path = CONTENDER_METRICS_PATH,
    predictions_path: str | Path = CONTENDER_PREDICTIONS_PATH,
    validation_seasons: int = 2,
    cutoff_season: str | None = None,
    random_state: int = 42,
    candidate_models: dict[str, Pipeline] | None = None,
) -> ContenderModelTrainResult:
    """Train contender models with chronological validation and save outputs."""
    fingerprints = pd.read_parquet(input_path)
    modeling_frame = prepare_modeling_frame(fingerprints)
    split = chronological_split(
        modeling_frame,
        validation_seasons=validation_seasons,
        cutoff_season=cutoff_season,
    )
    feature_columns = usable_feature_columns(split.train_frame, DEFAULT_FEATURE_COLUMNS)
    if not feature_columns:
        raise ValueError("No usable feature columns are available for model training")

    models = candidate_models or candidate_model_pipelines(random_state=random_state)
    trained_models = _fit_models(models, split.train_frame, feature_columns)
    predictions = _validation_predictions(
        trained_models,
        split.test_frame,
        feature_columns,
    )
    metrics_by_model = {
        model_name: evaluate_predictions(
            predictions[predictions["model_name"] == model_name]
        )
        for model_name in trained_models
    }
    selected_model_name = select_best_model(metrics_by_model)

    final_model = clone(models[selected_model_name])
    final_model.fit(
        _feature_matrix(modeling_frame, feature_columns),
        modeling_frame[TARGET_COLUMN].astype(int),
    )

    model_output = Path(model_path)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model_name": selected_model_name,
            "model": final_model,
            "feature_columns": list(feature_columns),
            "target_column": TARGET_COLUMN,
            "trained_at_utc": datetime.now(UTC).isoformat(),
        },
        model_output,
    )

    predictions_output = Path(predictions_path)
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(predictions_output, index=False)

    metrics_payload = {
        "target": TARGET_COLUMN,
        "selected_model": selected_model_name,
        "feature_columns": list(feature_columns),
        "train_seasons": split.train_seasons,
        "test_seasons": split.test_seasons,
        "models": {
            model_name: {
                **metrics_by_model[model_name],
                "feature_importance": feature_importance(
                    trained_models[model_name],
                    feature_columns,
                ),
            }
            for model_name in trained_models
        },
    }
    metrics_output = Path(metrics_path)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    with metrics_output.open("w", encoding="utf-8") as file:
        json.dump(_json_safe(metrics_payload), file, indent=2, sort_keys=True)

    return ContenderModelTrainResult(
        selected_model_name=selected_model_name,
        train_seasons=tuple(split.train_seasons),
        test_seasons=tuple(split.test_seasons),
        feature_columns=tuple(feature_columns),
        model_path=model_output,
        metrics_path=metrics_output,
        predictions_path=predictions_output,
    )


@dataclass(frozen=True)
class ChronologicalSplit:
    """Chronological train/test split result."""

    train_frame: pd.DataFrame
    test_frame: pd.DataFrame
    train_seasons: list[str]
    test_seasons: list[str]


def prepare_modeling_frame(
    frame: pd.DataFrame,
    *,
    target_column: str = TARGET_COLUMN,
) -> pd.DataFrame:
    """Return rows with a usable binary target for contender modeling."""
    required_columns = {"season", target_column}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"Modeling data is missing required columns: {missing}")

    result = frame.copy()
    result[target_column] = _target_to_int(result[target_column])
    result = result.dropna(subset=["season", target_column]).copy()
    result[target_column] = result[target_column].astype(int)
    if result[target_column].nunique() < 2:
        raise ValueError("Modeling data must contain both target classes")
    return result


def chronological_split(
    frame: pd.DataFrame,
    *,
    validation_seasons: int = 2,
    cutoff_season: str | None = None,
) -> ChronologicalSplit:
    """Split data so train seasons are earlier than test seasons."""
    seasons = sorted(
        (str(season) for season in frame["season"].dropna().unique()),
        key=_season_sort_key,
    )
    if len(seasons) < 2:
        raise ValueError("Chronological validation requires at least two seasons")

    if cutoff_season is not None:
        cutoff_year = _season_sort_key(cutoff_season)
        train_seasons = [
            season for season in seasons if _season_sort_key(season) <= cutoff_year
        ]
        test_seasons = [
            season for season in seasons if _season_sort_key(season) > cutoff_year
        ]
    else:
        if validation_seasons < 1:
            raise ValueError("validation_seasons must be at least 1")
        split_index = max(1, len(seasons) - validation_seasons)
        train_seasons = seasons[:split_index]
        test_seasons = seasons[split_index:]

    if not train_seasons or not test_seasons:
        raise ValueError("Chronological split must produce train and test seasons")

    train_frame = frame[frame["season"].astype(str).isin(train_seasons)].copy()
    test_frame = frame[frame["season"].astype(str).isin(test_seasons)].copy()
    if train_frame[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Training split must contain both target classes")
    return ChronologicalSplit(
        train_frame=train_frame,
        test_frame=test_frame,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
    )


def candidate_model_pipelines(random_state: int = 42) -> dict[str, Pipeline]:
    """Return the requested contender model candidates."""
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=2000,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        class_weight="balanced",
                        min_samples_leaf=2,
                        n_estimators=300,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "gradient_boosting": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("model", GradientBoostingClassifier(random_state=random_state)),
            ]
        ),
    }


def usable_feature_columns(
    train_frame: pd.DataFrame,
    requested_columns: tuple[str, ...] = DEFAULT_FEATURE_COLUMNS,
) -> list[str]:
    """Return numeric feature columns that have at least one training value."""
    feature_columns: list[str] = []
    for column in requested_columns:
        if column not in train_frame.columns:
            continue
        values = pd.to_numeric(train_frame[column], errors="coerce")
        if values.notna().any():
            feature_columns.append(column)
    return feature_columns


def evaluate_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    """Compute validation metrics for one model's predictions."""
    y_true = predictions["actual_deep_playoff"].astype(int)
    y_score = predictions["contender_probability"].astype(float)
    y_pred = predictions["predicted_deep_playoff"].astype(int)

    roc_auc = None
    if y_true.nunique() == 2:
        roc_auc = float(roc_auc_score(y_true, y_score))

    return {
        "roc_auc": roc_auc,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision_at_top_8_per_season": precision_at_top_k_per_season(
            predictions,
            k=8,
        ),
        "calibration_table": calibration_table(predictions),
    }


def precision_at_top_k_per_season(
    predictions: pd.DataFrame,
    *,
    k: int = 8,
) -> dict[str, Any]:
    """Compute precision among the top-k predicted teams in each season."""
    by_season = []
    for season, season_frame in predictions.groupby("season"):
        top = season_frame.nlargest(min(k, len(season_frame)), "contender_probability")
        precision = float(top["actual_deep_playoff"].mean())
        by_season.append(
            {
                "season": str(season),
                "k": int(len(top)),
                "precision": precision,
            }
        )

    average = None
    if by_season:
        average = float(np.mean([row["precision"] for row in by_season]))
    return {"average": average, "by_season": by_season}


def calibration_table(
    predictions: pd.DataFrame,
    *,
    bins: int = 10,
) -> list[dict[str, Any]]:
    """Build a fixed-width calibration table for predicted probabilities."""
    if predictions.empty:
        return []

    frame = predictions.copy()
    edges = np.linspace(0, 1, bins + 1)
    labels = [f"{edges[index]:.1f}-{edges[index + 1]:.1f}" for index in range(bins)]
    frame["probability_bin"] = pd.cut(
        frame["contender_probability"].clip(0, 1),
        bins=edges,
        labels=labels,
        include_lowest=True,
    )
    grouped = (
        frame.groupby("probability_bin", observed=True)
        .agg(
            count=("actual_deep_playoff", "size"),
            avg_predicted_probability=("contender_probability", "mean"),
            observed_rate=("actual_deep_playoff", "mean"),
        )
        .reset_index()
    )
    return [
        {
            "probability_bin": str(row.probability_bin),
            "count": int(row.count),
            "avg_predicted_probability": float(row.avg_predicted_probability),
            "observed_rate": float(row.observed_rate),
        }
        for row in grouped.itertuples()
    ]


def select_best_model(metrics_by_model: dict[str, dict[str, Any]]) -> str:
    """Select the best model by ROC-AUC, falling back to accuracy."""
    if not metrics_by_model:
        raise ValueError("No model metrics were provided")

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[int, float, float]:
        metrics = item[1]
        roc_auc = metrics.get("roc_auc")
        has_auc = roc_auc is not None
        return (int(has_auc), float(roc_auc or -1.0), float(metrics["accuracy"]))

    return max(metrics_by_model.items(), key=sort_key)[0]


def feature_importance(
    model: Pipeline, feature_columns: list[str]
) -> list[dict[str, Any]]:
    """Extract coefficients or feature importances when the model exposes them."""
    estimator = model.named_steps["model"]
    if hasattr(estimator, "coef_"):
        coefficients = estimator.coef_[0]
        return _sorted_feature_values(feature_columns, coefficients, "coefficient")
    if hasattr(estimator, "feature_importances_"):
        return _sorted_feature_values(
            feature_columns,
            estimator.feature_importances_,
            "importance",
        )
    return []


def _fit_models(
    models: dict[str, Pipeline],
    train_frame: pd.DataFrame,
    feature_columns: list[str],
) -> dict[str, Pipeline]:
    x_train = _feature_matrix(train_frame, feature_columns)
    y_train = train_frame[TARGET_COLUMN].astype(int)
    trained = {}
    for model_name, model in models.items():
        fitted = clone(model)
        fitted.fit(x_train, y_train)
        trained[model_name] = fitted
    return trained


def _validation_predictions(
    trained_models: dict[str, Pipeline],
    test_frame: pd.DataFrame,
    feature_columns: list[str],
) -> pd.DataFrame:
    x_test = _feature_matrix(test_frame, feature_columns)
    id_columns = [
        column for column in IDENTIFIER_COLUMNS if column in test_frame.columns
    ]
    base = test_frame.loc[:, id_columns].copy()
    base["actual_deep_playoff"] = test_frame[TARGET_COLUMN].astype(int).to_numpy()

    rows = []
    for model_name, model in trained_models.items():
        model_predictions = base.copy()
        probabilities = model.predict_proba(x_test)[:, 1]
        model_predictions["model_name"] = model_name
        model_predictions["contender_probability"] = probabilities
        model_predictions["predicted_deep_playoff"] = probabilities >= 0.5
        rows.append(model_predictions)
    return pd.concat(rows, ignore_index=True)


def _feature_matrix(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return (
        frame.loc[:, feature_columns]
        .apply(pd.to_numeric, errors="coerce")
        .astype(float)
    )


def _target_to_int(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype("boolean").astype("Int64")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").astype("Int64")

    normalized = series.astype("string").str.strip().str.lower()
    mapped = normalized.map(
        {
            "true": 1,
            "t": 1,
            "yes": 1,
            "y": 1,
            "1": 1,
            "false": 0,
            "f": 0,
            "no": 0,
            "n": 0,
            "0": 0,
        }
    )
    return mapped.astype("Int64")


def _season_sort_key(season: str) -> int:
    season_text = str(season)
    return int(season_text[:4])


def _sorted_feature_values(
    feature_columns: list[str],
    values: Any,
    value_name: str,
) -> list[dict[str, Any]]:
    rows = [
        {"feature": feature, value_name: float(value)}
        for feature, value in zip(feature_columns, values, strict=True)
    ]
    return sorted(rows, key=lambda row: abs(row[value_name]), reverse=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value
