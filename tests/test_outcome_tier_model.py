"""Tests for playoff outcome tier model training and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from moreymachine.models.outcome_tier_model import (
    OUTCOME_TIER_METRICS_PATH,
    OUTCOME_TIER_MODEL_PATH,
    OUTCOME_TIER_PREDICTIONS_PATH,
    PLAYOFF_TIER_LABELS,
    TARGET_COLUMN,
    chronological_split,
    prepare_modeling_frame,
    train_outcome_tier_model,
    usable_feature_columns,
)


def test_chronological_split_trains_on_earlier_seasons() -> None:
    frame = prepare_modeling_frame(_toy_fingerprints())

    split = chronological_split(frame, validation_seasons=2)

    assert split.train_seasons == ["2015-16", "2016-17"]
    assert split.test_seasons == ["2017-18", "2018-19"]
    assert set(split.train_frame["season"]) == {"2015-16", "2016-17"}
    assert set(split.test_frame["season"]) == {"2017-18", "2018-19"}


def test_usable_features_exclude_outcome_leakage_labels() -> None:
    frame = prepare_modeling_frame(_toy_fingerprints())
    feature_columns = usable_feature_columns(frame)

    assert "net_rating" in feature_columns
    assert "quality_tier" in feature_columns
    assert TARGET_COLUMN not in feature_columns
    assert "deep_playoff" not in feature_columns
    assert "finals_team" not in feature_columns
    assert "champion" not in feature_columns


def test_train_outcome_tier_model_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "team_fingerprints.parquet"
    model_path = tmp_path / OUTCOME_TIER_MODEL_PATH.name
    metrics_path = tmp_path / OUTCOME_TIER_METRICS_PATH.name
    predictions_path = tmp_path / OUTCOME_TIER_PREDICTIONS_PATH.name
    _toy_fingerprints().to_parquet(input_path, index=False)

    result = train_outcome_tier_model(
        input_path=input_path,
        model_path=model_path,
        metrics_path=metrics_path,
        predictions_path=predictions_path,
        validation_seasons=2,
        random_state=7,
        candidate_models=_small_candidate_models(),
    )

    assert result.model_path == model_path
    assert result.metrics_path == metrics_path
    assert result.predictions_path == predictions_path
    assert result.selected_model_name in {"random_forest", "gradient_boosting"}

    artifact = joblib.load(model_path)
    assert artifact["model_name"] == result.selected_model_name
    assert artifact["target_column"] == TARGET_COLUMN
    assert artifact["tier_labels"] == list(PLAYOFF_TIER_LABELS)
    assert "net_rating" in artifact["feature_columns"]

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["selected_model"] == result.selected_model_name
    assert set(metrics["models"]) == {"random_forest", "gradient_boosting"}
    assert metrics["models"]["random_forest"]["confusion_matrix"]["labels"] == list(
        PLAYOFF_TIER_LABELS
    )
    assert "mean_absolute_tier_error" in metrics["models"]["gradient_boosting"]
    assert "top_feature_importances" in metrics["models"]["random_forest"]

    predictions = pd.read_parquet(predictions_path)
    probability_columns = {
        f"playoff_tier_probability_{tier}" for tier in PLAYOFF_TIER_LABELS
    }
    assert {
        "season",
        "team_abbr",
        "actual_playoff_tier",
        "model_name",
        "expected_playoff_tier",
        "predicted_tier",
        *probability_columns,
    }.issubset(predictions.columns)
    assert set(predictions["model_name"]) == set(metrics["models"])
    assert (
        predictions.loc[:, list(probability_columns)].sum(axis=1).round(6).eq(1).all()
    )


def _toy_fingerprints() -> pd.DataFrame:
    rows = []
    for season_index, season in enumerate(["2015-16", "2016-17", "2017-18", "2018-19"]):
        for tier in PLAYOFF_TIER_LABELS:
            strength = tier + season_index * 0.05
            rows.append(
                {
                    "season": season,
                    "team_abbr": f"T{tier}",
                    "team_id": tier,
                    "team_name": f"Team {tier}",
                    "offensive_rating": 105 + strength,
                    "defensive_rating": 115 - strength,
                    "net_rating": strength * 2 - 5,
                    "pace": 96 + tier * 0.2,
                    "efg_percentage": 0.49 + tier * 0.01,
                    "turnover_percentage": 0.17 - tier * 0.005,
                    "offensive_rebounding_percentage": 0.22 + tier * 0.01,
                    "defensive_rebounding_percentage": 0.70 + tier * 0.01,
                    "free_throw_rate": 0.18 + tier * 0.01,
                    "three_point_attempt_rate": 0.30 + tier * 0.015,
                    "three_point_percentage": 0.32 + tier * 0.008,
                    "estimated_shooting_pressure": tier / 5,
                    "estimated_possession_control": tier / 6,
                    "estimated_two_way_balance": tier / 7,
                    "playoff_tier": tier,
                    "quality_tier": min(5, max(0, tier)),
                    "deep_playoff": tier >= 3,
                    "finals_team": tier >= 4,
                    "champion": tier == 5,
                }
            )
    return pd.DataFrame(rows)


def _small_candidate_models() -> dict[str, Pipeline]:
    return {
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        class_weight="balanced",
                        min_samples_leaf=1,
                        n_estimators=10,
                        random_state=7,
                    ),
                ),
            ]
        ),
        "gradient_boosting": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    GradientBoostingClassifier(n_estimators=10, random_state=7),
                ),
            ]
        ),
    }
