"""Recommendation board schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import REPORTS_DATA_DIR

RECOMMENDATION_VALUES = (
    "Priority Target",
    "Strong Fit If Affordable",
    "Role-Player Target",
    "Only If Cheap",
    "Avoid",
    "Unrealistic / Unavailable",
    "Missing Data / Cannot Evaluate",
    "Manual Review Required",
    "Contract Blocked",
)

CURRENT_RECOMMENDATION_SCHEMA = ArtifactSchema(
    name="candidate_fit_rankings_all",
    path=REPORTS_DATA_DIR / "candidate_fit_rankings_all.parquet",
    required_artifact=True,
    required_columns=(
        "player_id",
        "player_name",
        "candidate_type",
        "candidate_status_freshness",
        "board_type",
        "recommendation",
        "final_fit",
        "role_on_sixers",
        "why_fit",
        "concerns",
        "salary_context",
        "acquisition_summary",
        "risk_summary",
        "data_sources",
        "missing_data_flags",
    ),
    enum_columns={"recommendation": RECOMMENDATION_VALUES},
    provenance_columns=("data_sources",),
    non_null_columns=("player_id", "player_name", "candidate_type", "recommendation"),
    source_columns=("data_sources",),
)

RECOMMENDATION_V2_SCHEMA = ArtifactSchema(
    name="candidate_fit_rankings_v2",
    path=REPORTS_DATA_DIR / "candidate_fit_rankings_v2.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "current_team",
        "position",
        "candidate_type",
        "acquisition_path",
        "primary_scenario",
        "primary_roster_slot",
        "expected_role_on_phi",
        "expected_minutes_context",
        "starter_possible",
        "closing_possible",
        "playoff_rotation_possible",
        "best_case",
        "realistic_case",
        "downside_case",
        "gaps_addressed",
        "gaps_not_addressed",
        "compatibility_with_embiid",
        "compatibility_with_maxey",
        "compatibility_with_george",
        "final_recommendation_score",
        "recommendation",
        "recommendation_confidence",
        "contradiction_flags",
        "manual_review_required",
        "missing_data_flags",
        "evidence_summary",
        "source_summary",
    ),
    enum_columns={"recommendation": RECOMMENDATION_VALUES},
    provenance_columns=("source_summary",),
    non_null_columns=("player_id", "player_name", "recommendation"),
    source_columns=("source_summary", "source_url", "source_note"),
)

SCHEMAS = (CURRENT_RECOMMENDATION_SCHEMA, RECOMMENDATION_V2_SCHEMA)

