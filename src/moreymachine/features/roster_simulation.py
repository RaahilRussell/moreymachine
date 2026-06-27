"""Roster slot and minutes-context simulation for candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.compatibility_matrix import CANDIDATE_CORE_COMPATIBILITY_PATH
from moreymachine.features.gap_model import SIXERS_GAP_MODEL_PATH
from moreymachine.features.player_skill_profiles import PLAYER_SKILL_PROFILES_PATH
from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    FEATURES_DATA_DIR,
    REPORTS_DATA_DIR,
)

CANDIDATE_ROSTER_SIMULATION_PATH = (
    FEATURES_DATA_DIR / "candidate_roster_simulation.parquet"
)
ROSTER_SIMULATION_EXAMPLES_PATH = REPORTS_DATA_DIR / "roster_simulation_examples.md"


@dataclass(frozen=True)
class RosterSimulationResult:
    """Summary from roster-slot simulation."""

    rows: int
    no_clear_role: int
    center_overlap_flags: int
    starter_possible: int
    output_path: Path
    report_path: Path


def simulate_roster_slots(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    skill_profiles_path: str | Path = PLAYER_SKILL_PROFILES_PATH,
    compatibility_path: str | Path = CANDIDATE_CORE_COMPATIBILITY_PATH,
    gap_model_path: str | Path = SIXERS_GAP_MODEL_PATH,
    output_path: str | Path = CANDIDATE_ROSTER_SIMULATION_PATH,
    report_path: str | Path = ROSTER_SIMULATION_EXAMPLES_PATH,
) -> RosterSimulationResult:
    """Simulate likely PHI roster slots for every acquisition candidate."""
    target_team = str(team or "PHI").upper()
    context = context or {}
    candidates = pd.read_parquet(candidate_universe_path)
    skills = pd.read_parquet(skill_profiles_path)
    compatibility = pd.read_parquet(compatibility_path)
    gaps = pd.read_parquet(gap_model_path)
    frame = candidates.merge(
        skills, on="player_id", how="left", suffixes=("", "_skill")
    )
    gap_priority = _slot_priority(gaps)
    compatibility_lookup = _compatibility_lookup(compatibility)
    rows = [
        _simulation_row(
            row,
            compatibility_lookup,
            gap_priority,
            target_team=target_team,
            context_mode=str(context.get("context_mode") or "unknown"),
        )
        for row in frame.to_dict(orient="records")
    ]
    out = pd.DataFrame(rows)

    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    report.write_text(_render_report(out), encoding="utf-8")

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                candidate_universe_path,
                skill_profiles_path,
                compatibility_path,
                gap_model_path,
            ),
            upstream_artifacts=(
                candidate_universe_path,
                skill_profiles_path,
                compatibility_path,
                gap_model_path,
            ),
            known_limitations=(
                "Minutes contexts are scenario bands, not coaching projections.",
                "True lineup availability and private team intent are not sourced.",
            ),
        )

    return RosterSimulationResult(
        rows=len(out),
        no_clear_role=int(out["no_clear_role"].sum()),
        center_overlap_flags=int(out["embiid_overlap_flag"].sum()),
        starter_possible=int(out["starter_possible"].sum()),
        output_path=output,
        report_path=report,
    )


def _slot_priority(gaps: pd.DataFrame) -> dict[str, float]:
    priority = {}
    for row in gaps.to_dict(orient="records"):
        slot = str(row.get("roster_slot_needed") or "")
        priority[slot] = max(float(row.get("severity") or 0), priority.get(slot, 0))
    return priority


def _compatibility_lookup(frame: pd.DataFrame) -> dict[int, dict[str, dict[str, Any]]]:
    lookup: dict[int, dict[str, dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        candidate_id = int(row["candidate_id"])
        player = str(row["sixers_player_name"])
        lookup.setdefault(candidate_id, {})[player] = row
    return lookup


def _simulation_row(
    row: dict[str, Any],
    compatibility_lookup: dict[int, dict[str, dict[str, Any]]],
    gap_priority: dict[str, float],
    *,
    target_team: str,
    context_mode: str,
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    position = str(row.get("position") or row.get("position_skill") or "")
    candidate_type = str(row.get("candidate_type") or "")
    is_center = "C" in position
    is_wing = "F" in position or "G-F" in position
    is_guard = "G" in position
    slots = _possible_slots(row, position, candidate_type)
    blocked_slots = []
    contradiction_flags = []
    redundancy_flags = []

    compat = compatibility_lookup.get(player_id, {})
    embiid = compat.get("Joel Embiid", {})
    maxey = compat.get("Tyrese Maxey", {})
    george = compat.get("Paul George", {})
    embiid_flags = _json_list(embiid.get("conflict_flags"))
    maxey_flags = _json_list(maxey.get("conflict_flags"))
    george_flags = _json_list(george.get("conflict_flags"))

    embiid_overlap = "embiid_center_overlap" in embiid_flags
    maxey_overlap = "maxey_usage_overlap" in maxey_flags
    george_overlap = bool(george_flags)
    two_big = _two_big_compatible(row, is_center, embiid_flags)

    if is_center:
        blocked_slots.append("starting_center")
        if not two_big:
            contradiction_flags.append("normal_starting_center_slot_blocked_by_embiid")
    if maxey_overlap:
        blocked_slots.append("high_usage_primary_guard")
        contradiction_flags.append("maxey_usage_overlap")
    if candidate_type in {"star_unrealistic", "core_unavailable"}:
        slots = ["theoretical_star_upgrade"]
        contradiction_flags.append("theoretical_or_unavailable_candidate")
    if candidate_type in {"missing_contract_status", "manual_review_needed"}:
        contradiction_flags.append("candidate_status_manual_review_required")

    primary = _choose_primary_slot(slots, gap_priority)
    no_clear = primary == "no_clear_role"
    if no_clear:
        contradiction_flags.append("no_clear_role")
    if primary == "regular_season_depth":
        redundancy_flags.append("regular_season_depth_only")
    if is_center and primary == "starting_center":
        primary = "non_embiid_center_minutes"
        contradiction_flags.append("starting_center_reassigned_to_non_embiid_minutes")

    starter_possible = _starter_possible(row, primary, is_center, two_big)
    closing_possible = _closing_possible(
        row, primary, contradiction_flags, is_center, two_big
    )
    playoff_possible = _playoff_rotation_possible(row, primary, contradiction_flags)
    regular_only = primary == "regular_season_depth" or (
        not playoff_possible and not no_clear
    )
    matchup_dependent = primary in {
        "matchup_big",
        "double_big_stretch_partner",
        "regular_season_depth",
    }

    likely_contexts = _lineup_contexts(primary, is_center, is_guard, is_wing)
    bad_contexts = _bad_contexts(primary, is_center, maxey_overlap, two_big)
    expected_role = _expected_role(primary, is_center, two_big)
    minutes_context = _minutes_context(primary, playoff_possible, regular_only)
    role_confidence = _role_confidence(no_clear, contradiction_flags, row)
    possible_slots = _ordered_unique(slots)
    secondary_slots = [slot for slot in possible_slots if slot != primary]
    evidence = {
        "candidate_type": candidate_type,
        "position": position,
        "possible_slots": possible_slots,
        "embiid_flags": embiid_flags,
        "maxey_flags": maxey_flags,
        "george_flags": george_flags,
        "claim_allowed": {
            "spacing": _bool(row, "spot_up_spacing_claim_allowed"),
            "shooting_gravity": _bool(row, "shooting_gravity_claim_allowed"),
            "fake_spacing_risk": _bool(row, "fake_spacing_risk_claim_allowed"),
            "movement": _bool(row, "movement_shooting_claim_allowed"),
            "rim_protection": _bool(row, "rim_protection_claim_allowed"),
            "defensive_rebounding": _bool(row, "defensive_rebounding_claim_allowed"),
            "wing_defense": _bool(row, "wing_defense_proxy_claim_allowed"),
            "poa_defense": _bool(row, "point_of_attack_defense_proxy_claim_allowed"),
            "switchability": _bool(row, "switchability_proxy_claim_allowed"),
            "secondary_creation": _bool(row, "secondary_creation_claim_allowed"),
            "connector": _bool(row, "connector_passing_claim_allowed"),
            "ball_security": _bool(row, "ball_security_claim_allowed"),
            "low_usage": _bool(row, "low_usage_fit_claim_allowed"),
            "playoff_portability": _bool(row, "playoff_portability_base_claim_allowed"),
            "sample_reliability": _bool(row, "sample_reliability_claim_allowed"),
            "role_stability": _bool(row, "role_stability_claim_allowed"),
        },
    }
    missing = _missing_flags(row, contradiction_flags)

    return {
        "target_team": target_team,
        "player_id": player_id,
        "player_name": row.get("player_name"),
        "possible_roster_slots": json.dumps(possible_slots),
        "primary_roster_slot": primary,
        "secondary_roster_slots": json.dumps(secondary_slots),
        "blocked_slots": json.dumps(_ordered_unique(blocked_slots)),
        "role_on_phi": expected_role,
        "expected_role_on_phi": expected_role,
        "expected_minutes_context": minutes_context,
        "likely_lineup_contexts": json.dumps(likely_contexts),
        "bad_lineup_contexts": json.dumps(bad_contexts),
        "starter_possible": bool(starter_possible),
        "closing_lineup_possible": bool(closing_possible),
        "playoff_rotation_possible": bool(playoff_possible),
        "regular_season_depth_only": bool(regular_only),
        "matchup_dependent": bool(matchup_dependent),
        "two_big_compatible": bool(two_big),
        "no_clear_role": bool(no_clear),
        "embiid_overlap_flag": bool(embiid_overlap),
        "maxey_overlap_flag": bool(maxey_overlap),
        "george_overlap_flag": bool(george_overlap),
        "role_redundancy_flags": json.dumps(_ordered_unique(redundancy_flags)),
        "contradiction_flags": json.dumps(_ordered_unique(contradiction_flags)),
        "role_confidence": role_confidence,
        "data_evidence": json.dumps(evidence, sort_keys=True),
        "source": "candidate_universe + skill_profiles + compatibility + gap_model",
        "source_note": f"context_mode={context_mode}",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(missing) if missing else "none",
    }


def build_roster_simulation(
    **kwargs: Any,
) -> RosterSimulationResult:
    """Compatibility alias used by the team-scoped pipeline."""
    return simulate_roster_slots(**kwargs)


def _possible_slots(
    row: dict[str, Any], position: str, candidate_type: str
) -> list[str]:
    if candidate_type in {"star_unrealistic", "core_unavailable"}:
        return ["theoretical_star_upgrade"]
    slots: list[str] = []
    is_center = "C" in position
    is_forward = "F" in position
    if is_center:
        if _bool(row, "rim_protection_claim_allowed") or _bool(
            row, "defensive_rebounding_claim_allowed"
        ):
            slots.extend(["backup_center", "non_embiid_center_minutes", "matchup_big"])
        else:
            slots.append("regular_season_depth")
        if _bool(row, "spot_up_spacing_claim_allowed") and _bool(
            row, "switchability_proxy_claim_allowed"
        ):
            slots.append("double_big_stretch_partner")
    if is_forward and _bool(row, "spot_up_spacing_claim_allowed"):
        slots.append("stretch_forward")
    if _bool(row, "wing_defense_proxy_claim_allowed"):
        slots.extend(["defensive_forward", "3_and_d_wing"])
    if _bool(row, "point_of_attack_defense_proxy_claim_allowed"):
        slots.append("point_of_attack_defender")
    if _bool(row, "movement_shooting_claim_allowed"):
        slots.append("movement_shooter")
    if _bool(row, "spot_up_spacing_claim_allowed"):
        slots.append("low_usage_spacer")
    if _bool(row, "connector_passing_claim_allowed"):
        slots.append("low_usage_connector")
    if _bool(row, "secondary_creation_claim_allowed"):
        slots.append("secondary_creator")
        slots.append("bench_creator")
    if _bool(row, "defensive_rebounding_claim_allowed") and is_forward:
        slots.append("rebounding_forward")
    if not slots and _float(row.get("minutes")) >= 500:
        slots.append("regular_season_depth")
    if not slots:
        slots.append("no_clear_role")
    return slots


def _choose_primary_slot(slots: list[str], priority: dict[str, float]) -> str:
    ordered = _ordered_unique(slots)
    if "theoretical_star_upgrade" in ordered:
        return "theoretical_star_upgrade"
    if "no_clear_role" in ordered:
        return "no_clear_role"
    return max(ordered, key=lambda slot: (priority.get(slot, 0), _slot_tiebreak(slot)))


def _slot_tiebreak(slot: str) -> int:
    order = {
        "point_of_attack_defender": 20,
        "matchup_big": 19,
        "backup_center": 18,
        "non_embiid_center_minutes": 17,
        "movement_shooter": 16,
        "3_and_d_wing": 15,
        "defensive_forward": 14,
        "low_usage_spacer": 13,
        "bench_creator": 12,
        "secondary_creator": 11,
        "low_usage_connector": 10,
        "stretch_forward": 9,
        "rebounding_forward": 8,
        "regular_season_depth": 1,
    }
    return order.get(slot, 0)


def _two_big_compatible(
    row: dict[str, Any], is_center: bool, embiid_flags: list[str]
) -> bool:
    if not is_center:
        return False
    if "double_big_unproven" in embiid_flags:
        return False
    return _bool(row, "spot_up_spacing_claim_allowed") and (
        _bool(row, "switchability_proxy_claim_allowed")
        or _bool(row, "wing_defense_proxy_claim_allowed")
    )


def _starter_possible(
    row: dict[str, Any], primary: str, is_center: bool, two_big: bool
) -> bool:
    if primary in {"no_clear_role", "regular_season_depth", "theoretical_star_upgrade"}:
        return False
    if is_center:
        return two_big and primary == "double_big_stretch_partner"
    return (
        _float(row.get("minutes")) >= 1200
        and _bool(row, "sample_reliability_claim_allowed")
        and primary in {"3_and_d_wing", "defensive_forward", "point_of_attack_defender"}
    )


def _closing_possible(
    row: dict[str, Any],
    primary: str,
    contradiction_flags: list[str],
    is_center: bool,
    two_big: bool,
) -> bool:
    if primary in {"no_clear_role", "regular_season_depth", "theoretical_star_upgrade"}:
        return False
    if is_center and not two_big:
        return False
    if "maxey_usage_overlap" in contradiction_flags:
        return False
    return _bool(row, "playoff_portability_base_claim_allowed") and (
        _bool(row, "spot_up_spacing_claim_allowed")
        or _bool(row, "wing_defense_proxy_claim_allowed")
        or _bool(row, "rim_protection_claim_allowed")
    )


def _playoff_rotation_possible(
    row: dict[str, Any], primary: str, contradiction_flags: list[str]
) -> bool:
    if primary in {"no_clear_role", "theoretical_star_upgrade"}:
        return False
    if "candidate_status_manual_review_required" in contradiction_flags:
        return False
    return _bool(row, "sample_reliability_claim_allowed") and (
        _bool(row, "playoff_portability_base_claim_allowed")
        or primary in {"backup_center", "matchup_big", "point_of_attack_defender"}
    )


def _lineup_contexts(
    primary: str, is_center: bool, is_guard: bool, is_wing: bool
) -> list[str]:
    contexts = []
    if is_center:
        contexts.append("Embiid-off minutes")
    if is_guard:
        contexts.append("Maxey support or non-Maxey guard minutes")
    if is_wing:
        contexts.append("George/wing-depth lineups")
    if primary in {"movement_shooter", "low_usage_spacer", "stretch_forward"}:
        contexts.append("Embiid/Maxey spacing lineups")
    if primary in {"backup_center", "matchup_big"}:
        contexts.append("matchup or regular-season big minutes")
    return contexts or ["general rotation context"]


def _bad_contexts(
    primary: str, is_center: bool, maxey_overlap: bool, two_big: bool
) -> list[str]:
    contexts = []
    if is_center and not two_big:
        contexts.append("starting next to Embiid")
    if maxey_overlap:
        contexts.append("high-usage guard lineups with Maxey")
    if primary == "regular_season_depth":
        contexts.append("closing playoff lineups")
    return contexts


def _expected_role(primary: str, is_center: bool, two_big: bool) -> str:
    if primary == "theoretical_star_upgrade":
        return "theoretical star upgrade, not a realistic roster-slot projection"
    if primary == "no_clear_role":
        return "no clear Sixers role from current evidence"
    if is_center and not two_big:
        return "non-Embiid center minutes, backup center, or matchup big"
    mapping = {
        "double_big_stretch_partner": "scenario-dependent double-big partner",
        "matchup_big": "matchup big and regular-season size option",
        "backup_center": "backup center",
        "point_of_attack_defender": "point-of-attack defender next to Maxey",
        "movement_shooter": "movement shooter around Embiid and Maxey",
        "low_usage_spacer": "low-usage spacer",
        "3_and_d_wing": "3-and-D wing",
        "defensive_forward": "defensive forward",
        "bench_creator": "bench creator",
        "secondary_creator": "secondary creator",
        "regular_season_depth": "regular-season depth",
    }
    return mapping.get(primary, primary.replace("_", " "))


def _minutes_context(primary: str, playoff: bool, regular_only: bool) -> str:
    if primary == "no_clear_role":
        return "no reliable minutes projection"
    if regular_only:
        return "regular-season depth minutes; playoff role unproven"
    if playoff:
        return "playoff rotation candidate with role-specific minutes"
    return "scenario-dependent rotation minutes"


def _role_confidence(
    no_clear: bool, contradiction_flags: list[str], row: dict[str, Any]
) -> str:
    if no_clear or "candidate_status_manual_review_required" in contradiction_flags:
        return "low"
    if contradiction_flags:
        return "medium"
    if _bool(row, "sample_reliability_claim_allowed"):
        return "high"
    return "medium"


def _missing_flags(row: dict[str, Any], contradiction_flags: list[str]) -> list[str]:
    flags = set(_split_flags(row.get("missing_data_flags_skill")))
    flags.update(_split_flags(row.get("missing_data_flags")))
    if "candidate_status_manual_review_required" in contradiction_flags:
        flags.add("candidate_status_manual_review_required")
    return sorted(flag for flag in flags if flag != "none")


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _json_list(value: Any) -> list[str]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        return [str(item) for item in json.loads(value)]
    except (TypeError, json.JSONDecodeError):
        return [str(value)]


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or pd.isna(value):
        return []
    return [part for part in str(value).split(";") if part and part != "none"]


def _bool(row: dict[str, Any], column: str) -> bool:
    value = row.get(column)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    if pd.isna(value):
        return False
    return bool(value)


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_report(frame: pd.DataFrame) -> str:
    centers = frame[frame["embiid_overlap_flag"]].sort_values(
        "player_name", ascending=True
    )
    clear = frame[~frame["no_clear_role"]].sort_values(
        ["playoff_rotation_possible", "role_confidence"], ascending=False
    )
    no_clear = frame[frame["no_clear_role"]]
    lines = [
        "# Roster Simulation Examples",
        "",
        "The simulation assigns roster slots before recommendation scoring.",
        "",
        "## Center Candidates",
        "",
        _table(centers.head(15)),
        "",
        "## Clear Role Examples",
        "",
        _table(clear.head(15)),
        "",
        "## No Clear Role Examples",
        "",
        _table(no_clear.head(15)),
        "",
        "## Rules",
        "",
        "- Centers are not projected as normal starters because Embiid owns that slot.",
        "- Double-big roles require shooting plus mobility/defensive evidence.",
        "- Regular-season depth alone is not a priority playoff role.",
    ]
    return "\n".join(lines)


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    lines = [
        "| Player | Primary Slot | Role | Starter | Playoff | Flags |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in frame.to_dict(orient="records"):
        flags = ", ".join(json.loads(row["contradiction_flags"])[:3])
        lines.append(
            f"| {row['player_name']} | {row['primary_roster_slot']} | "
            f"{row['expected_role_on_phi']} | {row['starter_possible']} | "
            f"{row['playoff_rotation_possible']} | {flags} |"
        )
    return "\n".join(lines)
