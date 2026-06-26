"""Entity-level schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import (
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    TEAM_SEASONS_PATH,
)

PLAYER_SCHEMA = ArtifactSchema(
    name="player_seasons",
    path=PLAYER_SEASONS_PATH,
    required_artifact=True,
    required_columns=(
        "season",
        "player_id",
        "player_name",
        "team_abbr",
        "position",
        "minutes",
        "usage_rate",
        "true_shooting",
    ),
    optional_columns=("three_pa", "three_pa_rate", "assist_pct", "turnover_pct"),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("season", "player_id", "player_name"),
)

PLAYER_BIO_SCHEMA = ArtifactSchema(
    name="player_bio",
    path=PLAYER_BIO_PATH,
    required_artifact=True,
    required_columns=("player_id", "player_name", "position", "height_inches"),
    optional_columns=("weight", "draft_year", "draft_number"),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("player_id", "player_name"),
)

TEAM_SCHEMA = ArtifactSchema(
    name="team_seasons",
    path=TEAM_SEASONS_PATH,
    required_artifact=True,
    required_columns=("season", "team_abbr", "off_rating", "def_rating", "net_rating"),
    optional_columns=("pace", "three_pa_rate", "efg_pct", "tov_pct"),
    provenance_columns=("source", "pulled_at", "data_mode"),
    non_null_columns=("season", "team_abbr"),
)

SCHEMAS = (PLAYER_SCHEMA, PLAYER_BIO_SCHEMA, TEAM_SCHEMA)
