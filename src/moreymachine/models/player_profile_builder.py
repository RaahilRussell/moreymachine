"""Full player profile data model builder."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.models.explanation_engine_v2 import (
    EVIDENCE_OBJECTS_PATH,
    EXPLANATION_CLAIMS_PATH,
    PLAYER_EXPLANATIONS_V2_PATH,
)
from moreymachine.models.fit_breakdown import PLAYER_FIT_BREAKDOWNS_PATH
from moreymachine.models.help_impact import PLAYER_HELP_IMPACT_PATH
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.models.salary_cards import PLAYER_SALARY_CARDS_PATH
from moreymachine.models.scenario_engine import CANDIDATE_SCENARIOS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

PLAYER_PROFILES_PATH = REPORTS_DATA_DIR / "player_profiles.parquet"
PLAYER_PROFILES_JSON_PATH = REPORTS_DATA_DIR / "player_profiles.json"
PLAYER_PROFILES_INDEX_PATH = REPORTS_DATA_DIR / "player_profiles_index.parquet"


@dataclass(frozen=True)
class PlayerProfileBuildResult:
    """Summary from player profile build."""

    rows: int
    complete_or_mostly_complete: int
    profiles_path: Path
    json_path: Path
    index_path: Path


def build_player_profiles(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    explanations_path: str | Path = PLAYER_EXPLANATIONS_V2_PATH,
    salary_cards_path: str | Path = PLAYER_SALARY_CARDS_PATH,
    help_impact_path: str | Path = PLAYER_HELP_IMPACT_PATH,
    fit_breakdowns_path: str | Path = PLAYER_FIT_BREAKDOWNS_PATH,
    scenarios_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    claims_path: str | Path = EXPLANATION_CLAIMS_PATH,
    evidence_path: str | Path = EVIDENCE_OBJECTS_PATH,
    profiles_path: str | Path = PLAYER_PROFILES_PATH,
    json_path: str | Path = PLAYER_PROFILES_JSON_PATH,
    index_path: str | Path = PLAYER_PROFILES_INDEX_PATH,
) -> PlayerProfileBuildResult:
    """Build full player profiles from structured artifacts."""
    target_team = str(team or "PHI").upper()
    context = context or {}
    rankings = pd.read_parquet(rankings_path)
    explanations = pd.read_parquet(explanations_path)
    salary = pd.read_parquet(salary_cards_path)
    help_impact = pd.read_parquet(help_impact_path)
    fit_breakdowns = pd.read_parquet(fit_breakdowns_path)
    scenarios = pd.read_parquet(scenarios_path)
    claims = pd.read_parquet(claims_path)
    evidence = pd.read_parquet(evidence_path)

    merged = rankings.merge(
        explanations, on="player_id", how="left", suffixes=("", "_exp")
    )
    merged = merged.merge(salary, on="player_id", how="left", suffixes=("", "_salary"))
    merged = merged.merge(
        help_impact, on="player_id", how="left", suffixes=("", "_help")
    )
    merged = merged.merge(
        fit_breakdowns,
        on="player_id",
        how="left",
        suffixes=("", "_breakdown"),
    )
    scenario_lookup = _group_by_player(scenarios)
    claim_lookup = _group_by_player(claims)
    evidence_lookup = _group_by_player(evidence)
    rows = [
        _profile_row(
            row,
            scenario_lookup,
            claim_lookup,
            evidence_lookup,
            target_team=target_team,
            context_mode=str(context.get("context_mode") or "unknown"),
        )
        for row in merged.to_dict(orient="records")
    ]
    profiles = pd.DataFrame(rows)
    index = _profile_index(profiles)

    profiles_output = Path(profiles_path)
    json_output = Path(json_path)
    index_output = Path(index_path)
    profiles_output.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_parquet(profiles_output, index=False)
    index.to_parquet(index_output, index=False)
    json_output.write_text(
        json.dumps(profiles.to_dict(orient="records"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    run_id = new_run_id()
    for artifact in (profiles_output, json_output, index_output):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                rankings_path,
                explanations_path,
                salary_cards_path,
                help_impact_path,
                fit_breakdowns_path,
                scenarios_path,
                claims_path,
                evidence_path,
            ),
            upstream_artifacts=(
                rankings_path,
                explanations_path,
                salary_cards_path,
                help_impact_path,
                fit_breakdowns_path,
                scenarios_path,
                claims_path,
                evidence_path,
            ),
            known_limitations=(
                "Profiles are generated from cached validated public-data artifacts.",
                "Incomplete salary, transaction, injury, and availability data "
                "remain flagged.",
            ),
        )
    complete = profiles["profile_completeness"].isin(["complete", "mostly_complete"])
    return PlayerProfileBuildResult(
        rows=len(profiles),
        complete_or_mostly_complete=int(complete.sum()),
        profiles_path=profiles_output,
        json_path=json_output,
        index_path=index_output,
    )


def _profile_row(
    row: dict[str, Any],
    scenario_lookup: dict[int, list[dict[str, Any]]],
    claim_lookup: dict[int, list[dict[str, Any]]],
    evidence_lookup: dict[int, list[dict[str, Any]]],
    *,
    target_team: str,
    context_mode: str,
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    scenarios = scenario_lookup.get(player_id, [])
    claims = claim_lookup.get(player_id, [])
    evidence = evidence_lookup.get(player_id, [])
    scenario_by_type = {item["scenario_type"]: item for item in scenarios}
    salary_card = _salary_card(row)
    unsupported = [claim for claim in claims if not bool(claim.get("allowed"))]
    profile_id = row.get("player_profile_id") or _profile_id(player_id, row.get("player_name"))
    completeness = _completeness(row, claims, evidence, salary_card)
    return {
        "target_team": target_team,
        "player_profile_id": profile_id,
        "player_id": player_id,
        "player_name": row.get("player_name"),
        "current_team": row.get("current_team"),
        "position": row.get("position"),
        "height": row.get("height"),
        "weight": row.get("weight"),
        "age": row.get("age"),
        "candidate_type": row.get("candidate_type"),
        "board_type": row.get("board_type"),
        "acquisition_path": row.get("acquisition_path"),
        "source_summary": row.get("source_summary"),
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "score_breakdown_json": row.get("score_waterfall_data")
        or _score_breakdown_json(row),
        "help_areas_json": row.get("top_help_areas") or "[]",
        "does_not_help_json": row.get("does_not_help") or "[]",
        "final_fit_score": row.get("final_recommendation_score"),
        "recommendation": row.get("recommendation"),
        "recommendation_confidence": row.get("recommendation_confidence"),
        "overall_tier": row.get("recommendation"),
        "explanation_confidence": row.get("confidence"),
        "manual_review_required": bool(row.get("manual_review_required")),
        "contradiction_flags": row.get("contradiction_flags"),
        "primary_roster_slot": row.get("primary_roster_slot"),
        "secondary_roster_slots": row.get("secondary_scenarios"),
        "blocked_slots": row.get("blocked_slots"),
        "expected_role_on_phi": row.get("expected_role_on_phi"),
        "expected_minutes_context": row.get("expected_minutes_context"),
        "starter_possible": bool(row.get("starter_possible")),
        "closing_possible": bool(row.get("closing_possible")),
        "playoff_rotation_possible": bool(row.get("playoff_rotation_possible")),
        "regular_season_depth_only": bool(row.get("regular_season_depth_only")),
        "matchup_dependent": bool(row.get("matchup_dependent")),
        "two_big_compatible": bool(row.get("two_big_compatible")),
        "no_clear_role": bool(row.get("no_clear_role")),
        "top_gaps_helped": row.get("helps_most_summary") or row.get("gaps_addressed"),
        "gaps_not_helped": row.get("does_not_help_summary")
        or row.get("gaps_not_addressed"),
        "fit_with_embiid": row.get("compatibility_with_embiid"),
        "fit_with_maxey": row.get("compatibility_with_maxey"),
        "fit_with_george": row.get("compatibility_with_george"),
        "fit_with_current_roster": _current_roster_fit(row),
        "lineup_contexts": row.get("expected_minutes_context"),
        "bad_lineup_contexts": row.get("downside_case"),
        "redundancy_flags": row.get("role_redundancy_flags"),
        "role_conflict_flags": row.get("contradiction_flags"),
        "salary_card_json": json.dumps(salary_card, sort_keys=True),
        "salary_card_status": _salary_card_status(row, salary_card),
        "contract_status": row.get("contract_status"),
        "cap_hit_millions": row.get("cap_hit_millions"),
        "base_salary_millions": row.get("base_salary_millions"),
        "contract_aav_millions": row.get("contract_aav_millions"),
        "acquisition_feasibility_score": row.get("acquisition_feasibility_score"),
        "feasibility_tier": row.get("feasibility_tier"),
        "trade_cost_proxy": row.get("trade_cost_proxy"),
        "salary_matching_complexity": row.get("salary_matching_complexity"),
        "opportunity_cost_score": row.get("opportunity_cost_score"),
        "opportunity_cost_flags": row.get("opportunity_cost_flags"),
        "opportunity_cost_summary": row.get("opportunity_cost_summary"),
        "shooting_summary": _skill_summary(row, "spacing"),
        "creation_summary": _skill_summary(row, "creation"),
        "defense_summary": _skill_summary(row, "defense"),
        "rebounding_summary": _skill_summary(row, "rebounding"),
        "portability_summary": _component_summary(row, "Playoff Role"),
        "sample_reliability": row.get("recommendation_confidence"),
        "best_case_scenario": _scenario_json(scenario_by_type, "best_case"),
        "realistic_scenario": _scenario_json(scenario_by_type, "realistic_case"),
        "downside_scenario": _scenario_json(scenario_by_type, "bad_fit_case"),
        "playoff_scenario": _scenario_json(scenario_by_type, "playoff_case"),
        "regular_season_scenario": _scenario_json(
            scenario_by_type, "regular_season_only_case"
        ),
        "overpay_scenario": _scenario_json(scenario_by_type, "overpay_case"),
        "missing_data_scenario": _scenario_json(scenario_by_type, "missing_data_case"),
        "primary_scenario": row.get("primary_scenario"),
        "scenario_robustness_score": row.get("scenario_robustness_score"),
        "executive_summary": row.get("executive_summary"),
        "why_the_model_likes_him": row.get("why_the_model_likes_him"),
        "what_he_helps_most": row.get("what_he_helps_most"),
        "what_he_does_not_solve": row.get("what_he_does_not_solve"),
        "role_on_sixers": row.get("role_on_sixers"),
        "fit_with_core_explanation": _core_explanation(row),
        "salary_and_acquisition_explanation": row.get(
            "contract_and_acquisition_context"
        ),
        "main_concerns": row.get("main_concerns"),
        "why_this_could_be_wrong": row.get("why_this_could_be_wrong"),
        "recommendation_interpretation": row.get("recommendation_interpretation"),
        "evidence_summary": row.get("evidence_summary"),
        "assumptions": "Generated from cached public-data artifacts.",
        "missing_or_stale_data": row.get("missing_or_stale_data"),
        "evidence_objects": json.dumps(evidence, sort_keys=True),
        "claim_to_evidence_map": json.dumps(_claim_map(claims), sort_keys=True),
        "unsupported_claim_flags": json.dumps(
            [claim["claim_type"] for claim in unsupported]
        ),
        "data_sources": row.get("source_summary"),
        "source_note": f"full player profile builder; context_mode={context_mode}",
        "missing_data_flags": row.get("missing_data_flags") or "none",
        "profile_completeness": completeness,
    }


def _salary_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "salary_card_title": row.get("salary_card_title"),
        "salary_summary": row.get("salary_summary"),
        "contract_status": row.get("contract_status"),
        "cap_hit_millions": row.get("cap_hit_millions"),
        "base_salary_millions": row.get("base_salary_millions"),
        "contract_aav_millions": row.get("contract_aav_millions"),
        "acquisition_path": row.get("acquisition_path"),
        "feasibility_tier": row.get("feasibility_tier"),
        "manual_review_needed": bool(row.get("manual_review_needed")),
        "salary_warning_flags": row.get("salary_warning_flags"),
    }


def _salary_card_status(row: dict[str, Any], salary_card: dict[str, Any]) -> str:
    missing = str(row.get("missing_data_flags") or "")
    if salary_card.get("cap_hit_millions") is None:
        return "missing_salary_flagged"
    if "base_salary_missing" in missing or "contract_aav_missing" in missing:
        return "partial_salary_flagged"
    return "salary_card_present"


def _score_breakdown_json(row: dict[str, Any]) -> str:
    labels = (
        ("Need Match", "gap_match_score"),
        ("Skill Evidence", "skill_evidence_score"),
        ("Core Compatibility", "core_compatibility_score"),
        ("Roster Slot Fit", "roster_slot_fit_score"),
        ("Contender Blueprint Fit", "contender_blueprint_fit_score"),
        ("Playoff Role", "playoff_role_score"),
        ("Scenario Robustness", "scenario_robustness_score"),
        ("Acquisition Feasibility", "acquisition_feasibility_score"),
        ("Contract Value", "contract_value_score"),
        ("Risk", "risk_score"),
        ("Opportunity Cost", "opportunity_cost_score"),
        ("Final", "final_recommendation_score"),
    )
    return json.dumps(
        [
            {"label": label, "value": row.get(column)}
            for label, column in labels
            if column in row
        ],
        sort_keys=True,
    )


def _profile_index(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in profiles.to_dict(orient="records"):
        rows.append(
            {
                "player_profile_id": row["player_profile_id"],
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "current_team": row.get("current_team"),
                "candidate_type": row.get("candidate_type"),
                "recommendation": row.get("recommendation"),
                "profile_path": (
                    f"data/reports/scouting_reports/{row['player_profile_id']}.md"
                ),
            }
        )
    return pd.DataFrame(rows)


def _group_by_player(frame: pd.DataFrame) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        out.setdefault(int(row["player_id"]), []).append(row)
    return out


def _profile_id(player_id: int, player_name: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(player_name))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = (
        ascii_name
        .lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("'", "")
        .replace("’", "")
    )
    return f"{player_id}-{slug}"


def _completeness(
    row: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    salary_card: dict[str, Any],
) -> str:
    if bool(row.get("manual_review_required")):
        return "manual_review_needed"
    missing = str(row.get("missing_data_flags") or "")
    if not claims or not evidence:
        return "weak"
    if "base_salary_missing" in missing or "contract_aav_missing" in missing:
        return "mostly_complete"
    if salary_card.get("cap_hit_millions") is None:
        return "partial"
    return "complete"


def _scenario_json(scenarios: dict[str, dict[str, Any]], scenario_type: str) -> str:
    return json.dumps(scenarios.get(scenario_type, {}), sort_keys=True)


def _claim_map(claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    out = {}
    for claim in claims:
        out[str(claim["claim_type"])] = _json_list(claim.get("evidence_object_ids"))
    return out


def _current_roster_fit(row: dict[str, Any]) -> str:
    return (
        f"Embiid: {row.get('compatibility_with_embiid')}; "
        f"Maxey: {row.get('compatibility_with_maxey')}; "
        f"George: {row.get('compatibility_with_george')}"
    )


def _core_explanation(row: dict[str, Any]) -> str:
    return _current_roster_fit(row)


def _skill_summary(row: dict[str, Any], claim_type: str) -> str:
    claims = _json_list(row.get("claim_to_evidence_map"))
    return f"{claim_type} summary generated from evidence claims: {claims}"


def _component_summary(row: dict[str, Any], component: str) -> str:
    cards = _json_list(row.get("component_cards"))
    for card in cards:
        if card.get("component") == component:
            return card.get("why_it_helped_score") or card.get("what_it_means")
    return ""


def _json_list(value: Any) -> list[Any]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
