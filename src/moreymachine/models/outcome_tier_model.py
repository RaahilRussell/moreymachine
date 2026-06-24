"""Train and evaluate models that predict playoff outcome tiers."""

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
from sklearn.metrics import accuracy_score, confusion_matrix, mean_absolute_error
from sklearn.pipeline import Pipeline

from moreymachine.features.team_fingerprints import (
    FINGERPRINT_FEATURE_COLUMNS,
    TEAM_FINGERPRINTS_PATH,
)
from moreymachine.utils.paths import MODELS_DATA_DIR, REPORTS_DATA_DIR

TARGET_COLUMN = "playoff_tier"
PLAYOFF_TIER_LABELS = tuple(range(6))
DEFAULT_FEATURE_COLUMNS = (*FINGERPRINT_FEATURE_COLUMNS, "quality_tier")
IDENTIFIER_COLUMNS = ("season", "team_abbr", "team_id", "team_name")

OUTCOME_TIER_MODEL_PATH = MODELS_DATA_DIR / "outcome_tier_model.joblib"
OUTCOME_TIER_METRICS_PATH = REPORTS_DATA_DIR / "outcome_tier_metrics.json"
OUTCOME_TIER_PREDICTIONS_PATH = REPORTS_DATA_DIR / "outcome_tier_predictions.parquet"


@dataclass(frozen=True)
class OutcomeTierModelTrainResult:
    """Summary of a completed playoff outcome tier model training run."""

    selected_model_name: str
    train_seasons: tuple[str, ...]
    test_seasons: tuple[str, ...]
    feature_columns: tuple[str, ...]
    model_path: Path
    metrics_path: Path
    predictions_path: Path


@dataclass(frozen=True)
class ChronologicalSplit:
    """Chronological train/test split result."""

    train_frame: pd.DataFrame
    test_frame: pd.DataFrame
    train_seasons: list[str]
    test_seasons: list[str]


def train_outcome_tier_model(
    *,
    input_path: str | Path = TEAM_FINGERPRINTS_PATH,
    model_path: str | Path = OUTCOME_TIER_MODEL_PATH,
    metrics_path: str | Path = OUTCOME_TIER_METRICS_PATH,
    predictions_path: str | Path = OUTCOME_TIER_PREDICTIONS_PATH,
    validation_seasons: int = 2,
    cutoff_season: str | None = None,
    random_state: int = 42,
    candidate_models: dict[str, Pipeline] | None = None,
) -> OutcomeTierModelTrainResult:
    """Train playoff outcome tier models and save artifacts/reports."""
    fingerprints = pd.read_parquet(input_path)
    modeling_frame = prepare_modeling_frame(fingerprints)
    split = chronological_split(
        modeling_frame,
        validation_seasons=validation_seasons,
        cutoff_season=cutoff_season,
    )
    feature_columns = usable_feature_columns(split.train_frame)
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
            "tier_labels": list(PLAYOFF_TIER_LABELS),
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
        "tier_labels": list(PLAYOFF_TIER_LABELS),
        "feature_columns": list(feature_columns),
        "train_seasons": split.train_seasons,
        "test_seasons": split.test_seasons,
        "models": {
            model_name: {
                **metrics_by_model[model_name],
                "top_feature_importances": feature_importance(
                    trained_models[model_name],
                    feature_columns,
                    top_n=15,
                ),
            }
            for model_name in trained_models
        },
    }
    metrics_output = Path(metrics_path)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    with metrics_output.open("w", encoding="utf-8") as file:
        json.dump(_json_safe(metrics_payload), file, indent=2, sort_keys=True)

    return OutcomeTierModelTrainResult(
        selected_model_name=selected_model_name,
        train_seasons=tuple(split.train_seasons),
        test_seasons=tuple(split.test_seasons),
        feature_columns=tuple(feature_columns),
        model_path=model_output,
        metrics_path=metrics_output,
        predictions_path=predictions_output,
    )


def prepare_modeling_frame(
    frame: pd.DataFrame,
    *,
    target_column: str = TARGET_COLUMN,
) -> pd.DataFrame:
    """Return rows with valid playoff tier targets."""
    required_columns = {"season", target_column}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"Modeling data is missing required columns: {missing}")

    result = frame.copy()
    result[target_column] = pd.to_numeric(result[target_column], errors="coerce")
    result = result.dropna(subset=["season", target_column]).copy()
    result[target_column] = result[target_column].astype(int)

    invalid_tiers = sorted(set(result[target_column]) - set(PLAYOFF_TIER_LABELS))
    if invalid_tiers:
        raise ValueError(f"Invalid playoff_tier values: {invalid_tiers}")
    if result[target_column].nunique() < 2:
        raise ValueError("Modeling data must contain at least two playoff tiers")
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
        raise ValueError("Training split must contain at least two playoff tiers")
    return ChronologicalSplit(
        train_frame=train_frame,
        test_frame=test_frame,
        train_seasons=train_seasons,
        test_seasons=test_seasons,
    )


def candidate_model_pipelines(random_state: int = 42) -> dict[str, Pipeline]:
    """Return the requested playoff outcome tier model candidates."""
    return {
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
    """Compute validation metrics for one model's playoff tier predictions."""
    actual = predictions["actual_playoff_tier"].astype(int)
    predicted = predictions["predicted_tier"].astype(int)
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "mean_absolute_tier_error": float(mean_absolute_error(actual, predicted)),
        "expected_tier_mean_absolute_error": float(
            mean_absolute_error(actual, predictions["expected_playoff_tier"])
        ),
        "confusion_matrix": {
            "labels": list(PLAYOFF_TIER_LABELS),
            "matrix": confusion_matrix(
                actual,
                predicted,
                labels=list(PLAYOFF_TIER_LABELS),
            ).tolist(),
        },
    }


def select_best_model(metrics_by_model: dict[str, dict[str, Any]]) -> str:
    """Select the best model by lowest tier MAE, then highest accuracy."""
    if not metrics_by_model:
        raise ValueError("No model metrics were provided")

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, float]:
        metrics = item[1]
        return (
            -float(metrics["mean_absolute_tier_error"]),
            float(metrics["accuracy"]),
        )

    return max(metrics_by_model.items(), key=sort_key)[0]


def feature_importance(
    model: Pipeline,
    feature_columns: list[str],
    *,
    top_n: int = 15,
) -> list[dict[str, Any]]:
    """Extract top feature importances when the model exposes them."""
    estimator = model.named_steps["model"]
    if not hasattr(estimator, "feature_importances_"):
        return []

    rows = [
        {"feature": feature, "importance": float(importance)}
        for feature, importance in zip(
            feature_columns,
            estimator.feature_importances_,
            strict=True,
        )
    ]
    rows.sort(key=lambda row: row["importance"], reverse=True)
    return rows[:top_n]


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
    base["actual_playoff_tier"] = test_frame[TARGET_COLUMN].astype(int).to_numpy()

    rows = []
    for model_name, model in trained_models.items():
        model_predictions = base.copy()
        probabilities = _aligned_probabilities(model, x_test)
        model_predictions["model_name"] = model_name
        for tier in PLAYOFF_TIER_LABELS:
            model_predictions[f"playoff_tier_probability_{tier}"] = probabilities[tier]
        probability_frame = model_predictions[
            [f"playoff_tier_probability_{tier}" for tier in PLAYOFF_TIER_LABELS]
        ]
        model_predictions["expected_playoff_tier"] = sum(
            tier * probability_frame[f"playoff_tier_probability_{tier}"]
            for tier in PLAYOFF_TIER_LABELS
        )
        model_predictions["predicted_tier"] = probability_frame.to_numpy().argmax(
            axis=1
        )
        rows.append(model_predictions)
    return pd.concat(rows, ignore_index=True)


def _aligned_probabilities(
    model: Pipeline, features: pd.DataFrame
) -> dict[int, np.ndarray]:
    raw_probabilities = model.predict_proba(features)
    estimator = model.named_steps["model"]
    aligned = {
        tier: np.zeros(raw_probabilities.shape[0], dtype=float)
        for tier in PLAYOFF_TIER_LABELS
    }
    for column_index, class_label in enumerate(estimator.classes_):
        class_tier = int(class_label)
        if class_tier in aligned:
            aligned[class_tier] = raw_probabilities[:, column_index]
    return aligned


def _feature_matrix(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return (
        frame.loc[:, feature_columns]
        .apply(pd.to_numeric, errors="coerce")
        .astype(float)
    )


def _season_sort_key(season: str) -> int:
    return int(str(season)[:4])


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
