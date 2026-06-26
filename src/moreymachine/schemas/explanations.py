"""Explanation and evidence schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import REPORTS_DATA_DIR

EXPLANATION_CLAIM_SCHEMA = ArtifactSchema(
    name="explanation_claims",
    path=REPORTS_DATA_DIR / "explanation_claims.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "claim",
        "claim_type",
        "allowed",
        "evidence_object_ids",
        "confidence",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "claim", "claim_type"),
)

EVIDENCE_OBJECT_SCHEMA = ArtifactSchema(
    name="evidence_objects",
    path=REPORTS_DATA_DIR / "evidence_objects.parquet",
    required_columns=(
        "evidence_id",
        "player_id",
        "claim",
        "evidence_type",
        "supporting_columns",
        "supporting_values",
        "source",
        "confidence",
        "missing_data_flags",
    ),
    optional_columns=("source_url", "pulled_at", "data_mode"),
    provenance_columns=("source",),
    non_null_columns=("evidence_id", "claim", "evidence_type"),
)

SCHEMAS = (EXPLANATION_CLAIM_SCHEMA, EVIDENCE_OBJECT_SCHEMA)

