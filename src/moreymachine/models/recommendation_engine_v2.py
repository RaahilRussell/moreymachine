"""Scenario-aware recommendation engine v2."""

from __future__ import annotations

import argparse
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
from moreymachine.features.player_skill_profiles import PLAYER_SKILL_PROFILES_PATH
from moreymachine.features.roster_simulation import CANDIDATE_ROSTER_SIMULATION_PATH
from moreymachine.models.scenario_engine import CANDIDATE_SCENARIOS_PATH
from moreymachine.utils.paths import CANDIDATE_UNIVERSE_PATH, REPORTS_DATA_DIR

CANDIDATE_FIT_RANKINGS_V2_PATH = REPORTS_DATA_DIR / "candidate_fit_rankings_v2.parquet"
CANDIDATE_FIT_RANKINGS_V2_CSV_PATH = REPORTS_DATA_DIR / "candidate_fit_rankings_v2.csv"
CANDIDATE_FIT_RANKINGS_REALISTIC_V2_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_realistic_v2.parquet"
)
CANDIDATE_FIT_RANKINGS_FREE_AGENTS_V2_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_free_agents_v2.parquet"
)
CANDIDATE_FIT_RANKINGS_TRADE_TARGETS_V2_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_trade_targets_v2.parquet"
)
CANDIDATE_FIT_RANKINGS_WATCHLIST_V2_PATH = (
    REPORTS_DATA_DIR / "candidate_fit_rankings_watchlist_v2.parquet"
)

FREE_AGENT_TYPES = {
    "unrestricted_free_agent",
    "restricted_free_agent",
    "likely_free_agent",
    "minimum_candidate",
    "mle_candidate",
}
TRADE_TYPES = {
    "realistic_trade_target",
    "expensive_trade_target",
    "rookie_scale_trade_target",
    "expensive_but_possible",
}
WATCHLIST_TYPES = {
    "star_unrealistic",
    "core_unavailable",
    "contract_blocked",
    "manual_review_needed",
    "unavailable_core_player",
    "manual_watchlist",
    "missing_contract_status",
}


@dataclass(frozen=True)
class RecommendationV2Result:
    """Summary from v2 recommendation build."""

    rows: int
    priority_targets: int
    manual_review: int
    output_path: Path
    csv_path: Path


def rank_candidates_v2(
    *,
    team: str = "PHI",
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    skill_profiles_path: str | Path = PLAYER_SKILL_PROFILES_PATH,
    roster_simulation_path: str | Path = CANDIDATE_ROSTER_SIMULATION_PATH,
    acquisition_feasibility_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    compatibility_path: str | Path = CANDIDATE_CORE_COMPATIBILITY_PATH,
    scenarios_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    gap_model_path: str | Path = SIXERS_GAP_MODEL_PATH,
    output_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    csv_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_CSV_PATH,
) -> RecommendationV2Result:
    """Build scenario-aware candidate rankings."""
    candidates = pd.read_parquet(candidate_universe_path)
    skills = pd.read_parquet(skill_profiles_path)
    simulation = pd.read_parquet(roster_simulation_path)
    acquisition = pd.read_parquet(acquisition_feasibility_path)
    compatibility = pd.read_parquet(compatibility_path)
    scenarios = pd.read_parquet(scenarios_path)
    gaps = pd.read_parquet(gap_model_path)

    frame = candidates.merge(
        skills, on="player_id", how="left", suffixes=("", "_skill")
    )
    frame = frame.merge(simulation, on="player_id", how="left", suffixes=("", "_sim"))
    frame = frame.merge(
        acquisition,
        left_on="player_id",
        right_on="candidate_id",
        how="left",
        suffixes=("", "_acquisition"),
    )
    compatibility_lookup = _compatibility_lookup(compatibility)
    scenario_lookup = _scenario_lookup(scenarios)
    gap_lookup = _gap_lookup(gaps)
    rows = [
        _ranking_row(row, compatibility_lookup, scenario_lookup, gap_lookup, team)
        for row in frame.to_dict(orient="records")
    ]
    ranked = pd.DataFrame(rows).sort_values(
        ["final_recommendation_score", "player_name"], ascending=[False, True]
    )
    ranked = ranked.reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    ranked["board_type"] = ranked.apply(_board_type, axis=1)

    output = Path(output_path)
    csv = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_parquet(output, index=False)
    ranked.to_csv(csv, index=False)
    _write_splits(ranked)

    run_id = new_run_id()
    artifacts = [
        output,
        csv,
        CANDIDATE_FIT_RANKINGS_REALISTIC_V2_PATH,
        CANDIDATE_FIT_RANKINGS_FREE_AGENTS_V2_PATH,
        CANDIDATE_FIT_RANKINGS_TRADE_TARGETS_V2_PATH,
        CANDIDATE_FIT_RANKINGS_WATCHLIST_V2_PATH,
    ]
    for artifact in artifacts:
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                candidate_universe_path,
                skill_profiles_path,
                roster_simulation_path,
                acquisition_feasibility_path,
                compatibility_path,
                scenarios_path,
                gap_model_path,
            ),
            upstream_artifacts=(
                candidate_universe_path,
                skill_profiles_path,
                roster_simulation_path,
                acquisition_feasibility_path,
                compatibility_path,
                scenarios_path,
                gap_model_path,
            ),
            known_limitations=(
                "Recommendation v2 is a public-data decision product, not NBA advice.",
                "True trade cost, injury status, and team intent remain incomplete.",
            ),
        )

    return RecommendationV2Result(
        rows=len(ranked),
        priority_targets=int((ranked["recommendation"] == "Priority Target").sum()),
        manual_review=int(ranked["manual_review_required"].sum()),
        output_path=output,
        csv_path=csv,
    )


def _ranking_row(
    row: dict[str, Any],
    compatibility: dict[int, dict[str, dict[str, Any]]],
    scenarios: dict[int, dict[str, dict[str, Any]]],
    gaps: dict[str, list[dict[str, Any]]],
    team: str,
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    scenario_rows = scenarios.get(player_id, {})
    compat_rows = compatibility.get(player_id, {})
    possible_slots = _json_list(row.get("possible_roster_slots"))
    contradiction_flags = _json_list(row.get("contradiction_flags"))
    gaps_addressed = _gaps_for_slots(possible_slots, gaps)
    gaps_not_addressed = _gaps_not_addressed(gaps_addressed, gaps)

    scores = _component_scores(row, compat_rows, scenario_rows, gaps_addressed, gaps)
    final_score = _final_score(scores)
    recommendation = _recommendation(row, scores, final_score, contradiction_flags)
    confidence = _recommendation_confidence(row, scores, contradiction_flags)
    missing_flags = _combined_missing_flags(row, scenario_rows)
    best = scenario_rows.get("best_case", {})
    realistic = scenario_rows.get("realistic_case", {})
    downside = scenario_rows.get("bad_fit_case", {}) or scenario_rows.get(
        "conservative_case", {}
    )

    return {
        "player_id": player_id,
        "player_name": row.get("player_name"),
        "current_team": row.get("current_team") or row.get("current_team_skill"),
        "position": row.get("position") or row.get("position_skill"),
        "candidate_type": row.get("candidate_type"),
        "acquisition_path": row.get("acquisition_path"),
        "primary_scenario": realistic.get("scenario_id", f"{player_id}_realistic_case"),
        "secondary_scenarios": json.dumps(
            [f"{player_id}_{name}" for name in ("best_case", "playoff_case")]
        ),
        "primary_roster_slot": row.get("primary_roster_slot"),
        "expected_role_on_phi": row.get("expected_role_on_phi"),
        "expected_minutes_context": row.get("expected_minutes_context"),
        "starter_possible": bool(row.get("starter_possible")),
        "closing_possible": bool(row.get("closing_lineup_possible")),
        "playoff_rotation_possible": bool(row.get("playoff_rotation_possible")),
        "best_case": best.get("upside_case", ""),
        "realistic_case": realistic.get("upside_case", ""),
        "downside_case": downside.get("downside_case", ""),
        "gaps_addressed": json.dumps(gaps_addressed),
        "gaps_not_addressed": json.dumps(gaps_not_addressed),
        "compatibility_with_embiid": _compat_text(compat_rows, "Joel Embiid"),
        "compatibility_with_maxey": _compat_text(compat_rows, "Tyrese Maxey"),
        "compatibility_with_george": _compat_text(compat_rows, "Paul George"),
        **scores,
        "final_recommendation_score": final_score,
        "recommendation": recommendation,
        "recommendation_confidence": confidence,
        "contradiction_flags": json.dumps(contradiction_flags),
        "manual_review_required": bool(row.get("manual_review_required")),
        "missing_data_flags": ";".join(missing_flags) if missing_flags else "none",
        "evidence_summary": _evidence_summary(row, scores, gaps_addressed),
        "source_summary": (
            "candidate_universe; player_skill_profiles; roster_simulation; "
            "acquisition_feasibility; compatibility; scenarios"
        ),
        "source_url": row.get("source_url") or row.get("salary_source") or "",
        "source_note": f"Generated for {team} from cached validated artifacts",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
    }


def _component_scores(
    row: dict[str, Any],
    compat_rows: dict[str, dict[str, Any]],
    scenario_rows: dict[str, dict[str, Any]],
    gaps_addressed: list[str],
    gaps: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    gap_match = _gap_match_score(gaps_addressed, gaps)
    skill_evidence = _skill_evidence_score(row)
    core = _core_compatibility_score(compat_rows)
    slot = _slot_score(row)
    blueprint = round(
        (gap_match * 0.65) + (_float(row.get("playoff_portability_base")) * 0.35), 2
    )
    playoff = _playoff_score(row)
    scenario = _scenario_robustness_score(row, scenario_rows)
    acquisition = _float(row.get("acquisition_feasibility_score"))
    contract = _contract_value_score(row)
    risk = _risk_score(row)
    uncertainty = _uncertainty_penalty(row)
    contradiction = _contradiction_penalty(row)
    return {
        "gap_match_score": gap_match,
        "skill_evidence_score": skill_evidence,
        "core_compatibility_score": core,
        "roster_slot_fit_score": slot,
        "contender_blueprint_fit_score": blueprint,
        "playoff_role_score": playoff,
        "scenario_robustness_score": scenario,
        "acquisition_feasibility_score": acquisition,
        "contract_value_score": contract,
        "risk_score": risk,
        "uncertainty_penalty": uncertainty,
        "contradiction_penalty": contradiction,
    }


def _final_score(scores: dict[str, float]) -> float:
    raw = (
        0.16 * scores["gap_match_score"]
        + 0.12 * scores["skill_evidence_score"]
        + 0.14 * scores["core_compatibility_score"]
        + 0.16 * scores["roster_slot_fit_score"]
        + 0.08 * scores["contender_blueprint_fit_score"]
        + 0.10 * scores["playoff_role_score"]
        + 0.10 * scores["scenario_robustness_score"]
        + 0.08 * scores["acquisition_feasibility_score"]
        + 0.06 * scores["contract_value_score"]
        + 0.08 * (100 - scores["risk_score"])
    )
    raw -= scores["uncertainty_penalty"] + scores["contradiction_penalty"]
    return round(max(0.0, min(100.0, raw)), 2)


def _recommendation(
    row: dict[str, Any],
    scores: dict[str, float],
    final_score: float,
    contradiction_flags: list[str],
) -> str:
    candidate_type = str(row.get("candidate_type") or "")
    acquisition_path = str(row.get("acquisition_path") or "")
    if bool(row.get("manual_review_required")):
        return "Manual Review Required"
    if (
        candidate_type in {"missing_contract_status"}
        or acquisition_path == "unknown_missing_data"
    ):
        return "Missing Data / Cannot Evaluate"
    if candidate_type in {"contract_blocked"}:
        return "Contract Blocked"
    if candidate_type in {
        "star_unrealistic",
        "core_unavailable",
        "unavailable_core_player",
    }:
        return "Unrealistic / Unavailable"
    if bool(row.get("no_clear_role")):
        return "Avoid"
    if bool(row.get("regular_season_depth_only")):
        return "Only If Cheap"
    fatal = {"maxey_usage_overlap", "candidate_status_manual_review_required"}
    if fatal.intersection(contradiction_flags):
        return "Avoid"
    if (
        final_score >= 78
        and scores["gap_match_score"] >= 35
        and scores["roster_slot_fit_score"] >= 70
        and scores["scenario_robustness_score"] >= 65
        and scores["acquisition_feasibility_score"] >= 55
        and scores["contradiction_penalty"] <= 8
        and bool(row.get("playoff_rotation_possible"))
    ):
        return "Priority Target"
    if final_score >= 68 and scores["acquisition_feasibility_score"] >= 40:
        return "Strong Fit If Affordable"
    if final_score >= 58:
        return "Role-Player Target"
    if final_score >= 42:
        return "Only If Cheap"
    return "Avoid"


def _recommendation_confidence(
    row: dict[str, Any], scores: dict[str, float], contradiction_flags: list[str]
) -> str:
    if bool(row.get("manual_review_required")) or scores["uncertainty_penalty"] >= 20:
        return "Low"
    if contradiction_flags or scores["risk_score"] >= 55:
        return "Medium"
    if (
        scores["scenario_robustness_score"] >= 65
        and scores["roster_slot_fit_score"] >= 70
    ):
        return "High"
    return "Medium"


def _gap_match_score(
    gaps_addressed: list[str], gap_lookup: dict[str, list[dict[str, Any]]]
) -> float:
    severities = []
    for gaps in gap_lookup.values():
        for gap in gaps:
            if str(gap["gap_name"]) in gaps_addressed:
                severities.append(float(gap.get("severity") or 0))
    return round(min(100.0, sum(severities) * 2.2), 2)


def _skill_evidence_score(row: dict[str, Any]) -> float:
    dimensions = [
        "spot_up_spacing",
        "movement_shooting",
        "rim_protection",
        "wing_defense_proxy",
        "point_of_attack_defense_proxy",
        "secondary_creation",
        "connector_passing",
        "low_usage_fit",
        "playoff_portability_base",
    ]
    scores = []
    for dim in dimensions:
        value = _float(row.get(dim))
        if _bool(row, f"{dim}_claim_allowed"):
            scores.append(value)
        else:
            scores.append(value * 0.35)
    return round(sum(scores) / len(scores), 2)


def _core_compatibility_score(compat_rows: dict[str, dict[str, Any]]) -> float:
    values = []
    for name in ("Joel Embiid", "Tyrese Maxey", "Paul George"):
        if name in compat_rows:
            values.append(_float(compat_rows[name].get("compatibility_score")))
    if not values:
        return 40.0
    return round(sum(values) / len(values), 2)


def _slot_score(row: dict[str, Any]) -> float:
    if bool(row.get("no_clear_role")):
        return 5.0
    if bool(row.get("regular_season_depth_only")):
        return 35.0
    primary = str(row.get("primary_roster_slot") or "")
    base = {
        "point_of_attack_defender": 82,
        "matchup_big": 62,
        "backup_center": 70,
        "non_embiid_center_minutes": 66,
        "movement_shooter": 72,
        "3_and_d_wing": 78,
        "defensive_forward": 74,
        "low_usage_spacer": 68,
        "bench_creator": 65,
        "secondary_creator": 62,
        "low_usage_connector": 64,
        "stretch_forward": 70,
        "rebounding_forward": 58,
        "theoretical_star_upgrade": 12,
    }.get(primary, 45)
    if bool(row.get("embiid_overlap_flag")) and not bool(row.get("two_big_compatible")):
        base -= 15
    return round(max(0.0, min(100.0, base)), 2)


def _playoff_score(row: dict[str, Any]) -> float:
    if bool(row.get("playoff_rotation_possible")):
        return 80.0
    if bool(row.get("regular_season_depth_only")):
        return 25.0
    if bool(row.get("no_clear_role")):
        return 5.0
    return 45.0


def _scenario_robustness_score(
    row: dict[str, Any], scenario_rows: dict[str, dict[str, Any]]
) -> float:
    score = 55.0
    if bool(row.get("playoff_rotation_possible")):
        score += 15
    if bool(row.get("closing_lineup_possible")):
        score += 10
    if bool(row.get("regular_season_depth_only")):
        score -= 15
    if bool(row.get("no_clear_role")):
        score -= 30
    if (
        scenario_rows.get("bad_fit_case", {})
        .get("roster_slot", "")
        .startswith("starting_center")
    ):
        score -= 8
    return round(max(0.0, min(100.0, score)), 2)


def _contract_value_score(row: dict[str, Any]) -> float:
    cap_hit = _float(row.get("cap_hit_millions"))
    if cap_hit <= 0:
        return 35.0
    role_score = _slot_score(row)
    if cap_hit <= 3:
        return min(100.0, role_score + 22)
    if cap_hit <= 14:
        return min(100.0, role_score + 10)
    if cap_hit <= 25:
        return role_score
    if cap_hit <= 40:
        return max(0.0, role_score - 18)
    return max(0.0, role_score - 35)


def _risk_score(row: dict[str, Any]) -> float:
    risk = 15.0
    if bool(row.get("manual_review_required")):
        risk += 35
    if bool(row.get("no_clear_role")):
        risk += 35
    if bool(row.get("regular_season_depth_only")):
        risk += 15
    if bool(row.get("embiid_overlap_flag")) and not bool(row.get("two_big_compatible")):
        risk += 18
    if _float(row.get("acquisition_feasibility_score")) < 35:
        risk += 18
    risk += min(20, len(_json_list(row.get("contradiction_flags"))) * 7)
    return round(min(100.0, risk), 2)


def _uncertainty_penalty(row: dict[str, Any]) -> float:
    flags = _split_flags(row.get("missing_data_flags"))
    penalty = min(20, len(flags) * 2)
    if bool(row.get("manual_review_required")):
        penalty += 10
    return round(min(35.0, penalty), 2)


def _contradiction_penalty(row: dict[str, Any]) -> float:
    flags = _json_list(row.get("contradiction_flags"))
    penalty = len(flags) * 6
    if "normal_starting_center_slot_blocked_by_embiid" in flags:
        penalty += 4
    if "maxey_usage_overlap" in flags:
        penalty += 10
    return round(min(35.0, penalty), 2)


def _compatibility_lookup(frame: pd.DataFrame) -> dict[int, dict[str, dict[str, Any]]]:
    lookup: dict[int, dict[str, dict[str, Any]]] = {}
    core = frame[
        frame["sixers_player_name"].isin(["Joel Embiid", "Tyrese Maxey", "Paul George"])
    ]
    for row in core.to_dict(orient="records"):
        lookup.setdefault(int(row["candidate_id"]), {})[
            str(row["sixers_player_name"])
        ] = row
    return lookup


def _scenario_lookup(frame: pd.DataFrame) -> dict[int, dict[str, dict[str, Any]]]:
    lookup: dict[int, dict[str, dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        lookup.setdefault(int(row["player_id"]), {})[str(row["scenario_type"])] = row
    return lookup


def _gap_lookup(gaps: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in gaps.sort_values("severity", ascending=False).to_dict(orient="records"):
        out.setdefault(str(row["roster_slot_needed"]), []).append(row)
    return out


def _gaps_for_slots(
    slots: list[str], gap_lookup: dict[str, list[dict[str, Any]]]
) -> list[str]:
    names = []
    for slot in slots:
        for gap in gap_lookup.get(slot, [])[:2]:
            names.append(str(gap["gap_name"]))
    return _ordered_unique(names)


def _gaps_not_addressed(
    addressed: list[str], gap_lookup: dict[str, list[dict[str, Any]]]
) -> list[str]:
    important = []
    for gaps in gap_lookup.values():
        for gap in gaps:
            if float(gap.get("severity") or 0) > 7:
                important.append(str(gap["gap_name"]))
    return [name for name in _ordered_unique(important) if name not in addressed][:5]


def _compat_text(compat_rows: dict[str, dict[str, Any]], name: str) -> str:
    row = compat_rows.get(name)
    if not row:
        return "not evaluated"
    flags = _json_list(row.get("conflict_flags"))
    score = _float(row.get("compatibility_score"))
    if flags:
        return f"{score:.1f} / {row.get('compatibility_type')} ({', '.join(flags[:3])})"
    return f"{score:.1f} / {row.get('compatibility_type')}"


def _evidence_summary(
    row: dict[str, Any], scores: dict[str, float], gaps_addressed: list[str]
) -> str:
    slot = row.get("primary_roster_slot")
    role = row.get("expected_role_on_phi")
    return (
        f"Slot={slot}; role={role}; gaps={', '.join(gaps_addressed[:3])}; "
        f"gap={scores['gap_match_score']:.1f}; "
        f"slot_fit={scores['roster_slot_fit_score']:.1f}; "
        f"acquisition={scores['acquisition_feasibility_score']:.1f}"
    )


def _combined_missing_flags(
    row: dict[str, Any], scenario_rows: dict[str, dict[str, Any]]
) -> list[str]:
    flags = set()
    flags.update(_split_flags(row.get("missing_data_flags")))
    flags.update(_split_flags(row.get("missing_data_flags_skill")))
    flags.update(_split_flags(row.get("missing_data_flags_sim")))
    flags.update(_split_flags(row.get("missing_data_flags_acquisition")))
    for scenario in scenario_rows.values():
        flags.update(_split_flags(scenario.get("missing_data_flags")))
    return sorted(flag for flag in flags if flag != "none")


def _board_type(row: pd.Series) -> str:
    candidate_type = str(row.get("candidate_type") or "")
    if candidate_type in FREE_AGENT_TYPES:
        return "free_agent"
    if candidate_type in TRADE_TYPES:
        return "trade_target"
    if candidate_type in WATCHLIST_TYPES or row["recommendation"] in {
        "Unrealistic / Unavailable",
        "Manual Review Required",
        "Missing Data / Cannot Evaluate",
        "Contract Blocked",
    }:
        return "watchlist"
    return "realistic"


def _write_splits(ranked: pd.DataFrame) -> None:
    realistic = ranked[
        ranked["board_type"].isin(["free_agent", "trade_target", "realistic"])
        & ~ranked["recommendation"].isin(
            [
                "Unrealistic / Unavailable",
                "Manual Review Required",
                "Missing Data / Cannot Evaluate",
                "Contract Blocked",
                "Avoid",
            ]
        )
    ]
    free_agents = ranked[ranked["board_type"] == "free_agent"]
    trade_targets = ranked[ranked["board_type"] == "trade_target"]
    watchlist = ranked[
        ranked["board_type"].eq("watchlist")
        | ranked["recommendation"].isin(
            [
                "Unrealistic / Unavailable",
                "Manual Review Required",
                "Missing Data / Cannot Evaluate",
                "Contract Blocked",
            ]
        )
    ]
    for path, frame in (
        (CANDIDATE_FIT_RANKINGS_REALISTIC_V2_PATH, realistic),
        (CANDIDATE_FIT_RANKINGS_FREE_AGENTS_V2_PATH, free_agents),
        (CANDIDATE_FIT_RANKINGS_TRADE_TARGETS_V2_PATH, trade_targets),
        (CANDIDATE_FIT_RANKINGS_WATCHLIST_V2_PATH, watchlist),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank candidates with v2 engine.")
    parser.add_argument("--team", default="PHI")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = rank_candidates_v2(team=args.team)
    print(f"Rows: {result.rows}")
    print(f"Priority targets: {result.priority_targets}")
    print(f"Manual review: {result.manual_review}")
    print(f"Output: {result.output_path}")
    print(f"CSV: {result.csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
