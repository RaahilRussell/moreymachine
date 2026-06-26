"""Player profile schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import REPORTS_DATA_DIR

PROFILE_COMPLETENESS_VALUES = (
    "complete",
    "mostly_complete",
    "partial",
    "weak",
    "manual_review_needed",
)

PLAYER_PROFILE_SCHEMA = ArtifactSchema(
    name="player_profiles",
    path=REPORTS_DATA_DIR / "player_profiles.parquet",
    required_columns=(
        "player_profile_id",
        "player_id",
        "player_name",
        "current_team",
        "position",
        "candidate_type",
        "board_type",
        "acquisition_path",
        "source_summary",
        "pulled_at",
        "data_mode",
        "final_fit_score",
        "recommendation",
        "recommendation_confidence",
        "overall_tier",
        "explanation_confidence",
        "manual_review_required",
        "contradiction_flags",
        "primary_roster_slot",
        "expected_role_on_phi",
        "starter_possible",
        "closing_possible",
        "playoff_rotation_possible",
        "top_gaps_helped",
        "gaps_not_helped",
        "fit_with_embiid",
        "fit_with_maxey",
        "fit_with_george",
        "salary_card_json",
        "best_case_scenario",
        "realistic_scenario",
        "downside_scenario",
        "executive_summary",
        "why_the_model_likes_him",
        "what_he_helps_most",
        "what_he_does_not_solve",
        "role_on_sixers",
        "main_concerns",
        "why_this_could_be_wrong",
        "recommendation_interpretation",
        "evidence_objects",
        "claim_to_evidence_map",
        "unsupported_claim_flags",
        "data_sources",
        "missing_data_flags",
        "profile_completeness",
    ),
    enum_columns={"profile_completeness": PROFILE_COMPLETENESS_VALUES},
    provenance_columns=("source_summary", "pulled_at", "data_mode"),
    non_null_columns=("player_profile_id", "player_id", "player_name"),
    source_columns=("source_summary", "data_sources", "source_note"),
)

PLAYER_PROFILE_INDEX_SCHEMA = ArtifactSchema(
    name="player_profiles_index",
    path=REPORTS_DATA_DIR / "player_profiles_index.parquet",
    required_columns=("player_profile_id", "player_id", "player_name", "profile_path"),
    optional_columns=("current_team", "candidate_type", "recommendation"),
    non_null_columns=("player_profile_id", "player_id", "player_name"),
    source_columns=(),
    freshness_columns=(),
)

SALARY_CARD_SCHEMA = ArtifactSchema(
    name="player_salary_cards",
    path=REPORTS_DATA_DIR / "player_salary_cards.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "salary_card_title",
        "salary_summary",
        "contract_status",
        "cap_hit_millions",
        "base_salary_millions",
        "contract_aav_millions",
        "years_remaining",
        "option_status",
        "free_agent_year",
        "salary_bucket",
        "salary_source",
        "source_url",
        "freshness_status",
        "acquisition_path",
        "feasibility_tier",
        "what_makes_him_easy_or_hard_to_get",
        "what_data_is_missing",
        "manual_review_needed",
        "salary_warning_flags",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    provenance_columns=("salary_source", "source_url", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "player_name", "contract_status"),
    source_columns=("salary_source", "source_url", "source_note"),
)

SCHEMAS = (PLAYER_PROFILE_SCHEMA, PLAYER_PROFILE_INDEX_SCHEMA, SALARY_CARD_SCHEMA)

