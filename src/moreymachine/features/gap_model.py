"""Blueprint-driven Sixers gap model.

This layer turns broad roster diagnosis into role-specific needs that later
recommendation layers can enforce. A candidate should only receive need-match
credit for a gap when the player's skill profile permits the relevant claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.context.roster_world import ROSTER_WORLD_PATH
from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.contender_blueprints import CONTENDER_BLUEPRINTS_PATH
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR, REPORTS_DATA_DIR

SIXERS_GAP_MODEL_PATH = FEATURES_DATA_DIR / "sixers_gap_model.parquet"
SIXERS_GAP_MODEL_REPORT_PATH = REPORTS_DATA_DIR / "sixers_gap_model.md"
CURRENT_GAP_REPORT_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.parquet"


@dataclass(frozen=True)
class GapModelResult:
    """Summary from a gap-model build."""

    gaps: int
    critical_or_significant: int
    output_path: Path
    report_path: Path


@dataclass(frozen=True)
class GapSpec:
    """Definition for one role-specific Sixers gap."""

    gap_id: str
    gap_name: str
    gap_category: str
    source_blueprint: str
    metric: str
    roster_slot_needed: str
    skill_requirements: tuple[str, ...]
    lineup_contexts: tuple[str, ...]
    why_it_matters: str
    playoff_failure_mode: str
    what_fixes_it: tuple[str, ...]
    what_does_not_fix_it: tuple[str, ...]
    assumptions: tuple[str, ...]
    lower_is_better: bool = False
    extra_missing_flags: tuple[str, ...] = ()


GAP_SPECS: tuple[GapSpec, ...] = (
    GapSpec(
        gap_id="non_embiid_center_minutes",
        gap_name="Non-Embiid center minutes",
        gap_category="center_depth",
        source_blueprint="star_center_anchor",
        metric="number_of_big_minutes_players",
        roster_slot_needed="non_embiid_center_minutes",
        skill_requirements=("rim_protection", "defensive_rebounding", "role_stability"),
        lineup_contexts=("Embiid off", "regular season non-star minutes"),
        why_it_matters=(
            "Philadelphia cannot make every credible center minute depend on Embiid."
        ),
        playoff_failure_mode="Non-Embiid minutes collapse and force emergency lineups.",
        what_fixes_it=(
            "credible backup center",
            "matchup big",
            "regular-season insurance",
        ),
        what_does_not_fix_it=(
            "an expensive center expected to start next to Embiid without "
            "two-big evidence",
            "a center with no defensive rebounding or rim-protection signal",
        ),
        assumptions=("Embiid blocks the normal starting-center slot.",),
    ),
    GapSpec(
        gap_id="backup_center_stability",
        gap_name="Backup center stability",
        gap_category="center_depth",
        source_blueprint="star_center_anchor",
        metric="backup_center_quality_proxy",
        roster_slot_needed="backup_center",
        skill_requirements=("rim_protection", "defensive_rebounding", "low_usage_fit"),
        lineup_contexts=("Embiid off", "bench units"),
        why_it_matters=(
            "A contender with a center anchor still needs stable non-star center "
            "minutes."
        ),
        playoff_failure_mode=(
            "Backup center minutes become a target in second quarters."
        ),
        what_fixes_it=(
            "low-mistake backup big",
            "defensive rebounder",
            "rim protector",
        ),
        what_does_not_fix_it=(
            "a high-usage big who needs starter touches",
            "a regular-season-only body with no playoff defensive evidence",
        ),
        assumptions=("Backup-center value is measured as a public-stats proxy.",),
    ),
    GapSpec(
        gap_id="rim_protection_without_embiid",
        gap_name="Rim protection without Embiid",
        gap_category="defense",
        source_blueprint="defense_first",
        metric="def_rating",
        roster_slot_needed="non_embiid_center_minutes",
        skill_requirements=("rim_protection", "size", "defensive_rebounding"),
        lineup_contexts=("Embiid off", "bench defense", "matchup big lineups"),
        why_it_matters=(
            "Playoff offenses attack the rim when the anchor is off the floor."
        ),
        playoff_failure_mode="Opponents get clean paint touches whenever Embiid rests.",
        what_fixes_it=(
            "verified rim protector",
            "big with block/rebound/size evidence",
        ),
        what_does_not_fix_it=(
            "a center with low block and rebound evidence",
            "a defensive label based only on steals",
        ),
        assumptions=("Team defensive rating is a broad proxy, not a rim-only metric.",),
        lower_is_better=True,
    ),
    GapSpec(
        gap_id="defensive_rebounding_without_embiid",
        gap_name="Defensive rebounding without Embiid",
        gap_category="rebounding",
        source_blueprint="defense_first",
        metric="defensive_rebounding_proxy",
        roster_slot_needed="rebounding_forward",
        skill_requirements=("defensive_rebounding", "minutes_context"),
        lineup_contexts=("Embiid off", "small-ball groups", "closing rebounding"),
        why_it_matters=(
            "One-shot defense matters more when every playoff possession slows down."
        ),
        playoff_failure_mode="Good defensive possessions die on second chances.",
        what_fixes_it=(
            "defensive rebounder with minutes evidence",
            "size at forward or center",
        ),
        what_does_not_fix_it=(
            "a small guard who rebounds only in tiny samples",
            "a big with role or availability uncertainty",
        ),
        assumptions=(
            "Public rebound rate is used because lineup rebounding is not complete.",
        ),
    ),
    GapSpec(
        gap_id="wing_defense",
        gap_name="Wing defense",
        gap_category="defense",
        source_blueprint="wing_depth_switchable",
        metric="number_of_playable_wings",
        roster_slot_needed="defensive_forward",
        skill_requirements=("wing_defense_proxy", "switchability_proxy", "size"),
        lineup_contexts=(
            "Embiid lineups",
            "George insurance",
            "playoff matchup defense",
        ),
        why_it_matters=(
            "Deep playoff teams need multiple wings who can survive matchups."
        ),
        playoff_failure_mode="One weak wing defender lets opponents control matchups.",
        what_fixes_it=("switchable wing", "size plus defensive-event evidence"),
        what_does_not_fix_it=(
            "a wing label without defensive evidence",
            "a small offensive player who creates another matchup target",
        ),
        assumptions=("Wing counts use NBA.com bio positions as a structural proxy.",),
    ),
    GapSpec(
        gap_id="point_of_attack_defense",
        gap_name="Point-of-attack defense",
        gap_category="defense",
        source_blueprint="defense_first",
        metric="def_rating",
        roster_slot_needed="point_of_attack_defender",
        skill_requirements=("point_of_attack_defense_proxy", "defensive_event_proxy"),
        lineup_contexts=("Maxey lineups", "bench guard defense", "late-clock defense"),
        why_it_matters="Maxey's offensive burden makes guard defensive cover valuable.",
        playoff_failure_mode=(
            "Opposing guards force rotations before Embiid can protect the rim."
        ),
        what_fixes_it=(
            "guard or wing with POA evidence",
            "low-usage defender who can play",
        ),
        what_does_not_fix_it=(
            "a steals-only defensive case",
            "a high-usage guard who duplicates Maxey without defensive cover",
        ),
        assumptions=("POA defense requires later compatibility and skill evidence.",),
        lower_is_better=True,
    ),
    GapSpec(
        gap_id="role_player_shooting_volume",
        gap_name="Role-player shooting volume",
        gap_category="shooting",
        source_blueprint="shooting_pressure",
        metric="number_of_rotation_shooters",
        roster_slot_needed="low_usage_spacer",
        skill_requirements=(
            "spot_up_spacing",
            "shooting_gravity",
            "sample_reliability",
        ),
        lineup_contexts=("Embiid post touches", "Maxey drives", "George wing lineups"),
        why_it_matters="Stars need defenders punished for helping off role players.",
        playoff_failure_mode="Defenses load the paint and ignore low-volume shooters.",
        what_fixes_it=("high-volume catch-and-shoot player", "movement shooter"),
        what_does_not_fix_it=(
            "a good percentage on low attempts",
            "a player defenses still help off in playoff lineups",
        ),
        assumptions=("Volume is required before the model can claim real spacing.",),
    ),
    GapSpec(
        gap_id="real_spacing_vs_fake_spacing",
        gap_name="Real spacing vs fake spacing",
        gap_category="shooting",
        source_blueprint="shooting_pressure",
        metric="role_player_spacing_proxy",
        roster_slot_needed="low_usage_spacer",
        skill_requirements=("spot_up_spacing", "shooting_gravity", "fake_spacing_risk"),
        lineup_contexts=("Embiid lineups", "Maxey downhill lineups"),
        why_it_matters=(
            "A shooter has to change defensive behavior, not just own a percentage."
        ),
        playoff_failure_mode=(
            "Opponents ignore non-threatening shooters and crowd the stars."
        ),
        what_fixes_it=(
            "attempt volume",
            "quick-trigger role shooting",
            "credible accuracy",
        ),
        what_does_not_fix_it=(
            "low-volume accuracy with no gravity",
            "a reluctant shooter listed as a spacer",
        ),
        assumptions=("Shot-location detail is not fully sourced yet.",),
        extra_missing_flags=("shot_profile_missing",),
    ),
    GapSpec(
        gap_id="movement_shooting",
        gap_name="Movement shooting",
        gap_category="shooting",
        source_blueprint="shooting_pressure",
        metric="estimated_shooting_pressure",
        roster_slot_needed="movement_shooter",
        skill_requirements=(
            "movement_shooting",
            "shooting_gravity",
            "sample_reliability",
        ),
        lineup_contexts=(
            "Embiid handoff actions",
            "bench offense",
            "late-clock spacing",
        ),
        why_it_matters=(
            "Movement shooting changes coverage before the ball reaches the star."
        ),
        playoff_failure_mode=(
            "Half-court possessions stagnate when spacing is stationary."
        ),
        what_fixes_it=("movement shooter", "high-volume quick-trigger shooter"),
        what_does_not_fix_it=(
            "stationary low-volume shooter",
            "shooter with no role evidence",
        ),
        assumptions=(
            "Movement shooting uses proxies until shot-type data is available.",
        ),
        extra_missing_flags=("shot_type_data_missing",),
    ),
    GapSpec(
        gap_id="low_usage_connector_play",
        gap_name="Low-usage connector play",
        gap_category="offense",
        source_blueprint="balanced_two_way",
        metric="turnover_control_proxy",
        roster_slot_needed="low_usage_connector",
        skill_requirements=("connector_passing", "low_usage_fit", "ball_security"),
        lineup_contexts=("Embiid lineups", "George lineups", "bench stabilization"),
        why_it_matters=(
            "The roster needs players who keep offense alive without taking touches."
        ),
        playoff_failure_mode="Role players either stall possessions or overhandle.",
        what_fixes_it=(
            "low-usage passer",
            "quick decision-maker",
            "low-turnover connector",
        ),
        what_does_not_fix_it=("high-usage creator", "passer with turnover problems"),
        assumptions=("Connector play uses assist and turnover proxies.",),
    ),
    GapSpec(
        gap_id="bench_creation",
        gap_name="Bench creation",
        gap_category="creation",
        source_blueprint="creator_committee",
        metric="bench_creation_proxy",
        roster_slot_needed="bench_creator",
        skill_requirements=("secondary_creation", "ball_security", "role_stability"),
        lineup_contexts=("non-Maxey minutes", "bench groups", "regular season offense"),
        why_it_matters=(
            "The offense should not collapse whenever the primary creators sit."
        ),
        playoff_failure_mode=(
            "Bench units cannot create a shot without overtaxing stars."
        ),
        what_fixes_it=(
            "secondary creator",
            "bench guard with passing and turnover evidence",
        ),
        what_does_not_fix_it=(
            "high-usage guard with Maxey overlap",
            "scorer with no passing",
        ),
        assumptions=(
            "Bench creation is a player-season proxy, not lineup play-by-play.",
        ),
    ),
    GapSpec(
        gap_id="turnover_control",
        gap_name="Turnover control",
        gap_category="offense",
        source_blueprint="balanced_two_way",
        metric="turnover_control_proxy",
        roster_slot_needed="low_usage_connector",
        skill_requirements=("ball_security", "low_usage_fit"),
        lineup_contexts=("playoff half court", "bench units", "closing possessions"),
        why_it_matters=(
            "Turnovers feed transition chances and erase star-created advantages."
        ),
        playoff_failure_mode=(
            "Low-margin playoff possessions get wasted by role-player mistakes."
        ),
        what_fixes_it=("low-turnover connector", "simple-decision role player"),
        what_does_not_fix_it=(
            "risky passer",
            "creator whose value depends on high usage",
        ),
        assumptions=("Turnover control combines team and player turnover proxies.",),
    ),
    GapSpec(
        gap_id="playoff_playable_size",
        gap_name="Playoff-playable size",
        gap_category="size",
        source_blueprint="wing_depth_switchable",
        metric="lineup_versatility_proxy",
        roster_slot_needed="defensive_forward",
        skill_requirements=("size", "switchability_proxy", "playoff_portability_base"),
        lineup_contexts=("switching lineups", "George insurance", "closing options"),
        why_it_matters="Playoff matchups punish small or single-position depth.",
        playoff_failure_mode=(
            "The rotation runs out of playable size against bigger wings."
        ),
        what_fixes_it=(
            "large wing",
            "switchable forward",
            "playoff-credible combo forward",
        ),
        what_does_not_fix_it=("small guard depth", "big who cannot guard in space"),
        assumptions=("Playable-size counts are position and role proxies.",),
    ),
    GapSpec(
        gap_id="lineup_versatility",
        gap_name="Lineup versatility",
        gap_category="versatility",
        source_blueprint="wing_depth_switchable",
        metric="lineup_versatility_proxy",
        roster_slot_needed="3_and_d_wing",
        skill_requirements=("switchability_proxy", "low_usage_fit", "shooting_gravity"),
        lineup_contexts=("closing lineups", "bench groups", "matchup-specific series"),
        why_it_matters="A contender needs counters when one lineup gets targeted.",
        playoff_failure_mode="The same lineup flaw repeats every game of a series.",
        what_fixes_it=("multi-position wing", "two-way forward", "spacer with defense"),
        what_does_not_fix_it=(
            "single-skill specialist",
            "player with no playoff role path",
        ),
        assumptions=(
            "Versatility is structural until lineup/on-off data is expanded.",
        ),
    ),
    GapSpec(
        gap_id="age_durability_insurance",
        gap_name="Age and durability insurance",
        gap_category="availability",
        source_blueprint="depth_heavy",
        metric="depth_balance_proxy",
        roster_slot_needed="regular_season_depth",
        skill_requirements=("role_stability", "sample_reliability", "minutes_context"),
        lineup_contexts=("regular season", "George/Embiid missed-game coverage"),
        why_it_matters=(
            "Older and high-burden cores need playable depth before the playoffs."
        ),
        playoff_failure_mode=(
            "The roster reaches the postseason without stable rotation reps."
        ),
        what_fixes_it=(
            "reliable depth",
            "low-risk role player",
            "positionally relevant minutes",
        ),
        what_does_not_fix_it=(
            "development-only flier",
            "player with unknown availability",
        ),
        assumptions=("Medical and injury-risk data are not fully sourced.",),
        extra_missing_flags=("injury_status_missing", "medical_risk_missing"),
    ),
    GapSpec(
        gap_id="usage_balance",
        gap_name="Usage balance",
        gap_category="offense",
        source_blueprint="balanced_two_way",
        metric="star_dependency_proxy",
        roster_slot_needed="secondary_creator",
        skill_requirements=(
            "secondary_creation",
            "low_usage_fit",
            "usage_compatibility",
        ),
        lineup_contexts=("Maxey lineups", "George lineups", "non-star minutes"),
        why_it_matters=(
            "The team needs help without creating another star-touch conflict."
        ),
        playoff_failure_mode=(
            "Too much offense depends on one creator or too many players need touches."
        ),
        what_fixes_it=("secondary creator", "connector who can scale down usage"),
        what_does_not_fix_it=(
            "high-usage guard with Maxey overlap",
            "non-shooter creator",
        ),
        assumptions=("Usage balance uses usage-share proxies.",),
        lower_is_better=True,
    ),
    GapSpec(
        gap_id="closing_lineup_flexibility",
        gap_name="Closing lineup flexibility",
        gap_category="playoff_fit",
        source_blueprint="balanced_two_way",
        metric="playoff_portability_proxy",
        roster_slot_needed="playoff_rotation_piece",
        skill_requirements=(
            "playoff_portability_base",
            "low_usage_fit",
            "defense_or_spacing",
        ),
        lineup_contexts=(
            "closing five",
            "series counters",
            "late-game defense/offense swaps",
        ),
        why_it_matters="The best target should be playable when matchups tighten.",
        playoff_failure_mode=(
            "A regular-season contributor becomes unusable in closing minutes."
        ),
        what_fixes_it=(
            "two-way role player",
            "spacer who can defend",
            "defender who can shoot enough",
        ),
        what_does_not_fix_it=(
            "regular-season-only depth",
            "specialist who gets hunted",
        ),
        assumptions=(
            "Closing value is a proxy until lineup-level playoff data is complete.",
        ),
    ),
    GapSpec(
        gap_id="regular_season_depth",
        gap_name="Regular-season depth",
        gap_category="depth",
        source_blueprint="depth_heavy",
        metric="depth_balance_proxy",
        roster_slot_needed="regular_season_depth",
        skill_requirements=("minutes_context", "role_stability"),
        lineup_contexts=("82-game rotation", "injury coverage", "load management"),
        why_it_matters=(
            "Depth protects the core from carrying every regular-season possession."
        ),
        playoff_failure_mode=(
            "The team gets to the playoffs with unstable or overused lineups."
        ),
        what_fixes_it=(
            "competent depth",
            "clear low-minute role",
            "low-cost insurance",
        ),
        what_does_not_fix_it=(
            "expensive player with no playoff pathway",
            "unknown-status candidate",
        ),
        assumptions=("Depth is useful but cannot by itself create a Priority Target.",),
    ),
    GapSpec(
        gap_id="stretch_forward_option",
        gap_name="Stretch-forward option",
        gap_category="shooting_size",
        source_blueprint="shooting_pressure",
        metric="role_player_spacing_proxy",
        roster_slot_needed="stretch_forward",
        skill_requirements=("spot_up_spacing", "size", "low_usage_fit"),
        lineup_contexts=("Embiid spacing", "George insurance", "frontcourt counters"),
        why_it_matters=(
            "A bigger spacer can preserve size while keeping the paint open."
        ),
        playoff_failure_mode=(
            "Small spacing lineups give up too much size, or big lineups shrink "
            "spacing."
        ),
        what_fixes_it=("forward-sized shooter", "stretch big with real volume"),
        what_does_not_fix_it=(
            "low-volume big shooter",
            "small guard shooter solving a forward gap",
        ),
        assumptions=(
            "Stretch-forward status requires player-level shooting evidence later.",
        ),
    ),
    GapSpec(
        gap_id="matchup_big_option",
        gap_name="Matchup big option",
        gap_category="center_depth",
        source_blueprint="dual_big",
        metric="number_of_big_minutes_players",
        roster_slot_needed="matchup_big",
        skill_requirements=("rim_protection", "defensive_rebounding", "role_stability"),
        lineup_contexts=(
            "specific playoff matchups",
            "regular-season size",
            "Embiid off",
        ),
        why_it_matters=(
            "Some series require extra size even if the starting center slot is "
            "blocked."
        ),
        playoff_failure_mode=(
            "The roster has no counter when size and rebounding swing a matchup."
        ),
        what_fixes_it=(
            "matchup big",
            "mobile big",
            "backup center with a narrow clear role",
        ),
        what_does_not_fix_it=(
            "starting-center projection next to Embiid without two-big proof",
            "expensive depth big with low feasibility",
        ),
        assumptions=(
            "Matchup-big value is scenario-dependent, not a default starter claim.",
        ),
    ),
)


def build_gap_model(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    roster_world_path: str | Path = ROSTER_WORLD_PATH,
    contender_blueprints_path: str | Path = CONTENDER_BLUEPRINTS_PATH,
    team_fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    current_gap_report_path: str | Path = CURRENT_GAP_REPORT_PATH,
    output_path: str | Path = SIXERS_GAP_MODEL_PATH,
    report_path: str | Path = SIXERS_GAP_MODEL_REPORT_PATH,
) -> GapModelResult:
    """Build the role-specific Sixers gap model."""
    normalized_team = str(team or "PHI").upper()
    context = context or {}
    roster_world = pd.read_parquet(roster_world_path)
    blueprints = pd.read_parquet(contender_blueprints_path)
    team_fingerprints = pd.read_parquet(team_fingerprints_path)
    current_gaps = _optional_parquet(current_gap_report_path)

    current_team = _latest_team_row(team_fingerprints, normalized_team)
    current_metrics = _current_metrics(roster_world, current_team)
    percentile_lookup = _current_gap_percentiles(current_gaps)
    rows = [
        _gap_row(
            spec,
            current_metrics,
            blueprints,
            percentile_lookup,
            team=normalized_team,
            context_mode=str(context.get("context_mode") or "unknown"),
        )
        for spec in GAP_SPECS
    ]
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["severity", "gap_id"], ascending=[False, True]
    ).reset_index(drop=True)

    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    report.write_text(_render_report(frame), encoding="utf-8")

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                roster_world_path,
                contender_blueprints_path,
                team_fingerprints_path,
                current_gap_report_path,
            ),
            upstream_artifacts=(
                roster_world_path,
                contender_blueprints_path,
                team_fingerprints_path,
                current_gap_report_path,
            ),
            known_limitations=(
                "Gap values use public-data proxies, not private scouting grades.",
                "Candidate need-match credit still requires player-level skill "
                "evidence.",
                "Injury, medical, and true trade-availability data are incomplete.",
            ),
        )

    severe = int((frame["severity"] >= 35).sum())
    return GapModelResult(
        gaps=len(frame),
        critical_or_significant=severe,
        output_path=output,
        report_path=report,
    )


def _optional_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _latest_team_row(team_fingerprints: pd.DataFrame, team: str) -> pd.Series:
    team_rows = team_fingerprints[team_fingerprints["team_abbr"] == team].copy()
    if team_rows.empty:
        return pd.Series(dtype="object")
    season = sorted(team_rows["season"].astype(str).unique())[-1]
    return team_rows[team_rows["season"].astype(str) == season].iloc[0]


def _current_metrics(
    roster_world: pd.DataFrame, phi_team: pd.Series
) -> dict[str, float]:
    roster = roster_world.copy()
    roster["current_minutes"] = _num(roster, "current_minutes")
    roster["usage_rate"] = _num(roster, "usage_rate")
    roster["three_pa"] = _num(roster, "three_pa")
    roster["three_pa_rate"] = _num(roster, "three_pa_rate")
    roster["assist_pct"] = _num(roster, "assist_pct")
    roster["rebound_pct"] = _num(roster, "rebound_pct")
    roster["turnover_pct"] = _num(roster, "turnover_pct")

    rotation = roster[roster["current_minutes"] >= 700].copy()
    positions = rotation["position"].fillna("").astype(str)
    wings = rotation[positions.str.contains("F|G-F|F-G", regex=True)]
    bigs = rotation[positions.str.contains("C")]
    shooters = rotation[
        (rotation["three_pa"] >= 150)
        | ((rotation["three_pa_rate"] >= 0.35) & (rotation["current_minutes"] >= 900))
    ]
    bench = roster.sort_values("current_minutes", ascending=False).iloc[5:]
    usage_weight = roster["usage_rate"] * roster["current_minutes"]
    total_usage = float(usage_weight.sum()) or 1.0
    usage_shares = (usage_weight / total_usage).sort_values(ascending=False)

    metrics = {
        "top_1_usage_share": _share(usage_shares, 0),
        "top_2_usage_share": _share(usage_shares, 1),
        "top_3_usage_share": _share(usage_shares, 2),
        "number_of_rotation_shooters": float(len(shooters)),
        "number_of_playable_wings": float(len(wings)),
        "number_of_big_minutes_players": float(len(bigs)),
        "backup_center_quality_proxy": _backup_center_proxy(bigs),
        "bench_creation_proxy": float(
            bench["assist_pct"].head(6).mean() if not bench.empty else 0
        ),
        "role_player_spacing_proxy": float(
            shooters["three_pa_rate"].mean() if not shooters.empty else 0
        ),
        "depth_balance_proxy": float(len(rotation)),
        "star_dependency_proxy": float(usage_shares.head(2).sum()),
        "lineup_versatility_proxy": float(len(wings) + len(shooters)),
        "defensive_rebounding_proxy": _team_metric(
            phi_team, "defensive_rebounding_percentage"
        ),
        "turnover_control_proxy": 1.0 - _team_metric(phi_team, "turnover_percentage"),
        "playoff_portability_proxy": _team_metric(
            phi_team, "estimated_two_way_balance"
        ),
        "estimated_shooting_pressure": _team_metric(
            phi_team, "estimated_shooting_pressure"
        ),
        "def_rating": _team_metric(phi_team, "defensive_rating"),
        "non_embiid_center_minutes": float(
            bigs[~bigs["player_name"].eq("Joel Embiid")]["current_minutes"].sum()
        ),
        "non_embiid_center_rebound_pct": float(
            bigs[~bigs["player_name"].eq("Joel Embiid")]["rebound_pct"].mean()
            if len(bigs[~bigs["player_name"].eq("Joel Embiid")])
            else 0
        ),
    }
    return metrics


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)


def _share(values: pd.Series, idx: int) -> float:
    if len(values) <= idx:
        return 0.0
    return round(float(values.iloc[idx]), 3)


def _team_metric(row: pd.Series, column: str) -> float:
    if row.empty or column not in row:
        return 0.0
    value = pd.to_numeric(row[column], errors="coerce")
    if pd.isna(value):
        return 0.0
    return float(value)


def _backup_center_proxy(bigs: pd.DataFrame) -> float:
    if bigs.empty or len(bigs) < 2:
        return 0.0
    ranked = bigs.sort_values("current_minutes", ascending=False).iloc[1:]
    minutes = ranked["current_minutes"].sum()
    if not minutes:
        return 0.0
    return float((ranked["rebound_pct"] * ranked["current_minutes"]).sum() / minutes)


def _current_gap_percentiles(current_gaps: pd.DataFrame) -> dict[str, float]:
    if current_gaps.empty or "category_key" not in current_gaps.columns:
        return {}
    key_map = {
        "role_player_shooting_volume": "shooting_pressure",
        "real_spacing_vs_fake_spacing": "shooting_pressure",
        "movement_shooting": "shooting_pressure",
        "rim_protection_without_embiid": "defense",
        "point_of_attack_defense": "defense",
        "defensive_rebounding_without_embiid": "rebounding",
        "regular_season_depth": "bench_rotation_depth",
    }
    out: dict[str, float] = {}
    for gap_id, category in key_map.items():
        match = current_gaps[current_gaps["category_key"] == category]
        if not match.empty and "percentile" in match.columns:
            out[gap_id] = float(match.iloc[0]["percentile"])
    return out


def _gap_row(
    spec: GapSpec,
    current_metrics: dict[str, float],
    blueprints: pd.DataFrame,
    percentile_lookup: dict[str, float],
    *,
    team: str,
    context_mode: str,
) -> dict[str, Any]:
    blueprint = _blueprint_row(blueprints, spec.source_blueprint)
    current = float(current_metrics.get(spec.metric, 0.0))
    reference = float(pd.to_numeric(blueprint.get(spec.metric, 0.0), errors="coerce"))
    severity = _severity(current, reference, lower_is_better=spec.lower_is_better)
    missing = _missing_flags(spec, current, reference)
    evidence = {
        "metric": spec.metric,
        "sixers_current_value": round(current, 3),
        "contender_reference_value": round(reference, 3),
        "source_blueprint": spec.source_blueprint,
        "roster_slot_needed": spec.roster_slot_needed,
        "skill_requirements": list(spec.skill_requirements),
        "lineup_contexts": list(spec.lineup_contexts),
    }
    return {
        "team_abbr": team,
        "gap_id": spec.gap_id,
        "gap_name": spec.gap_name,
        "gap_category": spec.gap_category,
        "source_blueprint": spec.source_blueprint,
        "sixers_current_value": round(current, 3),
        "contender_reference_value": round(reference, 3),
        "contender_percentile": percentile_lookup.get(spec.gap_id),
        "severity": severity,
        "confidence": _confidence(missing),
        "roster_slot_needed": spec.roster_slot_needed,
        "skill_requirements": json.dumps(list(spec.skill_requirements)),
        "lineup_contexts": json.dumps(list(spec.lineup_contexts)),
        "why_it_matters": spec.why_it_matters,
        "playoff_failure_mode": spec.playoff_failure_mode,
        "what_fixes_it": json.dumps(list(spec.what_fixes_it)),
        "what_does_not_fix_it": json.dumps(list(spec.what_does_not_fix_it)),
        "evidence": json.dumps(evidence, sort_keys=True),
        "assumptions": "; ".join(spec.assumptions),
        "source_url": "",
        "source_note": (
            f"roster_world_{team.lower()} + contender_blueprints + "
            f"team_fingerprints; context_mode={context_mode}"
        ),
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(missing) if missing else "none",
    }


def _blueprint_row(blueprints: pd.DataFrame, blueprint_id: str) -> pd.Series:
    match = blueprints[blueprints["blueprint_id"] == blueprint_id]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _severity(current: float, reference: float, *, lower_is_better: bool) -> float:
    if reference == 0:
        return 0.0
    if lower_is_better:
        gap = max(0.0, current - reference)
    else:
        gap = max(0.0, reference - current)
    return round(min(100.0, (gap / abs(reference)) * 100), 2)


def _missing_flags(spec: GapSpec, current: float, reference: float) -> list[str]:
    flags = list(spec.extra_missing_flags)
    if reference == 0:
        flags.append("blueprint_reference_missing")
    if current == 0 and spec.metric not in {"def_rating"}:
        flags.append("sixers_current_proxy_zero")
    return flags


def _confidence(missing_flags: list[str]) -> str:
    if any("missing" in flag for flag in missing_flags):
        return "low"
    if missing_flags:
        return "medium"
    return "high"


def _render_report(gaps: pd.DataFrame) -> str:
    lines = [
        "# Sixers Gap Model",
        "",
        "Role-specific gaps built from the current PHI roster world and structural "
        "contender blueprints.",
        "",
        "| Gap | Slot Needed | Severity | Confidence | What Fixes It |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in gaps.to_dict(orient="records"):
        fixes = ", ".join(json.loads(row["what_fixes_it"])[:3])
        lines.append(
            f"| {row['gap_name']} | {row['roster_slot_needed']} | "
            f"{row['severity']} | {row['confidence']} | {fixes} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- These are not generic player-quality categories.",
            "- A candidate only gets need-match credit when later skill-profile "
            "evidence allows the matching claim.",
            "- Center gaps do not open the starting-center slot because Embiid is a "
            "locked core player.",
            "- Missing injury, shot-type, and private availability data lower "
            "confidence instead of being invented.",
        ]
    )
    return "\n".join(lines)
