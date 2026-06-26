"""Cross-artifact validation for the v2 reasoning product."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.features.compatibility_matrix import CANDIDATE_CORE_COMPATIBILITY_PATH
from moreymachine.features.roster_simulation import CANDIDATE_ROSTER_SIMULATION_PATH
from moreymachine.models.best_by_need import BEST_BY_NEED_PATH
from moreymachine.models.explanation_engine_v2 import (
    EVIDENCE_OBJECTS_PATH,
    EXPLANATION_CLAIMS_PATH,
)
from moreymachine.models.fit_breakdown import PLAYER_FIT_BREAKDOWNS_PATH
from moreymachine.models.help_impact import PLAYER_HELP_IMPACT_PATH
from moreymachine.models.player_profile_builder import (
    PLAYER_PROFILES_INDEX_PATH,
    PLAYER_PROFILES_PATH,
)
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.models.salary_cards import PLAYER_SALARY_CARDS_PATH
from moreymachine.models.scenario_engine import CANDIDATE_SCENARIOS_PATH
from moreymachine.utils.paths import CANDIDATE_UNIVERSE_PATH, REPORTS_DATA_DIR

REASONING_VALIDATION_REPORT_PATH = REPORTS_DATA_DIR / "reasoning_validation_v2.md"
PLAYER_PROFILE_VALIDATION_REPORT_PATH = (
    REPORTS_DATA_DIR / "player_profile_validation.md"
)

PRIORITY = "Priority Target"
HIGH_RECOMMENDATIONS = {"Priority Target", "Strong Fit If Affordable"}
FREE_AGENT_BOARD_TYPES = {"free_agent"}
TRADE_BOARD_TYPES = {"trade_target"}
WATCHLIST_CANDIDATE_TYPES = {
    "star_unrealistic",
    "core_unavailable",
    "unavailable_core_player",
    "theoretical_only",
    "contract_blocked",
}
UNKNOWN_OR_STALE_STATUS = {
    "stale_needs_review",
    "manual_verification_required",
    "manual_review_required",
    "conflict_between_sources",
}
CRITICAL_MISSING_FLAGS = {
    "manual_review_needed",
    "candidate_status_manual_review_required",
    "stale_needs_review",
    "manual_verification_required",
    "conflict_between_sources",
    "cap_hit_missing",
}


@dataclass(frozen=True)
class ReasoningIssue:
    """One validation issue from the v2 reasoning system."""

    gate: str
    message: str
    severity: str = "error"
    player_id: int | None = None
    player_name: str | None = None


@dataclass
class ReasoningValidationResult:
    """Validation result for the v2 reasoning artifacts."""

    issues: list[ReasoningIssue] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[ReasoningIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ReasoningIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def add(
        self,
        gate: str,
        message: str,
        *,
        severity: str = "error",
        player_id: int | None = None,
        player_name: str | None = None,
    ) -> None:
        """Append a validation issue."""
        self.issues.append(
            ReasoningIssue(
                gate=gate,
                message=message,
                severity=severity,
                player_id=player_id,
                player_name=player_name,
            )
        )

    def to_markdown(self) -> str:
        """Render the validation result as Markdown."""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            "# Reasoning Validation V2",
            "",
            f"- Status: `{status}`",
            f"- Errors: `{len(self.errors)}`",
            f"- Warnings: `{len(self.warnings)}`",
            "",
            "## Row Counts",
            "",
            "| Artifact | Rows |",
            "| --- | ---: |",
        ]
        for name, count in sorted(self.row_counts.items()):
            lines.append(f"| {name} | {count} |")
        lines.extend(["", "## Issues", ""])
        if not self.issues:
            lines.append("- Clean.")
            return "\n".join(lines)
        lines.append("| Severity | Gate | Player | Message |")
        lines.append("| --- | --- | --- | --- |")
        for issue in self.issues:
            player = issue.player_name or ""
            if issue.player_id is not None:
                player = f"{player} ({issue.player_id})".strip()
            lines.append(
                f"| {issue.severity} | {issue.gate} | {player} | "
                f"{issue.message.replace('|', '/') } |"
            )
        return "\n".join(lines)


def validate_reasoning_v2(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    claims_path: str | Path = EXPLANATION_CLAIMS_PATH,
    evidence_path: str | Path = EVIDENCE_OBJECTS_PATH,
    profiles_path: str | Path = PLAYER_PROFILES_PATH,
    profile_index_path: str | Path = PLAYER_PROFILES_INDEX_PATH,
    salary_cards_path: str | Path = PLAYER_SALARY_CARDS_PATH,
    help_impact_path: str | Path = PLAYER_HELP_IMPACT_PATH,
    fit_breakdowns_path: str | Path = PLAYER_FIT_BREAKDOWNS_PATH,
    best_by_need_path: str | Path = BEST_BY_NEED_PATH,
    roster_simulation_path: str | Path = CANDIDATE_ROSTER_SIMULATION_PATH,
    compatibility_path: str | Path = CANDIDATE_CORE_COMPATIBILITY_PATH,
    scenarios_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
) -> ReasoningValidationResult:
    """Validate generated v2 reasoning artifacts from disk."""
    frames = {
        "rankings": _read_parquet(rankings_path),
        "claims": _read_parquet(claims_path),
        "evidence": _read_parquet(evidence_path),
        "profiles": _read_parquet(profiles_path),
        "profile_index": _read_parquet(profile_index_path),
        "salary_cards": _read_parquet(salary_cards_path),
        "help_impact": _read_parquet(help_impact_path),
        "fit_breakdowns": _read_parquet(fit_breakdowns_path),
        "best_by_need": _read_parquet(best_by_need_path),
        "roster_simulation": _read_parquet(roster_simulation_path),
        "compatibility": _read_parquet(compatibility_path),
        "scenarios": _read_parquet(scenarios_path),
        "candidate_universe": _read_parquet(candidate_universe_path, required=False),
    }
    return validate_reasoning_frames(**frames)


def validate_player_profile_artifacts(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    profiles_path: str | Path = PLAYER_PROFILES_PATH,
    profile_index_path: str | Path = PLAYER_PROFILES_INDEX_PATH,
    salary_cards_path: str | Path = PLAYER_SALARY_CARDS_PATH,
    help_impact_path: str | Path = PLAYER_HELP_IMPACT_PATH,
    fit_breakdowns_path: str | Path = PLAYER_FIT_BREAKDOWNS_PATH,
    scenarios_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    evidence_path: str | Path = EVIDENCE_OBJECTS_PATH,
) -> ReasoningValidationResult:
    """Validate profile-specific artifacts from disk."""
    frames = {
        "rankings": _read_parquet(rankings_path),
        "profiles": _read_parquet(profiles_path),
        "profile_index": _read_parquet(profile_index_path),
        "salary_cards": _read_parquet(salary_cards_path),
        "help_impact": _read_parquet(help_impact_path),
        "fit_breakdowns": _read_parquet(fit_breakdowns_path),
        "scenarios": _read_parquet(scenarios_path),
        "evidence": _read_parquet(evidence_path),
    }
    result = ReasoningValidationResult(
        row_counts={name: len(frame) for name, frame in frames.items()}
    )
    _validate_profile_links(result=result, **frames)
    _validate_profile_content(result=result, profiles=frames["profiles"])
    return result


def validate_reasoning_frames(
    *,
    rankings: pd.DataFrame,
    claims: pd.DataFrame,
    evidence: pd.DataFrame,
    profiles: pd.DataFrame,
    profile_index: pd.DataFrame | None = None,
    salary_cards: pd.DataFrame | None = None,
    help_impact: pd.DataFrame | None = None,
    fit_breakdowns: pd.DataFrame | None = None,
    best_by_need: pd.DataFrame | None = None,
    roster_simulation: pd.DataFrame | None = None,
    compatibility: pd.DataFrame | None = None,
    scenarios: pd.DataFrame | None = None,
    candidate_universe: pd.DataFrame | None = None,
) -> ReasoningValidationResult:
    """Validate v2 reasoning artifacts supplied as DataFrames."""
    frames = {
        "rankings": rankings,
        "claims": claims,
        "evidence": evidence,
        "profiles": profiles,
        "profile_index": profile_index,
        "salary_cards": salary_cards,
        "help_impact": help_impact,
        "fit_breakdowns": fit_breakdowns,
        "best_by_need": best_by_need,
        "roster_simulation": roster_simulation,
        "compatibility": compatibility,
        "scenarios": scenarios,
        "candidate_universe": candidate_universe,
    }
    result = ReasoningValidationResult(
        row_counts={
            name: len(frame) for name, frame in frames.items() if frame is not None
        }
    )
    _validate_claim_evidence(result, claims, evidence)
    _validate_claim_permissions(result, claims)
    _validate_recommendations(result, rankings, candidate_universe)
    _validate_roster_slots(result, rankings, profiles, roster_simulation)
    _validate_gap_skill_permissions(result, rankings, claims)
    _validate_core_compatibility(result, rankings, profiles, compatibility)
    _validate_profile_links(
        result=result,
        rankings=rankings,
        profiles=profiles,
        profile_index=profile_index,
        salary_cards=salary_cards,
        help_impact=help_impact,
        fit_breakdowns=fit_breakdowns,
        scenarios=scenarios,
        evidence=evidence,
    )
    _validate_profile_content(result=result, profiles=profiles)
    _validate_salary_cards(result, salary_cards)
    _validate_best_by_need(result, best_by_need)
    return result


def _validate_claim_evidence(
    result: ReasoningValidationResult, claims: pd.DataFrame, evidence: pd.DataFrame
) -> None:
    if claims.empty:
        result.add("claim_evidence", "explanation claim artifact is empty")
        return
    if evidence.empty:
        result.add("claim_evidence", "evidence object artifact is empty")
        return
    if not {"evidence_object_ids", "player_id", "claim_type"}.issubset(claims.columns):
        result.add("claim_evidence", "claim artifact lacks evidence linkage columns")
        return
    if "evidence_id" not in evidence.columns:
        result.add("claim_evidence", "evidence artifact lacks evidence_id")
        return
    evidence_ids = set(evidence["evidence_id"].astype(str))
    for row in claims.to_dict(orient="records"):
        ids = _json_list(row.get("evidence_object_ids"))
        if not ids:
            result.add(
                "claim_evidence",
                "claim has no evidence object",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
            continue
        missing = [item for item in ids if str(item) not in evidence_ids]
        if missing:
            result.add(
                "claim_evidence",
                f"claim references missing evidence ids: {missing[:3]}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )


def _validate_claim_permissions(
    result: ReasoningValidationResult, claims: pd.DataFrame
) -> None:
    if claims.empty or not {"claim_type", "claim", "allowed"}.issubset(claims.columns):
        return
    denied_prefixes = {
        "spacing": "Cannot verify",
        "rim_protection": "Cannot verify",
        "wing_defense": "Cannot verify",
        "point_of_attack_defense": "Cannot verify",
        "creation": "Cannot verify",
        "rebounding": "Cannot verify",
        "starter": "Do not project as a starter",
    }
    positive_words = {
        "spacing": "spaces the floor",
        "rim_protection": "protects the rim",
        "wing_defense": "adds wing defense",
        "point_of_attack_defense": "adds point-of-attack defense",
        "creation": "adds secondary creation",
        "rebounding": "helps defensive rebounding",
        "starter": "Starter projection is allowed",
    }
    for row in claims.to_dict(orient="records"):
        claim_type = str(row.get("claim_type") or "")
        if claim_type not in denied_prefixes:
            continue
        claim = str(row.get("claim") or "")
        allowed = _bool(row.get("allowed"))
        if not allowed and not claim.startswith(denied_prefixes[claim_type]):
            result.add(
                f"unsupported_{claim_type}_claim",
                f"denied claim does not clearly say it is unsupported: {claim}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if (
            not allowed
            and not claim.startswith(denied_prefixes[claim_type])
            and positive_words[claim_type].lower() in claim.lower()
        ):
            result.add(
                f"unsupported_{claim_type}_claim",
                f"unsupported claim uses positive language: {claim}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )


def _validate_recommendations(
    result: ReasoningValidationResult,
    rankings: pd.DataFrame,
    candidate_universe: pd.DataFrame | None,
) -> None:
    if rankings.empty:
        result.add("recommendations_present", "candidate rankings v2 is empty")
        return
    frame = _merge_candidate_status(rankings, candidate_universe)
    for row in frame.to_dict(orient="records"):
        recommendation = str(row.get("recommendation") or "")
        if recommendation and not row.get("primary_roster_slot"):
            result.add(
                "scoring_before_roster_slot",
                "recommendation exists before roster-slot assignment",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if recommendation and not row.get("primary_scenario"):
            result.add(
                "recommendation_before_scenario",
                "recommendation exists before scenario assignment",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        board_type = str(row.get("board_type") or "")
        candidate_type = str(row.get("candidate_type") or "")
        if board_type == "realistic" and candidate_type in WATCHLIST_CANDIDATE_TYPES:
            result.add(
                "theoretical_on_realistic_board",
                f"{candidate_type} appears on realistic board",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if recommendation != PRIORITY:
            if (
                recommendation in HIGH_RECOMMENDATIONS
                and str(row.get("primary_roster_slot") or "") == "no_clear_role"
            ):
                result.add(
                    "high_recommendation_no_clear_role",
                    "high recommendation has no clear roster role",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )
            continue
        if _bool(row.get("manual_review_required")):
            result.add(
                "priority_manual_review",
                "Priority Target requires manual review",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if float(row.get("scenario_robustness_score") or 0) < 65:
            result.add(
                "priority_without_scenario_robustness",
                "Priority Target lacks scenario robustness",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if float(row.get("acquisition_feasibility_score") or 0) < 55:
            result.add(
                "priority_low_feasibility",
                "Priority Target has low acquisition feasibility",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if str(row.get("primary_roster_slot") or "") == "no_clear_role":
            result.add(
                "priority_no_clear_role",
                "Priority Target has no clear role",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if candidate_type in WATCHLIST_CANDIDATE_TYPES:
            result.add(
                "priority_theoretical_only",
                "Priority Target is theoretical, unavailable, or blocked",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        status = str(row.get("candidate_status_freshness") or "")
        flags = _flag_set(row.get("missing_data_flags"))
        if status in UNKNOWN_OR_STALE_STATUS or flags.intersection(
            {"manual_review_needed", "candidate_status_manual_review_required"}
        ):
            result.add(
                "priority_unknown_or_stale_status",
                f"Priority Target has stale or unknown status: {status}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )


def _validate_roster_slots(
    result: ReasoningValidationResult,
    rankings: pd.DataFrame,
    profiles: pd.DataFrame,
    roster_simulation: pd.DataFrame | None,
) -> None:
    frames = [rankings, profiles]
    if roster_simulation is not None:
        frames.append(roster_simulation)
    for frame in frames:
        if frame.empty:
            continue
        for row in frame.to_dict(orient="records"):
            position = _position_from_row(row)
            primary_slot = str(row.get("primary_roster_slot") or "")
            starter = _bool(row.get("starter_possible"))
            two_big = _bool(row.get("two_big_compatible"))
            flags = _json_list(row.get("contradiction_flags"))
            if "C" in position and starter and not two_big:
                result.add(
                    "center_starter_conflict_with_embiid",
                    "center marked starter_possible without double-big evidence",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )
            if "C" in position and primary_slot == "starting_center":
                result.add(
                    "center_starter_conflict_with_embiid",
                    "center kept in blocked starting_center slot",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )
            if (
                "normal_starting_center_slot_blocked_by_embiid" in flags
                and starter
            ):
                result.add(
                    "center_starter_conflict_with_embiid",
                    "blocked Embiid-center overlap still marked starter_possible",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )


def _validate_gap_skill_permissions(
    result: ReasoningValidationResult, rankings: pd.DataFrame, claims: pd.DataFrame
) -> None:
    if rankings.empty or claims.empty:
        return
    allowed_lookup = _claim_allowed_lookup(claims)
    for row in rankings.to_dict(orient="records"):
        player_id = _int_or_none(row.get("player_id"))
        if player_id is None:
            continue
        for gap in _json_list(row.get("gaps_addressed")):
            claim_types = _claim_types_for_gap(str(gap))
            for claim_type in claim_types:
                if allowed_lookup.get(player_id, {}).get(claim_type) is False:
                    result.add(
                        "gap_without_skill_permission",
                        f"gap '{gap}' requires denied {claim_type} claim",
                        player_id=player_id,
                        player_name=row.get("player_name"),
                    )


def _validate_core_compatibility(
    result: ReasoningValidationResult,
    rankings: pd.DataFrame,
    profiles: pd.DataFrame,
    compatibility: pd.DataFrame | None,
) -> None:
    if compatibility is not None and not compatibility.empty:
        required = {"candidate_id", "sixers_player_name", "evidence", "confidence"}
        if required.issubset(compatibility.columns):
            core = compatibility[
                compatibility["sixers_player_name"].isin(
                    ["Joel Embiid", "Tyrese Maxey", "Paul George"]
                )
            ]
            missing_evidence = core[
                core["evidence"].isna() | (core["evidence"].astype(str).str.len() == 0)
            ]
            for row in missing_evidence.head(20).to_dict(orient="records"):
                result.add(
                    "core_compatibility_missing_evidence",
                    "core compatibility row lacks evidence",
                    player_id=_int_or_none(row.get("candidate_id")),
                    player_name=row.get("candidate_name"),
                )
    for frame in (rankings, profiles):
        if frame.empty:
            continue
        for column in ("fit_with_embiid", "fit_with_maxey", "fit_with_george"):
            if column not in frame.columns:
                continue
            bad = frame[
                frame[column].fillna("").astype(str).isin(["", "not evaluated"])
            ]
            for row in bad.head(20).to_dict(orient="records"):
                result.add(
                    "core_compatibility_missing",
                    f"{column} is not evaluated",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )


def _validate_profile_links(
    *,
    result: ReasoningValidationResult,
    rankings: pd.DataFrame,
    profiles: pd.DataFrame,
    evidence: pd.DataFrame,
    profile_index: pd.DataFrame | None = None,
    salary_cards: pd.DataFrame | None = None,
    help_impact: pd.DataFrame | None = None,
    fit_breakdowns: pd.DataFrame | None = None,
    scenarios: pd.DataFrame | None = None,
) -> None:
    if profiles.empty:
        result.add("player_profiles_present", "player profiles artifact is empty")
        return
    profile_ids = set(profiles["player_id"].dropna().astype(int))
    if rankings.empty:
        ranking_ids = set()
    else:
        ranking_ids = set(rankings["player_id"].dropna().astype(int))
    for player_id in sorted(ranking_ids - profile_ids)[:50]:
        result.add(
            "board_player_missing_profile",
            "board player has no player profile",
            player_id=player_id,
        )
    if profile_index is not None and not profile_index.empty:
        indexed = set(profile_index["player_id"].dropna().astype(int))
        for player_id in sorted(ranking_ids - indexed)[:50]:
            result.add(
                "clickable_row_missing_profile_id",
                "board player missing profile index row",
                player_id=player_id,
            )
    if "player_profile_id" in profiles.columns:
        missing_profile_id = profiles[profiles["player_profile_id"].fillna("") == ""]
        for row in missing_profile_id.head(20).to_dict(orient="records"):
            result.add(
                "clickable_row_missing_profile_id",
                "profile row lacks player_profile_id",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
    _validate_player_linked_artifact(
        result,
        profiles,
        salary_cards,
        "profile_missing_salary_card",
        "profile has no salary card",
    )
    _validate_player_linked_artifact(
        result,
        profiles,
        help_impact,
        "profile_missing_help_impact",
        "profile has no help-impact row",
    )
    _validate_player_linked_artifact(
        result,
        profiles,
        fit_breakdowns,
        "profile_missing_fit_breakdown",
        "profile has no fit-breakdown row",
    )
    _validate_player_linked_artifact(
        result,
        profiles,
        evidence,
        "profile_missing_evidence",
        "profile has no evidence rows",
    )
    if scenarios is not None and not scenarios.empty:
        scenario_ids = set(scenarios["player_id"].dropna().astype(int))
        for row in profiles[~profiles["player_id"].astype(int).isin(scenario_ids)].head(
            20
        ).to_dict(orient="records"):
            result.add(
                "profile_missing_scenario",
                "profile has no scenario rows",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )


def _validate_profile_content(
    *, result: ReasoningValidationResult, profiles: pd.DataFrame
) -> None:
    if profiles.empty:
        return
    required_text = {
        "top_gaps_helped": "profile_missing_top_help_areas",
        "gaps_not_helped": "profile_missing_does_not_help",
        "recommendation_interpretation": (
            "profile_missing_recommendation_interpretation"
        ),
        "evidence_summary": "profile_missing_evidence_summary",
    }
    for column, gate in required_text.items():
        if column not in profiles.columns:
            result.add(gate, f"profile artifact lacks {column}")
            continue
        missing = profiles[profiles[column].fillna("").astype(str).str.len() == 0]
        for row in missing.head(20).to_dict(orient="records"):
            result.add(
                gate,
                f"profile has empty {column}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
    for column in ("realistic_scenario", "best_case_scenario"):
        if column not in profiles.columns:
            continue
        missing = profiles[
            profiles[column].fillna("").astype(str).isin(["", "{}", "[]"])
        ]
        for row in missing.head(20).to_dict(orient="records"):
            result.add(
                "profile_missing_scenario",
                f"profile has empty {column}",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
    text_columns = [
        column
        for column in (
            "executive_summary",
            "why_the_model_likes_him",
            "main_concerns",
            "why_this_could_be_wrong",
        )
        if column in profiles.columns
    ]
    for column in text_columns:
        contains = profiles[column].fillna("").astype(str).str.contains(
            "No major concerns", case=False, regex=False
        )
        for row in profiles[contains].head(20).to_dict(orient="records"):
            result.add(
                "no_major_concerns_phrase",
                f"{column} uses forbidden phrase",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        repeated = (
            profiles[column]
            .fillna("")
            .astype(str)
            .loc[lambda series: series.str.len() >= 80]
            .value_counts()
        )
        duplicate_templates = repeated[repeated > 40]
        for text, count in duplicate_templates.head(5).items():
            result.add(
                "duplicate_template_explanations",
                f"{column} repeats exact long text {count} times: {text[:120]}",
            )
    if {"explanation_confidence", "missing_data_flags"}.issubset(profiles.columns):
        high = profiles[profiles["explanation_confidence"].fillna("") == "High"]
        for row in high.to_dict(orient="records"):
            critical = _flag_set(row.get("missing_data_flags")).intersection(
                CRITICAL_MISSING_FLAGS
            )
            if critical:
                result.add(
                    "high_confidence_with_critical_missing_data",
                    f"High confidence with critical missing flags: {sorted(critical)}",
                    player_id=_int_or_none(row.get("player_id")),
                    player_name=row.get("player_name"),
                )


def _validate_salary_cards(
    result: ReasoningValidationResult, salary_cards: pd.DataFrame | None
) -> None:
    if salary_cards is None:
        return
    if salary_cards.empty:
        result.add("salary_cards_present", "salary cards artifact is empty")
        return
    for row in salary_cards.to_dict(orient="records"):
        flags = _flag_set(row.get("missing_data_flags")).union(
            set(_json_list(row.get("salary_warning_flags")))
        )
        if pd.isna(row.get("cap_hit_millions")) and "cap_hit_missing" not in flags:
            result.add(
                "salary_cap_hit_missing_not_flagged",
                "salary card has missing cap hit without cap_hit_missing flag",
                player_id=_int_or_none(row.get("player_id")),
                player_name=row.get("player_name"),
            )
        if "salary_millions" in salary_cards.columns:
            result.add(
                "ambiguous_salary_field",
                "salary cards must not use ambiguous salary_millions",
            )
            break


def _validate_best_by_need(
    result: ReasoningValidationResult, best_by_need: pd.DataFrame | None
) -> None:
    if best_by_need is None:
        return
    if best_by_need.empty:
        result.add("best_by_need_present", "best-by-need artifact is empty")
        return
    required = {"need_id", "top_players", "why_these_players_fit"}
    missing_columns = required - set(best_by_need.columns)
    if missing_columns:
        result.add(
            "best_by_need_schema",
            f"best-by-need artifact missing columns: {sorted(missing_columns)}",
        )
        return
    for row in best_by_need.to_dict(orient="records"):
        players = _json_list(row.get("top_players"))
        if not isinstance(players, list):
            result.add(
                "best_by_need_top_players",
                "top_players is not a JSON list",
            )


def _read_parquet(path: str | Path, *, required: bool = True) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        if required:
            raise FileNotFoundError(f"Required artifact is missing: {file_path}")
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _merge_candidate_status(
    rankings: pd.DataFrame, candidate_universe: pd.DataFrame | None
) -> pd.DataFrame:
    if candidate_universe is None or candidate_universe.empty:
        return rankings.copy()
    cols = [
        column
        for column in (
            "player_id",
            "candidate_status_freshness",
            "missing_data_flags",
        )
        if column in candidate_universe.columns
    ]
    if "player_id" not in cols:
        return rankings.copy()
    status = candidate_universe[cols].drop_duplicates("player_id")
    return rankings.merge(
        status,
        on="player_id",
        how="left",
        suffixes=("", "_candidate"),
    )


def _position_from_row(row: dict[str, Any]) -> str:
    position = str(row.get("position") or "")
    if position:
        return position
    evidence = _json_dict(row.get("data_evidence"))
    return str(evidence.get("position") or "")


def _claim_allowed_lookup(claims: pd.DataFrame) -> dict[int, dict[str, bool]]:
    lookup: dict[int, dict[str, bool]] = {}
    for row in claims.to_dict(orient="records"):
        player_id = _int_or_none(row.get("player_id"))
        if player_id is None:
            continue
        lookup.setdefault(player_id, {})[str(row.get("claim_type"))] = _bool(
            row.get("allowed")
        )
    return lookup


def _claim_types_for_gap(gap: str) -> set[str]:
    text = gap.lower()
    claim_types = set()
    if any(word in text for word in ("spacing", "shooting", "stretch")):
        claim_types.add("spacing")
    if "rim" in text:
        claim_types.add("rim_protection")
    if "rebounding" in text or "rebound" in text:
        claim_types.add("rebounding")
    if "point-of-attack" in text:
        claim_types.add("point_of_attack_defense")
    elif any(word in text for word in ("wing defense", "defense")):
        claim_types.add("wing_defense")
    if "creation" in text or "creator" in text:
        claim_types.add("creation")
    return claim_types


def _validate_player_linked_artifact(
    result: ReasoningValidationResult,
    profiles: pd.DataFrame,
    artifact: pd.DataFrame | None,
    gate: str,
    message: str,
) -> None:
    if artifact is None:
        return
    if artifact.empty:
        result.add(gate, f"{message}: artifact is empty")
        return
    if "player_id" not in artifact.columns:
        result.add(gate, f"{message}: artifact lacks player_id")
        return
    artifact_ids = set(artifact["player_id"].dropna().astype(int))
    for row in profiles[~profiles["player_id"].astype(int).isin(artifact_ids)].head(
        20
    ).to_dict(orient="records"):
        result.add(
            gate,
            message,
            player_id=_int_or_none(row.get("player_id")),
            player_name=row.get("player_name"),
        )


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "") or _is_na(value):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return parsed if isinstance(parsed, list) else [parsed]


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, "") or _is_na(value):
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _flag_set(value: Any) -> set[str]:
    if value in (None, "", "none") or _is_na(value):
        return set()
    if isinstance(value, list):
        return {str(item) for item in value if str(item) != "none"}
    flags = set()
    for part in str(value).replace(",", ";").split(";"):
        cleaned = part.strip()
        if cleaned and cleaned != "none":
            flags.add(cleaned)
    return flags


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "") or _is_na(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _int_or_none(value: Any) -> int | None:
    try:
        if _is_na(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_na(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
