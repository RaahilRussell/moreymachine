"""Fit-score breakdown cards."""

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

PLAYER_FIT_BREAKDOWNS_PATH = REPORTS_DATA_DIR / "player_fit_breakdowns.parquet"
PLAYER_FIT_BREAKDOWNS_JSON_PATH = REPORTS_DATA_DIR / "player_fit_breakdowns.json"

COMPONENTS = (
    ("Need Match", "gap_match_score"),
    ("Skill Evidence", "skill_evidence_score"),
    ("Core Compatibility", "core_compatibility_score"),
    ("Roster Slot Fit", "roster_slot_fit_score"),
    ("Contender Blueprint Fit", "contender_blueprint_fit_score"),
    ("Playoff Role", "playoff_role_score"),
    ("Scenario Robustness", "scenario_robustness_score"),
    ("Acquisition Feasibility", "acquisition_feasibility_score"),
    ("Contract Value", "contract_value_score"),
    ("Risk / Uncertainty", "risk_score"),
)


@dataclass(frozen=True)
class FitBreakdownResult:
    """Summary from building fit breakdowns."""

    rows: int
    parquet_path: Path
    json_path: Path


def build_fit_breakdowns(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    parquet_path: str | Path = PLAYER_FIT_BREAKDOWNS_PATH,
    json_path: str | Path = PLAYER_FIT_BREAKDOWNS_JSON_PATH,
) -> FitBreakdownResult:
    """Build score breakdown report artifacts."""
    rankings = pd.read_parquet(rankings_path)
    rows = [_breakdown_row(row, rankings) for row in rankings.to_dict(orient="records")]
    frame = pd.DataFrame(rows)
    parquet = Path(parquet_path)
    json_output = Path(json_path)
    parquet.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(parquet, index=False)
    json_output.write_text(
        json.dumps(frame.to_dict(orient="records"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    run_id = new_run_id()
    for artifact in (parquet, json_output):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(rankings_path,),
            upstream_artifacts=(rankings_path,),
            known_limitations=(
                "Component grades explain model score construction, not basketball "
                "truth.",
            ),
        )
    return FitBreakdownResult(
        rows=len(frame), parquet_path=parquet, json_path=json_output
    )


def _breakdown_row(row: dict[str, Any], rankings: pd.DataFrame) -> dict[str, Any]:
    cards = [_component_card(row, name, column) for name, column in COMPONENTS]
    strongest = sorted(cards, key=lambda card: card["score"], reverse=True)[:3]
    weakest = sorted(cards, key=lambda card: card["score"])[:3]
    return {
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "final_score": row.get("final_recommendation_score"),
        "tier": row.get("recommendation"),
        "percentile_on_board": _percentile(
            rankings["final_recommendation_score"],
            row.get("final_recommendation_score"),
        ),
        "percentile_within_candidate_type": _within_percentile(
            rankings,
            row,
            "candidate_type",
            "final_recommendation_score",
        ),
        "percentile_within_role_category": _within_percentile(
            rankings,
            row,
            "primary_roster_slot",
            "final_recommendation_score",
        ),
        "component_cards": json.dumps(cards, sort_keys=True),
        "strongest_score_drivers": json.dumps(strongest, sort_keys=True),
        "weakest_score_drivers": json.dumps(weakest, sort_keys=True),
        "score_waterfall_data": json.dumps(_waterfall(row), sort_keys=True),
        "source": "candidate_fit_rankings_v2",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": row.get("missing_data_flags") or "none",
    }


def _component_card(row: dict[str, Any], name: str, column: str) -> dict[str, Any]:
    raw_score = _float(row.get(column))
    score = 100 - raw_score if column == "risk_score" else raw_score
    return {
        "component": name,
        "score": round(score, 2),
        "grade": _grade(score),
        "what_it_means": _component_meaning(name),
        "evidence": row.get("evidence_summary"),
        "why_it_helped_score": _helped_text(name, score),
        "why_it_hurt_score": _hurt_text(name, score),
        "missing_data": row.get("missing_data_flags") or "none",
        "confidence": row.get("recommendation_confidence"),
    }


def _waterfall(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": name, "value": round(_float(row.get(column)), 2)}
        for name, column in COMPONENTS
    ] + [
        {
            "label": "Uncertainty Penalty",
            "value": -_float(row.get("uncertainty_penalty")),
        },
        {
            "label": "Contradiction Penalty",
            "value": -_float(row.get("contradiction_penalty")),
        },
        {"label": "Final", "value": _float(row.get("final_recommendation_score"))},
    ]


def _component_meaning(name: str) -> str:
    meanings = {
        "Need Match": "How directly the player addresses supported Sixers gaps.",
        "Skill Evidence": "How much the public-stat skill profile supports claims.",
        "Core Compatibility": "Fit with Embiid, Maxey, and George.",
        "Roster Slot Fit": "Whether the player has a clear open role on PHI.",
        "Contender Blueprint Fit": (
            "How much the role moves PHI toward contender patterns."
        ),
        "Playoff Role": "Whether the simulated role can survive playoff context.",
        "Scenario Robustness": "How many scenarios remain useful after caveats.",
        "Acquisition Feasibility": "How realistic the acquisition path appears.",
        "Contract Value": "Whether salary context matches the projected role.",
        "Risk / Uncertainty": "How much risk is left after data and role checks.",
    }
    return meanings[name]


def _helped_text(name: str, score: float) -> str:
    if score >= 70:
        return f"{name} is a positive driver."
    if score >= 50:
        return f"{name} is usable but not a standout."
    return f"{name} did not materially help the score."


def _hurt_text(name: str, score: float) -> str:
    if score < 45:
        return f"{name} materially hurt the score."
    if score < 65:
        return f"{name} limited the score."
    return f"{name} did not hurt much."


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _percentile(series: pd.Series, value: Any) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    score = _float(value)
    return round(float((numeric <= score).mean() * 100), 2)


def _within_percentile(
    rankings: pd.DataFrame, row: dict[str, Any], group_col: str, score_col: str
) -> float:
    group = rankings[rankings[group_col] == row.get(group_col)]
    if group.empty:
        return 0.0
    return _percentile(group[score_col], row.get(score_col))


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
