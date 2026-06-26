"""Acquisition feasibility schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR

ACQUISITION_PATHS = (
    "minimum_signing",
    "mle_or_exception_signing",
    "free_agent_market",
    "restricted_free_agent_offer",
    "small_trade",
    "medium_trade",
    "expensive_trade",
    "star_trade",
    "rookie_scale_trade",
    "theoretical_only",
    "unavailable_or_core",
    "unknown_missing_data",
)

ACQUISITION_FEASIBILITY_SCHEMA = ArtifactSchema(
    name="acquisition_feasibility",
    path=FEATURES_DATA_DIR / "acquisition_feasibility.parquet",
    required_columns=(
        "candidate_id",
        "candidate_name",
        "candidate_type",
        "contract_status",
        "salary_bucket",
        "cap_hit_millions",
        "base_salary_millions",
        "contract_aav_millions",
        "years_remaining",
        "option_status",
        "acquisition_path",
        "acquisition_difficulty",
        "acquisition_feasibility_score",
        "feasibility_tier",
        "trade_cost_proxy",
        "salary_matching_complexity",
        "apron_or_exception_uncertainty",
        "source_quality",
        "freshness_status",
        "manual_review_required",
        "evidence",
        "source",
        "source_url",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    enum_columns={"acquisition_path": ACQUISITION_PATHS},
    provenance_columns=("source", "source_url", "pulled_at", "data_mode"),
    non_null_columns=("candidate_id", "candidate_name", "acquisition_path"),
)

SCHEMAS = (ACQUISITION_FEASIBILITY_SCHEMA,)

