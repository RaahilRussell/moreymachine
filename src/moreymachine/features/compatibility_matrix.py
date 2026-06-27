"""Candidate-to-current-roster compatibility matrix."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.context.roster_world import ROSTER_WORLD_PATH
from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.player_skill_profiles import PLAYER_SKILL_PROFILES_PATH
from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    FEATURES_DATA_DIR,
    REPORTS_DATA_DIR,
)

CANDIDATE_CORE_COMPATIBILITY_PATH = (
    FEATURES_DATA_DIR / "candidate_core_compatibility.parquet"
)
COMPATIBILITY_EXAMPLES_PATH = REPORTS_DATA_DIR / "compatibility_examples.md"


@dataclass(frozen=True)
class CompatibilityResult:
    """Summary from building compatibility rows."""

    rows: int
    embiid_conflicts: int
    maxey_conflicts: int
    george_positive_rows: int
    output_path: Path
    report_path: Path


def build_compatibility_matrix(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    skill_profiles_path: str | Path = PLAYER_SKILL_PROFILES_PATH,
    roster_world_path: str | Path = ROSTER_WORLD_PATH,
    output_path: str | Path = CANDIDATE_CORE_COMPATIBILITY_PATH,
    report_path: str | Path = COMPATIBILITY_EXAMPLES_PATH,
) -> CompatibilityResult:
    """Build compatibility rows for every candidate against current PHI players."""
    target_team = str(team or "PHI").upper()
    context = context or {}
    candidates = pd.read_parquet(candidate_universe_path)
    skills = pd.read_parquet(skill_profiles_path)
    roster = pd.read_parquet(roster_world_path)
    candidate_frame = candidates.merge(
        skills,
        on="player_id",
        how="left",
        suffixes=("", "_skill"),
    )
    rows = []
    for candidate in candidate_frame.to_dict(orient="records"):
        for sixer in roster.to_dict(orient="records"):
            rows.append(
                _compatibility_row(
                    candidate,
                    sixer,
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
                candidate_universe_path,
                skill_profiles_path,
                roster_world_path,
            ),
            upstream_artifacts=(
                candidate_universe_path,
                skill_profiles_path,
                roster_world_path,
            ),
            known_limitations=(
                "Compatibility uses public-stat skill gates and roster-context rules.",
                "It does not include private lineup data, team intent, or medical "
                "data.",
            ),
        )

    embiid = frame[frame["sixers_player_name"] == "Joel Embiid"]
    maxey = frame[frame["sixers_player_name"] == "Tyrese Maxey"]
    george = frame[frame["sixers_player_name"] == "Paul George"]
    return CompatibilityResult(
        rows=len(frame),
        embiid_conflicts=int(embiid["conflict_flags"].str.contains("embiid").sum()),
        maxey_conflicts=int(maxey["conflict_flags"].str.contains("maxey").sum()),
        george_positive_rows=int((george["compatibility_score"] >= 70).sum()),
        output_path=output,
        report_path=report,
    )


def _compatibility_row(
    candidate: dict[str, Any],
    sixer: dict[str, Any],
    *,
    target_team: str,
    context_mode: str,
) -> dict[str, Any]:
    positives: list[str] = []
    negatives: list[str] = []
    flags: list[str] = []
    contexts: list[str] = []
    missing: set[str] = set()
    score = 60.0

    candidate_name = str(candidate.get("player_name") or "")
    sixer_name = str(sixer.get("player_name") or "")
    candidate_position = str(
        candidate.get("position") or candidate.get("position_skill") or ""
    )
    candidate_type = str(candidate.get("candidate_type") or "")
    is_center = "C" in candidate_position
    is_guard = "G" in candidate_position
    is_wing = "F" in candidate_position or "G-F" in candidate_position

    if _freshness_needs_review(candidate):
        flags.append("candidate_status_needs_review")
        negatives.append("candidate status is stale or manually reviewable")
        score -= 12

    if sixer_name == "Joel Embiid":
        delta = _embiid_fit(candidate, is_center, positives, negatives, flags, contexts)
        score += delta
    elif sixer_name == "Tyrese Maxey":
        delta = _maxey_fit(candidate, is_guard, positives, negatives, flags, contexts)
        score += delta
    elif sixer_name == "Paul George":
        delta = _george_fit(candidate, is_wing, positives, negatives, flags, contexts)
        score += delta
    else:
        delta = _rotation_fit(candidate, sixer, positives, negatives, flags, contexts)
        score += delta

    if candidate_type in {"star_unrealistic", "core_unavailable"}:
        flags.append("availability_not_realistic")
        negatives.append("availability is not realistic enough for a clean fit claim")
        score -= 8
    if not _has_skill_row(candidate):
        missing.add("skill_profile_missing")
        flags.append("skill_profile_missing")
        score -= 15

    score = max(0.0, min(100.0, round(score, 2)))
    compatibility_type = _compatibility_type(score, flags)
    evidence = {
        "candidate_position": candidate_position,
        "sixers_player_role": sixer.get("current_role"),
        "sixers_roster_slot": sixer.get("roster_slot"),
        "spot_up_spacing_claim_allowed": _bool(
            candidate, "spot_up_spacing_claim_allowed"
        ),
        "rim_protection_claim_allowed": _bool(
            candidate, "rim_protection_claim_allowed"
        ),
        "wing_defense_claim_allowed": _bool(
            candidate, "wing_defense_proxy_claim_allowed"
        ),
        "secondary_creation_claim_allowed": _bool(
            candidate, "secondary_creation_claim_allowed"
        ),
        "low_usage_fit_claim_allowed": _bool(candidate, "low_usage_fit_claim_allowed"),
    }
    return {
        "target_team": target_team,
        "candidate_id": candidate.get("player_id"),
        "candidate_name": candidate_name,
        "sixers_player_id": sixer.get("player_id"),
        "sixers_player_name": sixer_name,
        "compatibility_score": score,
        "compatibility_type": compatibility_type,
        "positives": json.dumps(positives),
        "negatives": json.dumps(negatives),
        "conflict_flags": json.dumps(flags),
        "lineup_contexts": json.dumps(contexts or ["general_rotation_context"]),
        "evidence": json.dumps(evidence, sort_keys=True),
        "confidence": "low" if missing else "medium",
        "source": (
            "candidate_universe + player_skill_profiles + "
            f"roster_world_{target_team.lower()}"
        ),
        "source_note": f"context_mode={context_mode}",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(sorted(missing)) if missing else "none",
    }


def _embiid_fit(
    candidate: dict[str, Any],
    is_center: bool,
    positives: list[str],
    negatives: list[str],
    flags: list[str],
    contexts: list[str],
) -> float:
    delta = 0.0
    spacing = _bool(candidate, "spot_up_spacing_claim_allowed")
    rim = _bool(candidate, "rim_protection_claim_allowed")
    low_usage = _bool(candidate, "low_usage_fit_claim_allowed")
    switch = _bool(candidate, "switchability_proxy_claim_allowed")
    fake_spacing = _bool(candidate, "fake_spacing_risk_claim_allowed")

    if spacing:
        positives.append("verified shooting volume can support Embiid spacing")
        contexts.append("Embiid post-touch spacing")
        delta += 10
    elif fake_spacing:
        negatives.append("spacing claim is not verified for Embiid lineups")
        flags.append("embiid_spacing_concern")
        delta -= 10
    if is_center:
        contexts.append("Embiid-off center minutes")
        positives.append("can be evaluated for non-Embiid center minutes")
        flags.append("embiid_center_overlap")
        negatives.append("starting center slot is blocked by Embiid")
        delta -= 12
        if spacing or switch:
            positives.append("has a plausible double-big pathway if role stays narrow")
            contexts.append("scenario-dependent double-big look")
            delta += 6
        else:
            flags.append("double_big_unproven")
            negatives.append("double-big viability lacks shooting or mobility evidence")
            delta -= 10
    if rim and not is_center:
        positives.append(
            "adds defensive support around Embiid without using center slot"
        )
        delta += 6
    if low_usage:
        positives.append("low-usage profile fits next to Embiid touches")
        delta += 5
    return delta


def _maxey_fit(
    candidate: dict[str, Any],
    is_guard: bool,
    positives: list[str],
    negatives: list[str],
    flags: list[str],
    contexts: list[str],
) -> float:
    delta = 0.0
    usage = _float(candidate.get("usage_rate"))
    spacing = _bool(candidate, "spot_up_spacing_claim_allowed")
    secondary = _bool(candidate, "secondary_creation_claim_allowed")
    poa = _bool(candidate, "point_of_attack_defense_proxy_claim_allowed")
    low_usage = _bool(candidate, "low_usage_fit_claim_allowed")

    contexts.append("Maxey usage and guard-defense context")
    if is_guard and usage >= 0.24:
        flags.append("maxey_usage_overlap")
        negatives.append("high-usage guard profile overlaps with Maxey")
        delta -= 14
    if spacing:
        positives.append("verified shooting can space Maxey drives")
        delta += 8
    if secondary and usage < 0.24:
        positives.append("secondary creation can support non-Maxey minutes")
        delta += 7
    if poa:
        positives.append("point-of-attack defense can cover Maxey lineups")
        delta += 10
    if low_usage:
        positives.append("low-usage role does not fight Maxey for touches")
        delta += 5
    if is_guard and not poa and not spacing:
        flags.append("maxey_guard_fit_unclear")
        negatives.append("guard fit lacks verified spacing or defensive cover")
        delta -= 8
    return delta


def _george_fit(
    candidate: dict[str, Any],
    is_wing: bool,
    positives: list[str],
    negatives: list[str],
    flags: list[str],
    contexts: list[str],
) -> float:
    delta = 0.0
    wing_defense = _bool(candidate, "wing_defense_proxy_claim_allowed")
    spacing = _bool(candidate, "spot_up_spacing_claim_allowed")
    low_usage = _bool(candidate, "low_usage_fit_claim_allowed")
    secondary = _bool(candidate, "secondary_creation_claim_allowed")

    contexts.append("George wing-depth and durability-insurance context")
    if is_wing and wing_defense:
        positives.append("adds wing-defense insurance around George")
        delta += 12
    if spacing and low_usage:
        positives.append("can play low-usage spacing lineups with George")
        delta += 8
    if secondary:
        positives.append("secondary creation can reduce George's regular-season burden")
        delta += 5
    if is_wing and not wing_defense and not spacing:
        flags.append("george_redundancy_or_unclear_wing_fit")
        negatives.append("wing label lacks verified defense or spacing")
        delta -= 8
    return delta


def _rotation_fit(
    candidate: dict[str, Any],
    sixer: dict[str, Any],
    positives: list[str],
    negatives: list[str],
    flags: list[str],
    contexts: list[str],
) -> float:
    delta = 0.0
    roster_slot = str(sixer.get("roster_slot") or "")
    candidate_position = str(candidate.get("position") or "")
    spacing = _bool(candidate, "spot_up_spacing_claim_allowed")
    rim = _bool(candidate, "rim_protection_claim_allowed")
    wing_defense = _bool(candidate, "wing_defense_proxy_claim_allowed")
    secondary = _bool(candidate, "secondary_creation_claim_allowed")

    contexts.append(f"{roster_slot or 'rotation'} context")
    if roster_slot == "backup_center" and "C" in candidate_position:
        positives.append("competes for or stabilizes backup-center minutes")
        delta += 8
    if roster_slot == "defensive_forward" and wing_defense:
        positives.append("adds defensive-forward redundancy with evidence")
        delta += 5
    if roster_slot == "secondary_creator" and secondary:
        positives.append("adds creation depth to bench and non-star groups")
        delta += 5
    if spacing:
        positives.append("adds spacing to mixed bench groups")
        delta += 4
    if rim and roster_slot != "starting_center":
        positives.append("adds rim-protection depth in non-Embiid groups")
        delta += 4
    if roster_slot == "starting_center" and "C" in candidate_position:
        flags.append("starting_center_slot_blocked")
        negatives.append("candidate overlaps with Embiid's locked roster slot")
        delta -= 10
    return delta


def _freshness_needs_review(candidate: dict[str, Any]) -> bool:
    return str(candidate.get("candidate_status_freshness") or "") in {
        "stale_needs_review",
        "manual_verification_required",
        "conflict_between_sources",
    }


def _has_skill_row(candidate: dict[str, Any]) -> bool:
    return not pd.isna(candidate.get("spot_up_spacing"))


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


def _compatibility_type(score: float, flags: list[str]) -> str:
    if "availability_not_realistic" in flags:
        return "blocked"
    if any(flag.endswith("_overlap") or flag.endswith("_unproven") for flag in flags):
        return "conflict" if score < 50 else "scenario_dependent"
    if flags:
        return "scenario_dependent"
    if score >= 75:
        return "clean_fit"
    if score >= 65:
        return "positive"
    return "neutral"


def _render_report(frame: pd.DataFrame) -> str:
    embiid = frame[frame["sixers_player_name"] == "Joel Embiid"].copy()
    maxey = frame[frame["sixers_player_name"] == "Tyrese Maxey"].copy()
    george = frame[frame["sixers_player_name"] == "Paul George"].copy()
    lines = [
        "# Compatibility Examples",
        "",
        "Compatibility rows are generated before recommendations so role conflicts "
        "can affect scoring and explanations.",
        "",
        "## Best Embiid Fits",
        "",
        _compat_table(embiid.sort_values("compatibility_score", ascending=False)),
        "",
        "## Embiid Conflicts",
        "",
        _compat_table(embiid.sort_values("compatibility_score", ascending=True)),
        "",
        "## Maxey Fits",
        "",
        _compat_table(maxey.sort_values("compatibility_score", ascending=False)),
        "",
        "## George Fits",
        "",
        _compat_table(george.sort_values("compatibility_score", ascending=False)),
    ]
    return "\n".join(lines)


def _compat_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    lines = [
        "| Candidate | Score | Type | Positives | Negatives | Flags |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in frame.head(10).to_dict(orient="records"):
        positives = ", ".join(json.loads(row["positives"])[:2])
        negatives = ", ".join(json.loads(row["negatives"])[:2])
        flags = ", ".join(json.loads(row["conflict_flags"])[:3])
        lines.append(
            f"| {row['candidate_name']} | {row['compatibility_score']:.1f} | "
            f"{row['compatibility_type']} | {positives} | {negatives} | {flags} |"
        )
    return "\n".join(lines)
