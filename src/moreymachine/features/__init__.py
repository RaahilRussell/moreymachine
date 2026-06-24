"""Feature engineering utilities for MoreyMachine."""

from __future__ import annotations

from moreymachine.features.player_archetypes import (
    PLAYER_ARCHETYPE_SUMMARY_PATH,
    PLAYER_ARCHETYPES_PATH,
    PlayerArchetypeBuildResult,
    build_player_archetypes,
    create_player_archetypes,
    select_player_features,
    suggest_archetype_name,
)
from moreymachine.features.quality_tiers import (
    QUALITY_TIER_DEFINITIONS,
    QualityTierBuildResult,
    add_quality_tiers,
    build_quality_tiers,
)
from moreymachine.features.roster_archetypes import (
    ROSTER_ARCHETYPE_SUMMARY_PATH,
    TEAM_ROSTER_ARCHETYPES_PATH,
    RosterArchetypeBuildResult,
    build_roster_archetypes,
    create_roster_archetypes,
    select_cluster_features,
    suggest_cluster_name,
)
from moreymachine.features.roster_gaps import (
    DEFAULT_TARGET_TEAM,
    ROSTER_GAPS_MARKDOWN_PATH,
    ROSTER_GAPS_PATH,
    RosterGapBuildResult,
    build_roster_gaps,
    create_roster_gap_report,
    render_roster_gap_markdown,
)
from moreymachine.features.team_fingerprints import (
    FINGERPRINT_FEATURE_COLUMNS,
    LABEL_COLUMNS,
    TEAM_FINGERPRINTS_PATH,
    TeamFingerprintBuildResult,
    build_team_fingerprints,
    create_team_fingerprints,
)

__all__ = [
    "FINGERPRINT_FEATURE_COLUMNS",
    "LABEL_COLUMNS",
    "PLAYER_ARCHETYPE_SUMMARY_PATH",
    "PLAYER_ARCHETYPES_PATH",
    "QUALITY_TIER_DEFINITIONS",
    "DEFAULT_TARGET_TEAM",
    "ROSTER_ARCHETYPE_SUMMARY_PATH",
    "ROSTER_GAPS_MARKDOWN_PATH",
    "ROSTER_GAPS_PATH",
    "TEAM_FINGERPRINTS_PATH",
    "TEAM_ROSTER_ARCHETYPES_PATH",
    "PlayerArchetypeBuildResult",
    "QualityTierBuildResult",
    "RosterArchetypeBuildResult",
    "RosterGapBuildResult",
    "TeamFingerprintBuildResult",
    "add_quality_tiers",
    "build_player_archetypes",
    "build_roster_gaps",
    "build_roster_archetypes",
    "build_team_fingerprints",
    "build_quality_tiers",
    "create_player_archetypes",
    "create_roster_gap_report",
    "create_team_fingerprints",
    "create_roster_archetypes",
    "render_roster_gap_markdown",
    "select_player_features",
    "select_cluster_features",
    "suggest_archetype_name",
    "suggest_cluster_name",
]
