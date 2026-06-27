"""Candidate scenario engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.acquisition_feasibility import ACQUISITION_FEASIBILITY_PATH
from moreymachine.features.compatibility_matrix import CANDIDATE_CORE_COMPATIBILITY_PATH
from moreymachine.features.gap_model import SIXERS_GAP_MODEL_PATH
from moreymachine.features.roster_simulation import CANDIDATE_ROSTER_SIMULATION_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR, REPORTS_DATA_DIR

CANDIDATE_SCENARIOS_PATH = FEATURES_DATA_DIR / "candidate_scenarios.parquet"
SCENARIO_EXAMPLES_PATH = REPORTS_DATA_DIR / "scenario_examples.md"

SCENARIO_TYPES = (
    "best_case",
    "realistic_case",
    "conservative_case",
    "playoff_case",
    "regular_season_only_case",
    "overpay_case",
    "missing_data_case",
    "bad_fit_case",
)


@dataclass(frozen=True)
class ScenarioBuildResult:
    """Summary from building candidate scenarios."""

    rows: int
    candidates: int
    manual_review_scenarios: int
    output_path: Path
    report_path: Path


def build_candidate_scenarios(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    roster_simulation_path: str | Path = CANDIDATE_ROSTER_SIMULATION_PATH,
    acquisition_feasibility_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    compatibility_path: str | Path = CANDIDATE_CORE_COMPATIBILITY_PATH,
    gap_model_path: str | Path = SIXERS_GAP_MODEL_PATH,
    output_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    report_path: str | Path = SCENARIO_EXAMPLES_PATH,
) -> ScenarioBuildResult:
    """Build all scenario rows for every candidate."""
    target_team = str(team or "PHI").upper()
    context = context or {}
    simulation = pd.read_parquet(roster_simulation_path)
    acquisition = pd.read_parquet(acquisition_feasibility_path)
    compatibility = pd.read_parquet(compatibility_path)
    gaps = pd.read_parquet(gap_model_path)
    merged = simulation.merge(
        acquisition,
        left_on="player_id",
        right_on="candidate_id",
        how="left",
        suffixes=("", "_acquisition"),
    )
    compatibility_summary = _compatibility_summary(compatibility)
    gap_lookup = _gap_lookup(gaps)

    rows = []
    for row in merged.to_dict(orient="records"):
        for scenario_type in SCENARIO_TYPES:
            rows.append(
                _scenario_row(
                    row,
                    scenario_type,
                    compatibility_summary,
                    gap_lookup,
                    target_team=target_team,
                    context_mode=str(context.get("context_mode") or "unknown"),
                )
            )
    frame = pd.DataFrame(rows)

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
                roster_simulation_path,
                acquisition_feasibility_path,
                compatibility_path,
                gap_model_path,
            ),
            upstream_artifacts=(
                roster_simulation_path,
                acquisition_feasibility_path,
                compatibility_path,
                gap_model_path,
            ),
            known_limitations=(
                "Scenarios are deterministic product cases, not probabilistic "
                "forecasts.",
                "They depend on public-data role, fit, and acquisition proxies.",
            ),
        )

    return ScenarioBuildResult(
        rows=len(frame),
        candidates=frame["player_name"].nunique(),
        manual_review_scenarios=int(
            frame["missing_data_flags"].str.contains("manual_review", na=False).sum()
        ),
        output_path=output,
        report_path=report,
    )


def _compatibility_summary(frame: pd.DataFrame) -> dict[int, dict[str, dict[str, Any]]]:
    out: dict[int, dict[str, dict[str, Any]]] = {}
    core = frame[
        frame["sixers_player_name"].isin(["Joel Embiid", "Tyrese Maxey", "Paul George"])
    ]
    for row in core.to_dict(orient="records"):
        out.setdefault(int(row["candidate_id"]), {})[row["sixers_player_name"]] = row
    return out


def _gap_lookup(gaps: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in gaps.sort_values("severity", ascending=False).to_dict(orient="records"):
        out.setdefault(str(row["roster_slot_needed"]), []).append(row)
    return out


def _scenario_row(
    row: dict[str, Any],
    scenario_type: str,
    compatibility: dict[int, dict[str, dict[str, Any]]],
    gap_lookup: dict[str, list[dict[str, Any]]],
    *,
    target_team: str,
    context_mode: str,
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    player_name = str(row.get("player_name") or "")
    primary_slot = str(row.get("primary_roster_slot") or "no_clear_role")
    possible_slots = _json_list(row.get("possible_roster_slots"))
    lineups = _json_list(row.get("likely_lineup_contexts"))
    bad_lineups = _json_list(row.get("bad_lineup_contexts"))
    contradictions = _json_list(row.get("contradiction_flags"))
    missing_flags = _combined_flags(row)
    gaps_addressed = _gaps_for_slots(possible_slots, gap_lookup, row)
    gaps_not_addressed = _gaps_not_addressed(gaps_addressed, gap_lookup)
    core_summary = _core_summary(compatibility.get(player_id, {}))
    acquisition_context = _acquisition_context(row)

    text = _scenario_text(
        row,
        scenario_type,
        primary_slot,
        lineups,
        bad_lineups,
        contradictions,
        gaps_addressed,
    )
    scenario_missing = list(missing_flags)
    if scenario_type == "missing_data_case" and not scenario_missing:
        scenario_missing.append("no_critical_missing_data_identified")
    if scenario_type == "bad_fit_case" and contradictions:
        scenario_missing.extend(contradictions)

    return {
        "target_team": target_team,
        "scenario_id": f"{player_id}_{scenario_type}",
        "player_id": player_id,
        "player_name": player_name,
        "scenario_type": scenario_type,
        "roster_slot": _scenario_slot(primary_slot, scenario_type, row),
        "expected_minutes_context": _scenario_minutes(row, scenario_type),
        "lineups_affected": json.dumps(lineups),
        "gaps_addressed": json.dumps(gaps_addressed),
        "gaps_not_addressed": json.dumps(gaps_not_addressed),
        "compatibility_summary": core_summary,
        "acquisition_context": acquisition_context,
        "upside_case": text["upside_case"],
        "downside_case": text["downside_case"],
        "risk_case": text["risk_case"],
        "confidence": _scenario_confidence(row, scenario_type, scenario_missing),
        "recommendation_under_this_scenario": text["recommendation"],
        "source": "roster_simulation + acquisition_feasibility + compatibility",
        "source_note": f"context_mode={context_mode}",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(sorted(set(scenario_missing)))
        if scenario_missing
        else "none",
    }


def _scenario_text(
    row: dict[str, Any],
    scenario_type: str,
    primary_slot: str,
    lineups: list[str],
    bad_lineups: list[str],
    contradictions: list[str],
    gaps_addressed: list[str],
) -> dict[str, str]:
    role = str(row.get("expected_role_on_phi") or primary_slot.replace("_", " "))
    acquisition_score = _float(row.get("acquisition_feasibility_score"))
    cap_hit = _float(row.get("cap_hit_millions"))
    gap_text = ", ".join(gaps_addressed[:3]) if gaps_addressed else "no major gap"
    bad_context = ", ".join(bad_lineups) if bad_lineups else "none identified"
    lineups_text = ", ".join(lineups[:3]) if lineups else "general rotation context"

    if scenario_type == "best_case":
        return {
            "upside_case": f"{role} becomes a clean answer for {gap_text}.",
            "downside_case": f"The role narrows if {bad_context} matters.",
            "risk_case": _risk_text(row, contradictions),
            "recommendation": (
                "Worth prioritizing only if acquisition cost matches the role."
            ),
        }
    if scenario_type == "realistic_case":
        return {
            "upside_case": f"Most realistic use is {role} in {lineups_text}.",
            "downside_case": f"Does not automatically solve gaps outside {gap_text}.",
            "risk_case": _risk_text(row, contradictions),
            "recommendation": (
                "Evaluate as a role-specific target, not a generic upgrade."
            ),
        }
    if scenario_type == "conservative_case":
        return {
            "upside_case": f"Can help in narrower {primary_slot} minutes.",
            "downside_case": (
                "Role shrinks if skill evidence does not translate to PHI."
            ),
            "risk_case": _risk_text(row, contradictions),
            "recommendation": (
                "Useful only if the role stays narrow and price stays controlled."
            ),
        }
    if scenario_type == "playoff_case":
        playoff = bool(row.get("playoff_rotation_possible"))
        return {
            "upside_case": f"Playoff path is {role}."
            if playoff
            else "No clean playoff path yet.",
            "downside_case": f"Bad contexts: {bad_context}.",
            "risk_case": _risk_text(row, contradictions),
            "recommendation": "Playoff target"
            if playoff
            else "Do not treat as playoff proof.",
        }
    if scenario_type == "regular_season_only_case":
        return {
            "upside_case": "Can absorb regular-season minutes and protect the core.",
            "downside_case": "Regular-season depth does not equal a playoff solution.",
            "risk_case": _risk_text(row, contradictions),
            "recommendation": "Depth-only unless playoff role evidence improves.",
        }
    if scenario_type == "overpay_case":
        return {
            "upside_case": f"Basketball role may work, but cap hit is {cap_hit:.1f}M.",
            "downside_case": (
                "Overpaying can turn a useful role into bad roster construction."
            ),
            "risk_case": f"Acquisition feasibility score is {acquisition_score:.1f}.",
            "recommendation": "Avoid overpaying beyond the simulated role.",
        }
    if scenario_type == "missing_data_case":
        return {
            "upside_case": "If missing data checks out, the role can be reevaluated.",
            "downside_case": (
                "Missing or stale data can invalidate the current classification."
            ),
            "risk_case": _risk_text(row, contradictions),
            "recommendation": "Manual review before any confident recommendation.",
        }
    return {
        "upside_case": "There is still a narrow role if contradictions are resolved.",
        "downside_case": f"Bad-fit context: {bad_context}.",
        "risk_case": _risk_text(row, contradictions),
        "recommendation": "Avoid unless the bad-fit condition is false.",
    }


def _risk_text(row: dict[str, Any], contradictions: list[str]) -> str:
    if contradictions:
        return "Contradictions: " + ", ".join(contradictions[:4])
    if bool(row.get("manual_review_required")):
        return "Manual acquisition/status review is required."
    if _float(row.get("acquisition_feasibility_score")) < 35:
        return "Acquisition feasibility is low."
    return "Main risk is role translation and acquisition price."


def _scenario_slot(primary_slot: str, scenario_type: str, row: dict[str, Any]) -> str:
    if scenario_type == "bad_fit_case" and bool(row.get("embiid_overlap_flag")):
        return "starting_center_blocked_by_embiid"
    if scenario_type == "regular_season_only_case":
        return "regular_season_depth"
    return primary_slot


def _scenario_minutes(row: dict[str, Any], scenario_type: str) -> str:
    if scenario_type == "best_case" and bool(row.get("playoff_rotation_possible")):
        return "upper-end role-specific playoff rotation minutes"
    if scenario_type == "regular_season_only_case":
        return "regular-season depth minutes"
    if scenario_type == "bad_fit_case":
        return "minutes should shrink or role should be avoided"
    return str(row.get("expected_minutes_context") or "scenario-dependent minutes")


def _scenario_confidence(
    row: dict[str, Any], scenario_type: str, missing_flags: list[str]
) -> str:
    if scenario_type in {"missing_data_case", "bad_fit_case"}:
        return "medium"
    if missing_flags and any("missing" in flag for flag in missing_flags):
        return "low"
    return str(row.get("role_confidence") or "medium")


def _combined_flags(row: dict[str, Any]) -> list[str]:
    flags = set()
    flags.update(_split_flags(row.get("missing_data_flags")))
    flags.update(_split_flags(row.get("missing_data_flags_acquisition")))
    if bool(row.get("manual_review_required")):
        flags.add("manual_review_required")
    return sorted(flag for flag in flags if flag != "none")


def _gaps_for_slots(
    slots: list[str], gap_lookup: dict[str, list[dict[str, Any]]], row: dict[str, Any]
) -> list[str]:
    names: list[str] = []
    for slot in slots:
        for gap in gap_lookup.get(slot, [])[:2]:
            if _gap_allowed_by_skill_evidence(row, gap):
                names.append(str(gap["gap_name"]))
    return _ordered_unique(names)


def _gap_allowed_by_skill_evidence(row: dict[str, Any], gap: dict[str, Any]) -> bool:
    try:
        evidence = json.loads(str(row.get("data_evidence") or "{}"))
    except json.JSONDecodeError:
        return False
    allowed = evidence.get("claim_allowed", {})
    requirements = _json_list(gap.get("skill_requirements"))
    for requirement in requirements:
        if not _requirement_allowed(requirement, allowed, row):
            return False
    return True


def _requirement_allowed(
    requirement: str, allowed: dict[str, Any], row: dict[str, Any]
) -> bool:
    mapping = {
        "spot_up_spacing": "spacing",
        "shooting_gravity": "shooting_gravity",
        "movement_shooting": "movement",
        "rim_protection": "rim_protection",
        "defensive_rebounding": "defensive_rebounding",
        "wing_defense_proxy": "wing_defense",
        "point_of_attack_defense_proxy": "poa_defense",
        "switchability_proxy": "switchability",
        "secondary_creation": "secondary_creation",
        "connector_passing": "connector",
        "ball_security": "ball_security",
        "low_usage_fit": "low_usage",
        "playoff_portability_base": "playoff_portability",
        "sample_reliability": "sample_reliability",
        "role_stability": "role_stability",
        "minutes_context": "sample_reliability",
    }
    if requirement == "fake_spacing_risk":
        return not bool(allowed.get("fake_spacing_risk"))
    if requirement == "defense_or_spacing":
        return bool(allowed.get("wing_defense")) or bool(allowed.get("spacing"))
    if requirement == "usage_compatibility":
        contradictions = _json_list(row.get("contradiction_flags"))
        return "maxey_usage_overlap" not in contradictions
    if requirement == "size":
        return bool(allowed.get("switchability")) or bool(allowed.get("rim_protection"))
    key = mapping.get(requirement)
    if key is None:
        return True
    return bool(allowed.get(key))


def _gaps_not_addressed(
    addressed: list[str], gap_lookup: dict[str, list[dict[str, Any]]]
) -> list[str]:
    important = []
    for gaps in gap_lookup.values():
        for gap in gaps:
            if float(gap.get("severity") or 0) > 7:
                important.append(str(gap["gap_name"]))
    return [name for name in _ordered_unique(important) if name not in addressed][:5]


def _core_summary(core_rows: dict[str, dict[str, Any]]) -> str:
    pieces = []
    for name in ("Joel Embiid", "Tyrese Maxey", "Paul George"):
        row = core_rows.get(name)
        if not row:
            continue
        flags = _json_list(row.get("conflict_flags"))
        type_text = row.get("compatibility_type")
        if flags:
            pieces.append(f"{name}: {type_text} ({', '.join(flags[:2])})")
        else:
            pieces.append(f"{name}: {type_text}")
    return "; ".join(pieces) if pieces else "core compatibility not available"


def _acquisition_context(row: dict[str, Any]) -> str:
    return (
        f"{row.get('acquisition_path')} / {row.get('feasibility_tier')} "
        f"({row.get('acquisition_difficulty')})"
    )


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


def _ordered_unique(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_report(frame: pd.DataFrame) -> str:
    normalized = frame["player_name"].astype(str).str.normalize("NFKD")
    vuc = frame[
        normalized.str.encode("ascii", "ignore").str.decode("ascii") == "Nikola Vucevic"
    ]
    wing = frame[frame["roster_slot"].isin(["3_and_d_wing", "defensive_forward"])].head(
        8
    )
    lines = [
        "# Scenario Examples",
        "",
        "Each candidate gets best, realistic, downside, playoff, overpay, "
        "missing-data, and bad-fit cases.",
        "",
        "## Nikola Vucevic Example",
        "",
        _scenario_table(vuc),
        "",
        "## Wing/Forward Examples",
        "",
        _scenario_table(wing),
    ]
    return "\n".join(lines)


def _scenario_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No matching scenarios."
    lines = [
        "| Player | Scenario | Slot | Recommendation | Risk |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in frame.head(16).to_dict(orient="records"):
        lines.append(
            f"| {row['player_name']} | {row['scenario_type']} | "
            f"{row['roster_slot']} | {row['recommendation_under_this_scenario']} | "
            f"{row['risk_case']} |"
        )
    return "\n".join(lines)
