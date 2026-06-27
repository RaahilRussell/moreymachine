"""Opportunity-cost model for candidate acquisition decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.acquisition_feasibility import ACQUISITION_FEASIBILITY_PATH
from moreymachine.features.roster_simulation import CANDIDATE_ROSTER_SIMULATION_PATH
from moreymachine.utils.paths import CANDIDATE_UNIVERSE_PATH, FEATURES_DATA_DIR, REPORTS_DATA_DIR

OPPORTUNITY_COST_PATH = FEATURES_DATA_DIR / "opportunity_cost.parquet"
OPPORTUNITY_COST_REPORT_PATH = REPORTS_DATA_DIR / "opportunity_cost.md"


@dataclass(frozen=True)
class OpportunityCostResult:
    """Summary for opportunity-cost build."""

    rows: int
    high_cost_rows: int
    output_path: Path
    report_path: Path


def build_opportunity_cost(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    roster_simulation_path: str | Path = CANDIDATE_ROSTER_SIMULATION_PATH,
    acquisition_feasibility_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    output_path: str | Path = OPPORTUNITY_COST_PATH,
    report_path: str | Path = OPPORTUNITY_COST_REPORT_PATH,
) -> OpportunityCostResult:
    """Build explicit opportunity-cost rows for every candidate."""
    normalized_team = str(team or "PHI").upper()
    context = context or {}
    candidates = pd.read_parquet(candidate_universe_path)
    simulation = pd.read_parquet(roster_simulation_path)
    acquisition = pd.read_parquet(acquisition_feasibility_path)

    frame = candidates.merge(
        simulation,
        on="player_id",
        how="left",
        suffixes=("", "_sim"),
    ).merge(
        acquisition,
        left_on="player_id",
        right_on="candidate_id",
        how="left",
        suffixes=("", "_acq"),
    )
    rows = [
        _opportunity_row(row, normalized_team, context)
        for row in frame.to_dict(orient="records")
    ]
    output_frame = pd.DataFrame(rows)
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output_frame.to_parquet(output, index=False)
    report.write_text(_render_report(output_frame), encoding="utf-8")

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                candidate_universe_path,
                roster_simulation_path,
                acquisition_feasibility_path,
            ),
            upstream_artifacts=(
                candidate_universe_path,
                roster_simulation_path,
                acquisition_feasibility_path,
            ),
            known_limitations=(
                "Opportunity cost is a deterministic public-data proxy.",
                "It does not know private trade cost, medical data, or team intent.",
                "PHI center and high-usage guard rules come from manual team context.",
            ),
        )
    return OpportunityCostResult(
        rows=len(output_frame),
        high_cost_rows=int((output_frame["opportunity_cost_tier"] == "High").sum()),
        output_path=output,
        report_path=report,
    )


def _opportunity_row(
    row: dict[str, Any],
    team: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    player_name = row.get("player_name")
    position = str(row.get("position") or "")
    primary_slot = str(row.get("primary_roster_slot") or "no_clear_role")
    acquisition_score = _float(row.get("acquisition_feasibility_score"))
    cap_hit = _nullable_float(row.get("cap_hit_millions"))
    candidate_type = str(row.get("candidate_type") or "")
    contradiction_flags = _json_list(row.get("contradiction_flags"))
    blocked_slots = _json_list(row.get("blocked_slots"))
    missing = set(_split_flags(row.get("missing_data_flags")))
    missing.update(_split_flags(row.get("missing_data_flags_acq")))
    flags: list[str] = []
    penalty = 0.0

    if primary_slot == "no_clear_role" or bool(row.get("no_clear_role")):
        flags.append("no_clear_role")
        penalty += 25
    if candidate_type in {"star_unrealistic", "core_unavailable", "unavailable_core_player"}:
        flags.append("theoretical_or_unavailable")
        penalty += 40
    if str(row.get("freshness_status") or "").startswith(("stale", "manual", "conflict")):
        flags.append("status_needs_manual_review")
        penalty += 15
    if bool(row.get("manual_review_required")):
        flags.append("manual_review_required")
        penalty += 10
    if acquisition_score < 35:
        flags.append("low_acquisition_feasibility")
        penalty += 20
    elif acquisition_score < 55:
        flags.append("medium_acquisition_friction")
        penalty += 10
    if str(row.get("salary_matching_complexity") or "") == "high":
        flags.append("high_salary_matching_complexity")
        penalty += 10

    is_center = "C" in position
    if team == "PHI" and is_center:
        allowed_center_slots = {
            "backup_center",
            "non_embiid_center_minutes",
            "matchup_big",
            "double_big_stretch_partner",
            "regular_season_depth",
        }
        if primary_slot not in allowed_center_slots:
            flags.append("phi_center_slot_cost")
            penalty += 30
        if "starting_center" in blocked_slots:
            flags.append("embiid_blocks_normal_starting_center")
            penalty += 18
        if cap_hit is not None and cap_hit > 18 and primary_slot in {
            "backup_center",
            "non_embiid_center_minutes",
            "matchup_big",
        }:
            flags.append("expensive_center_for_narrow_role")
            penalty += 18
        if cap_hit is not None and cap_hit > 28 and "two_big_compatible" not in contradiction_flags:
            flags.append("large_center_salary_commitment")
            penalty += 12
    if team == "PHI" and "maxey_usage_overlap" in contradiction_flags:
        flags.append("maxey_high_usage_guard_overlap")
        penalty += 30

    if cap_hit is None:
        missing.add("cap_hit_missing_for_opportunity_cost")
        penalty += 8
    if missing:
        flags.append("incomplete_cost_data")
        penalty += 5

    score = round(max(0.0, min(100.0, penalty)), 2)
    evidence = {
        "position": position,
        "primary_roster_slot": primary_slot,
        "blocked_slots": blocked_slots,
        "contradiction_flags": contradiction_flags,
        "cap_hit_millions": cap_hit,
        "acquisition_feasibility_score": acquisition_score,
        "context_mode": context.get("context_mode", "unknown"),
    }
    return {
        "target_team": team,
        "player_id": player_id,
        "player_name": player_name,
        "candidate_type": candidate_type,
        "position": position,
        "primary_roster_slot": primary_slot,
        "acquisition_path": row.get("acquisition_path"),
        "cap_hit_millions": cap_hit,
        "acquisition_feasibility_score": acquisition_score,
        "opportunity_cost_score": score,
        "opportunity_cost_tier": _tier(score),
        "opportunity_cost_adjustment": round(-score * 0.18, 2),
        "opportunity_cost_flags": json.dumps(_ordered_unique(flags)),
        "role_cost_summary": _summary(player_name, primary_slot, score, flags),
        "why_it_matters": _why(flags),
        "evidence": json.dumps(evidence, sort_keys=True),
        "confidence": "Low" if missing else "Medium",
        "source": "candidate_universe + roster_simulation + acquisition_feasibility",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(sorted(missing)) if missing else "none",
    }


def _tier(score: float) -> str:
    if score >= 65:
        return "High"
    if score >= 40:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Minimal"


def _summary(
    player_name: Any,
    primary_slot: str,
    score: float,
    flags: list[str],
) -> str:
    if not flags:
        return f"{player_name} has no major opportunity-cost flag for {primary_slot}."
    return (
        f"{player_name} carries {score:.1f} opportunity-cost pressure for "
        f"{primary_slot}: {', '.join(flags[:3])}."
    )


def _why(flags: list[str]) -> str:
    if "maxey_high_usage_guard_overlap" in flags:
        return "High-usage guard overlap can spend roster resources without solving Maxey lineup constraints."
    if "expensive_center_for_narrow_role" in flags or "phi_center_slot_cost" in flags:
        return "PHI center additions must be priced for non-Embiid, matchup, or proven two-big roles."
    if "theoretical_or_unavailable" in flags:
        return "The player may be interesting in theory but should not occupy realistic action bandwidth."
    if "low_acquisition_feasibility" in flags:
        return "The acquisition path is costly enough to crowd out cleaner role answers."
    return "Opportunity cost is based on role clarity, acquisition friction, and missing-data risk."


def _render_report(frame: pd.DataFrame) -> str:
    lines = [
        "# Opportunity Cost",
        "",
        "Opportunity cost is explicit so recommendations cannot hide role or price problems.",
        "",
        "| Player | Slot | Cost | Tier | Flags |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in frame.sort_values("opportunity_cost_score", ascending=False).head(25).to_dict(orient="records"):
        flags = ", ".join(_json_list(row.get("opportunity_cost_flags"))[:3])
        lines.append(
            f"| {row['player_name']} | {row['primary_roster_slot']} | "
            f"{row['opportunity_cost_score']:.1f} | {row['opportunity_cost_tier']} | {flags} |"
        )
    return "\n".join(lines)


def _json_list(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or (isinstance(value, float) and pd.isna(value)):
        return []
    return [part for part in str(value).split(";") if part and part != "none"]


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
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


def _nullable_float(value: Any) -> float | None:
    try:
        if value in (None, "") or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
