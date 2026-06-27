"""Move recommendation layer built from structured candidate evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

MOVE_RECOMMENDATIONS_PATH = REPORTS_DATA_DIR / "move_recommendations.parquet"


@dataclass(frozen=True)
class MoveRecommendationResult:
    """Summary from move recommendation build."""

    rows: int
    output_path: Path


def build_move_recommendations(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    output_path: str | Path = MOVE_RECOMMENDATIONS_PATH,
) -> MoveRecommendationResult:
    """Build GM-readable move recommendation rows."""
    normalized_team = str(team or "PHI").upper()
    context = context or {}
    rankings = pd.read_parquet(rankings_path)
    rows = [
        _move_row(row, normalized_team, context)
        for row in rankings.to_dict(orient="records")
    ]
    frame = pd.DataFrame(rows).sort_values(
        ["move_score", "player_name"], ascending=[False, True]
    )
    frame["move_priority_rank"] = range(1, len(frame) + 1)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    run_id = new_run_id()
    write_metadata_for_artifact(
        output,
        run_id=run_id,
        source_files=(rankings_path,),
        upstream_artifacts=(rankings_path,),
        known_limitations=(
            "Move recommendations summarize structured board rows.",
            "They do not invent availability, salary, injury, or team-intent facts.",
            "Ollama is not used as source of truth for this artifact.",
        ),
    )
    return MoveRecommendationResult(rows=len(frame), output_path=output)


def _move_row(
    row: dict[str, Any],
    team: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    recommendation = str(row.get("recommendation") or "")
    board_type = str(row.get("board_type") or "")
    score = _float(row.get("final_recommendation_score"))
    action_type = _action_type(row)
    missing_flags = _split_flags(row.get("missing_data_flags"))
    evidence = {
        "rank": row.get("rank"),
        "final_recommendation_score": score,
        "recommendation": recommendation,
        "board_type": board_type,
        "primary_roster_slot": row.get("primary_roster_slot"),
        "acquisition_path": row.get("acquisition_path"),
        "gaps_addressed": _json_list(row.get("gaps_addressed")),
        "gaps_not_addressed": _json_list(row.get("gaps_not_addressed")),
        "opportunity_cost_score": _float(row.get("opportunity_cost_score")),
        "opportunity_cost_flags": _json_list(row.get("opportunity_cost_flags")),
        "context_mode": context.get("context_mode", "unknown"),
    }
    return {
        "team_abbr": team,
        "move_id": f"{team}_{row.get('player_id')}_{action_type}",
        "player_id": row.get("player_id"),
        "player_profile_id": row.get("player_profile_id"),
        "player_name": row.get("player_name"),
        "action_type": action_type,
        "board_type": board_type,
        "recommendation": recommendation,
        "move_score": score,
        "roster_slot": row.get("primary_roster_slot"),
        "expected_role": row.get("expected_role_on_phi"),
        "acquisition_path": row.get("acquisition_path"),
        "opportunity_cost_score": _float(row.get("opportunity_cost_score")),
        "opportunity_cost_flags": row.get("opportunity_cost_flags") or "[]",
        "why_do_this": _why_do_this(row, action_type),
        "why_not_do_this": _why_not_do_this(row, missing_flags),
        "manual_review_required": bool(row.get("manual_review_required")),
        "confidence": _confidence(row, missing_flags),
        "evidence": json.dumps(evidence, sort_keys=True),
        "source": "candidate_fit_rankings_v2",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(missing_flags) if missing_flags else "none",
    }


def _action_type(row: dict[str, Any]) -> str:
    recommendation = str(row.get("recommendation") or "")
    board_type = str(row.get("board_type") or "")
    if recommendation == "Manual Review Required":
        return "manual_review"
    if recommendation in {"Avoid", "Unrealistic / Unavailable", "Contract Blocked"}:
        return "avoid"
    if board_type == "free_agent":
        return "free_agent"
    if board_type == "trade_target":
        return "trade"
    if str(row.get("acquisition_path") or "").startswith("minimum"):
        return "low_cost_depth"
    return "candidate_action"


def _why_do_this(row: dict[str, Any], action_type: str) -> str:
    if action_type == "avoid":
        return "Use this as an avoid/constraint example, not a positive acquisition recommendation."
    gaps = _json_list(row.get("gaps_addressed"))
    gap_text = ", ".join(gaps[:3]) if gaps else "a role-specific need with limited gap evidence"
    return (
        f"Consider {row.get('player_name')} only for {row.get('expected_role_on_phi')} "
        f"because the structured board links him to {gap_text}."
    )


def _why_not_do_this(row: dict[str, Any], missing_flags: list[str]) -> str:
    cost_flags = _json_list(row.get("opportunity_cost_flags"))
    not_help = _json_list(row.get("gaps_not_addressed"))
    concerns = []
    if cost_flags:
        concerns.append("opportunity cost: " + ", ".join(cost_flags[:3]))
    if not_help:
        concerns.append("does not solve: " + ", ".join(not_help[:3]))
    if missing_flags:
        concerns.append("missing/stale data: " + ", ".join(missing_flags[:3]))
    if not concerns:
        concerns.append("price, role, and evidence should still be manually checked before action")
    return "; ".join(concerns)


def _confidence(row: dict[str, Any], missing_flags: list[str]) -> str:
    if bool(row.get("manual_review_required")) or len(missing_flags) >= 5:
        return "Low"
    if _float(row.get("opportunity_cost_score")) >= 40:
        return "Medium"
    return str(row.get("recommendation_confidence") or "Medium")


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


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
