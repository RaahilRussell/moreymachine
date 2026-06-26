"""Player help-impact summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.gap_model import SIXERS_GAP_MODEL_PATH
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR

PLAYER_HELP_IMPACT_PATH = FEATURES_DATA_DIR / "player_help_impact.parquet"


@dataclass(frozen=True)
class HelpImpactResult:
    """Summary from building player help-impact rows."""

    rows: int
    players_with_help: int
    output_path: Path


def build_help_impact(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    gap_model_path: str | Path = SIXERS_GAP_MODEL_PATH,
    output_path: str | Path = PLAYER_HELP_IMPACT_PATH,
) -> HelpImpactResult:
    """Build help and does-not-help summaries for every candidate."""
    rankings = pd.read_parquet(rankings_path)
    gaps = pd.read_parquet(gap_model_path)
    gap_lookup = {str(row["gap_name"]): row for row in gaps.to_dict(orient="records")}
    rows = [_help_row(row, gap_lookup) for row in rankings.to_dict(orient="records")]
    frame = pd.DataFrame(rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    write_metadata_for_artifact(
        output,
        run_id=new_run_id(),
        source_files=(rankings_path, gap_model_path),
        upstream_artifacts=(rankings_path, gap_model_path),
        known_limitations=(
            "Help areas inherit v2 skill-permission gates.",
            "Does-not-help rows are gap-model summaries, not scouting reports.",
        ),
    )
    return HelpImpactResult(
        rows=len(frame),
        players_with_help=int(frame["top_help_areas"].str.len().gt(2).sum()),
        output_path=output,
    )


def _help_row(
    row: dict[str, Any], gap_lookup: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    addressed = _json_list(row.get("gaps_addressed"))
    not_addressed = _json_list(row.get("gaps_not_addressed"))
    top_help = [
        _help_area(row, gap_lookup[name]) for name in addressed if name in gap_lookup
    ]
    top_help = sorted(
        top_help,
        key=lambda item: (item["severity_of_sixers_gap"], item["player_skill_score"]),
        reverse=True,
    )[:5]
    misses = [
        _does_not_help(row, gap_lookup[name])
        for name in not_addressed
        if name in gap_lookup
    ][:5]
    return {
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "top_help_areas": json.dumps(top_help, sort_keys=True),
        "does_not_help": json.dumps(misses, sort_keys=True),
        "helps_most_summary": _summary(top_help),
        "does_not_help_summary": _miss_summary(misses),
        "source": "candidate_fit_rankings_v2 + sixers_gap_model",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": row.get("missing_data_flags") or "none",
    }


def _help_area(row: dict[str, Any], gap: dict[str, Any]) -> dict[str, Any]:
    return {
        "help_area": gap["gap_name"],
        "severity_of_sixers_gap": float(gap.get("severity") or 0),
        "player_skill_score": _float(row.get("skill_evidence_score")),
        "evidence": row.get("evidence_summary"),
        "confidence": row.get("recommendation_confidence"),
        "expected_role_context": row.get("expected_role_on_phi"),
        "why_it_matters": gap.get("why_it_matters"),
        "limitations": _json_list(gap.get("what_does_not_fix_it")),
    }


def _does_not_help(row: dict[str, Any], gap: dict[str, Any]) -> dict[str, Any]:
    return {
        "gap": gap["gap_name"],
        "reason": (
            f"Current role is {row.get('expected_role_on_phi')}; this gap requires "
            f"{gap.get('roster_slot_needed')} and skills "
            f"{gap.get('skill_requirements')}."
        ),
        "whether_it_matters": "high"
        if float(gap.get("severity") or 0) >= 15
        else "medium",
    }


def _summary(help_areas: list[dict[str, Any]]) -> str:
    if not help_areas:
        return "No major supported help area from current evidence."
    return "; ".join(
        f"{item['help_area']} ({item['expected_role_context']})"
        for item in help_areas[:3]
    )


def _miss_summary(misses: list[dict[str, Any]]) -> str:
    if not misses:
        return "No major unaddressed top gap listed."
    return "; ".join(item["gap"] for item in misses[:3])


def _json_list(value: Any) -> list[Any]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
