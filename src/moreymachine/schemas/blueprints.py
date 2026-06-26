"""Contender blueprint schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import FEATURES_DATA_DIR

BLUEPRINT_COHORTS = (
    "champions",
    "finalists",
    "conference_finalists",
    "top_5_net_rating",
    "top_10_net_rating",
    "star_center_anchor",
    "heliocentric_guard",
    "wing_depth_switchable",
    "balanced_two_way",
    "defense_first",
    "shooting_pressure",
    "depth_heavy",
    "dual_big",
    "creator_committee",
)

CONTENDER_BLUEPRINT_SCHEMA = ArtifactSchema(
    name="contender_blueprints",
    path=FEATURES_DATA_DIR / "contender_blueprints.parquet",
    required_columns=(
        "blueprint_id",
        "blueprint_name",
        "cohort",
        "required_roles",
        "redundant_roles",
        "phi_distance",
        "what_moves_phi_closer",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=(
        "off_rating",
        "def_rating",
        "net_rating",
        "three_pa_rate",
        "usage_distribution",
    ),
    enum_columns={"cohort": BLUEPRINT_COHORTS},
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("blueprint_id", "blueprint_name", "cohort"),
)

TEAM_CONSTRUCTION_ARCHETYPE_SCHEMA = ArtifactSchema(
    name="team_construction_archetypes",
    path=FEATURES_DATA_DIR / "team_construction_archetypes.parquet",
    required_columns=(
        "team_abbr",
        "season",
        "team_construction_archetype",
        "source",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=("blueprint_id", "net_rating", "off_rating", "def_rating"),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("team_abbr", "season", "team_construction_archetype"),
)

SCHEMAS = (CONTENDER_BLUEPRINT_SCHEMA, TEAM_CONSTRUCTION_ARCHETYPE_SCHEMA)

