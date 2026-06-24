"""Model training utilities for MoreyMachine."""

from __future__ import annotations

from moreymachine.models.contender_model import (
    CONTENDER_METRICS_PATH,
    CONTENDER_MODEL_PATH,
    CONTENDER_PREDICTIONS_PATH,
    TARGET_COLUMN,
    ContenderModelTrainResult,
    train_contender_model,
)
from moreymachine.models.outcome_tier_model import (
    OUTCOME_TIER_METRICS_PATH,
    OUTCOME_TIER_MODEL_PATH,
    OUTCOME_TIER_PREDICTIONS_PATH,
    PLAYOFF_TIER_LABELS,
    OutcomeTierModelTrainResult,
    train_outcome_tier_model,
)

__all__ = [
    "CONTENDER_METRICS_PATH",
    "CONTENDER_MODEL_PATH",
    "CONTENDER_PREDICTIONS_PATH",
    "OUTCOME_TIER_METRICS_PATH",
    "OUTCOME_TIER_MODEL_PATH",
    "OUTCOME_TIER_PREDICTIONS_PATH",
    "PLAYOFF_TIER_LABELS",
    "TARGET_COLUMN",
    "ContenderModelTrainResult",
    "OutcomeTierModelTrainResult",
    "train_contender_model",
    "train_outcome_tier_model",
]
