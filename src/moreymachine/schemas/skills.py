"""Player skill-profile schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR, PLAYER_ROLE_EXPLANATIONS_PATH

SKILL_DIMENSIONS = (
    "spot_up_spacing",
    "movement_shooting",
    "pull_up_shooting",
    "shooting_gravity",
    "fake_spacing_risk",
    "primary_creation",
    "secondary_creation",
    "connector_passing",
    "low_usage_fit",
    "rim_pressure",
    "transition_pressure",
    "ball_security",
    "offensive_rebounding",
    "defensive_rebounding",
    "rim_protection",
    "vertical_spacing",
    "wing_defense_proxy",
    "point_of_attack_defense_proxy",
    "defensive_event_proxy",
    "switchability_proxy",
    "playoff_portability_base",
    "sample_reliability",
    "role_stability",
)

PLAYER_ROLES_SCHEMA = ArtifactSchema(
    name="player_roles",
    path=PLAYER_ROLE_EXPLANATIONS_PATH,
    required_artifact=True,
    required_columns=(
        "player_id",
        "player_name",
        "role_archetype",
        "expected_role",
        "role_confidence",
        "data_mode",
    ),
    optional_columns=(
        "spacing_score",
        "rim_protection_proxy",
        "wing_defense_proxy",
        "point_of_attack_defense_proxy",
    ),
    provenance_columns=("season", "data_mode"),
    non_null_columns=("player_id", "player_name", "role_archetype"),
    source_columns=("season", "source_url", "source_note"),
    freshness_columns=(),
)

PLAYER_SKILL_PROFILE_SCHEMA = ArtifactSchema(
    name="player_skill_profiles",
    path=FEATURES_DATA_DIR / "player_skill_profiles.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "season",
        *SKILL_DIMENSIONS,
        "evidence",
        "confidence",
        "claim_allowed",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=("foul_risk", "minutes_context", "age_curve_context"),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "player_name"),
)

SCHEMAS = (PLAYER_ROLES_SCHEMA, PLAYER_SKILL_PROFILE_SCHEMA)

