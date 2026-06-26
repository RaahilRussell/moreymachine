"""Candidate scenario schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR

SCENARIO_TYPES = (
    "best_case",
    "realistic_case",
    "conservative_case",
    "playoff_case",
    "regular_season_only_case",
    "overpay_case",
    "missing_data_case",
    "bad_fit_case",
)

CANDIDATE_SCENARIO_SCHEMA = ArtifactSchema(
    name="candidate_scenarios",
    path=FEATURES_DATA_DIR / "candidate_scenarios.parquet",
    required_columns=(
        "scenario_id",
        "player_name",
        "scenario_type",
        "roster_slot",
        "expected_minutes_context",
        "lineups_affected",
        "gaps_addressed",
        "gaps_not_addressed",
        "compatibility_summary",
        "acquisition_context",
        "upside_case",
        "downside_case",
        "risk_case",
        "confidence",
        "recommendation_under_this_scenario",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    enum_columns={"scenario_type": SCENARIO_TYPES},
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("scenario_id", "player_name", "scenario_type"),
)

SCHEMAS = (CANDIDATE_SCENARIO_SCHEMA,)

