"""Roster simulation schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.schemas.roster_world import ROSTER_SLOT_VALUES
from moreymachine.utils.paths import FEATURES_DATA_DIR

CANDIDATE_ROSTER_SIMULATION_SCHEMA = ArtifactSchema(
    name="candidate_roster_simulation",
    path=FEATURES_DATA_DIR / "candidate_roster_simulation.parquet",
    required_columns=(
        "player_id",
        "player_name",
        "possible_roster_slots",
        "primary_roster_slot",
        "secondary_roster_slots",
        "blocked_slots",
        "role_on_phi",
        "expected_role_on_phi",
        "expected_minutes_context",
        "likely_lineup_contexts",
        "bad_lineup_contexts",
        "starter_possible",
        "closing_lineup_possible",
        "playoff_rotation_possible",
        "regular_season_depth_only",
        "matchup_dependent",
        "two_big_compatible",
        "no_clear_role",
        "embiid_overlap_flag",
        "maxey_overlap_flag",
        "george_overlap_flag",
        "role_redundancy_flags",
        "contradiction_flags",
        "role_confidence",
        "data_evidence",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    enum_columns={"primary_roster_slot": ROSTER_SLOT_VALUES},
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "player_name", "primary_roster_slot"),
)

SCHEMAS = (CANDIDATE_ROSTER_SIMULATION_SCHEMA,)

