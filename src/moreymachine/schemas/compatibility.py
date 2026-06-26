"""Player-to-player compatibility schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR

COMPATIBILITY_TYPES = (
    "clean_fit",
    "positive",
    "neutral",
    "scenario_dependent",
    "conflict",
    "blocked",
)

CANDIDATE_CORE_COMPATIBILITY_SCHEMA = ArtifactSchema(
    name="candidate_core_compatibility",
    path=FEATURES_DATA_DIR / "candidate_core_compatibility.parquet",
    required_columns=(
        "candidate_id",
        "candidate_name",
        "sixers_player_id",
        "sixers_player_name",
        "compatibility_score",
        "compatibility_type",
        "positives",
        "negatives",
        "conflict_flags",
        "lineup_contexts",
        "evidence",
        "confidence",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    enum_columns={"compatibility_type": COMPATIBILITY_TYPES},
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("candidate_id", "candidate_name", "sixers_player_name"),
)

SCHEMAS = (CANDIDATE_CORE_COMPATIBILITY_SCHEMA,)

