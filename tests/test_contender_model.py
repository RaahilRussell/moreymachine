"""Tests for contender model training and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from moreymachine.models.contender_model import (
    CONTENDER_METRICS_PATH,
    CONTENDER_MODEL_PATH,
    CONTENDER_PREDICTIONS_PATH,
    TARGET_COLUMN,
    chronological_split,
    precision_at_top_k_per_season,
    prepare_modeling_frame,
    train_contender_model,
    usable_feature_columns,
)


def test_chronological_split_trains_on_earlier_seasons() -> None:
    frame = prepare_modeling_frame(_toy_fingerprints())

    split = chronological_split(frame, validation_seasons=2)

    assert split.train_seasons == ["2015-16", "2016-17"]
    assert split.test_seasons == ["2017-18", "2018-19"]
    assert set(split.train_frame["season"]) == {"2015-16", "2016-17"}
    assert set(split.test_frame["season"]) == {"2017-18", "2018-19"}


def test_usable_features_exclude_leakage_labels() -> None:
    frame = prepare_modeling_frame(_toy_fingerprints())
    feature_columns = usable_feature_columns(frame)

    assert "net_rating" in feature_columns
    assert "quality_tier" in feature_columns
    assert "playoff_tier" not in feature_columns
    assert "finals_team" not in feature_columns
    assert TARGET_COLUMN not in feature_columns


def test_precision_at_top_k_per_season() -> None:
    predictions = pd.DataFrame(
        {
            "season": ["2018-19", "2018-19", "2018-19"],
            "actual_deep_playoff": [1, 0, 1],
            "contender_probability": [0.9, 0.8, 0.1],
        }
    )

    result = precision_at_top_k_per_season(predictions, k=2)

    assert result["average"] == 0.5
    assert result["by_season"] == [{"season": "2018-19", "k": 2, "precision": 0.5}]


def test_train_contender_model_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "team_fingerprints.parquet"
    model_path = tmp_path / CONTENDER_MODEL_PATH.name
    metrics_path = tmp_path / CONTENDER_METRICS_PATH.name
    predictions_path = tmp_path / CONTENDER_PREDICTIONS_PATH.name
    _toy_fingerprints().to_parquet(input_path, index=False)

    result = train_contender_model(
        input_path=input_path,
        model_path=model_path,
        metrics_path=metrics_path,
        predictions_path=predictions_path,
        validation_seasons=2,
        random_state=7,
    )

    assert result.model_path == model_path
    assert result.metrics_path == metrics_path
    assert result.predictions_path == predictions_path
    assert result.selected_model_name in {
        "logistic_regression",
        "random_forest",
        "gradient_boosting",
    }

    artifact = joblib.load(model_path)
    assert artifact["model_name"] == result.selected_model_name
    assert artifact["target_column"] == TARGET_COLUMN
    assert "net_rating" in artifact["feature_columns"]

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["selected_model"] == result.selected_model_name
    assert set(metrics["models"]) == {
        "logistic_regression",
        "random_forest",
        "gradient_boosting",
    }
    assert "calibration_table" in metrics["models"]["logistic_regression"]
    assert "feature_importance" in metrics["models"]["random_forest"]

    predictions = pd.read_parquet(predictions_path)
    assert {
        "season",
        "team_abbr",
        "actual_deep_playoff",
        "model_name",
        "contender_probability",
        "predicted_deep_playoff",
    }.issubset(predictions.columns)
    assert set(predictions["model_name"]) == set(metrics["models"])


def _toy_fingerprints() -> pd.DataFrame:
    rows = []
    for season_index, season in enumerate(["2015-16", "2016-17", "2017-18", "2018-19"]):
        for team_index in range(10):
            strength = team_index - 4.5 + season_index * 0.1
            deep_playoff = team_index >= 7
            rows.append(
                {
                    "season": season,
                    "team_abbr": f"T{team_index:02d}",
                    "team_id": team_index,
                    "team_name": f"Team {team_index:02d}",
                    "offensive_rating": 110 + strength,
                    "defensive_rating": 110 - strength,
                    "net_rating": strength * 2,
                    "pace": 96 + team_index * 0.1,
                    "efg_percentage": 0.50 + team_index * 0.005,
                    "turnover_percentage": 0.16 - team_index * 0.003,
                    "offensive_rebounding_percentage": 0.22 + team_index * 0.004,
                    "defensive_rebounding_percentage": 0.70 + team_index * 0.004,
                    "free_throw_rate": 0.18 + team_index * 0.004,
                    "three_point_attempt_rate": 0.30 + team_index * 0.01,
                    "three_point_percentage": 0.32 + team_index * 0.004,
                    "estimated_shooting_pressure": team_index / 9,
                    "estimated_possession_control": team_index / 10,
                    "estimated_two_way_balance": team_index / 11,
                    "playoff_tier": 3 if deep_playoff else 1,
                    "quality_tier": (
                        5 if team_index >= 8 else (4 if team_index >= 6 else 2)
                    ),
                    "deep_playoff": deep_playoff,
                    "finals_team": team_index >= 8,
                    "champion": team_index == 9,
                }
            )
    return pd.DataFrame(rows)
