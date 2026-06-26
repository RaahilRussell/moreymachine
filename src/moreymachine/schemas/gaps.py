"""Team gap schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR, REPORTS_DATA_DIR

CURRENT_ROSTER_GAPS_SCHEMA = ArtifactSchema(
    name="phi_roster_gaps",
    path=REPORTS_DATA_DIR / "phi_roster_gaps.parquet",
    required_artifact=True,
    required_columns=(
        "target_team",
        "target_season",
        "category_key",
        "gap_name",
        "severity_score",
        "what_it_means",
        "why_it_matters_in_playoffs",
        "what_kind_of_player_fixes_it",
        "data_sources",
    ),
    optional_columns=("gap_size", "gap_tier", "relevant_stats"),
    provenance_columns=("data_sources",),
    non_null_columns=("target_team", "target_season", "category_key", "gap_name"),
    source_columns=("data_sources",),
)

SIXERS_GAP_MODEL_SCHEMA = ArtifactSchema(
    name="sixers_gap_model",
    path=FEATURES_DATA_DIR / "sixers_gap_model.parquet",
    required_columns=(
        "gap_id",
        "gap_name",
        "gap_category",
        "source_blueprint",
        "sixers_current_value",
        "contender_reference_value",
        "severity",
        "confidence",
        "roster_slot_needed",
        "skill_requirements",
        "lineup_contexts",
        "why_it_matters",
        "playoff_failure_mode",
        "what_fixes_it",
        "what_does_not_fix_it",
        "evidence",
        "assumptions",
        "missing_data_flags",
    ),
    optional_columns=("contender_percentile",),
    provenance_columns=("source_blueprint",),
    non_null_columns=("gap_id", "gap_name", "gap_category"),
    source_columns=("source_blueprint", "source_url", "source_note"),
)

SCHEMAS = (CURRENT_ROSTER_GAPS_SCHEMA, SIXERS_GAP_MODEL_SCHEMA)

