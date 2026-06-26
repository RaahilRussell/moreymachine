"""Roster world schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import PROCESSED_DATA_DIR, REPORTS_DATA_DIR

ROSTER_SLOT_VALUES = (
    "starting_center",
    "backup_center",
    "non_embiid_center_minutes",
    "matchup_big",
    "double_big_stretch_partner",
    "stretch_forward",
    "defensive_forward",
    "3_and_d_wing",
    "movement_shooter",
    "low_usage_spacer",
    "low_usage_connector",
    "point_of_attack_defender",
    "secondary_creator",
    "bench_creator",
    "rebounding_forward",
    "regular_season_depth",
    "developmental_upside",
    "theoretical_star_upgrade",
    "no_clear_role",
    "poor_fit_redundant_role",
)

ROSTER_WORLD_SCHEMA = ArtifactSchema(
    name="roster_world_phi",
    path=PROCESSED_DATA_DIR / "roster_world_phi.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "team",
        "position",
        "age",
        "role_archetype",
        "current_role",
        "locked_role_status",
        "roster_slot",
        "usage_burden",
        "shooting_gravity",
        "defensive_role",
        "creation_role",
        "replaceability",
        "role_scarcity",
        "role_confidence",
        "evidence",
        "assumptions",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=("height", "weight", "current_minutes", "true_shooting"),
    enum_columns={"roster_slot": ROSTER_SLOT_VALUES},
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "player_name", "roster_slot"),
)

ROSTER_WORLD_REPORT_SCHEMA = ArtifactSchema(
    name="roster_world_phi_report",
    path=REPORTS_DATA_DIR / "roster_world_phi.md",
    required_columns=(),
    artifact_type="markdown",
)

SCHEMAS = (ROSTER_WORLD_SCHEMA,)

