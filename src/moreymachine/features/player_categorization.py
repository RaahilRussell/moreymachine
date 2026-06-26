"""Multidimensional player categorization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.utils.paths import FEATURES_DATA_DIR

PLAYER_CATEGORIZATIONS_PATH = FEATURES_DATA_DIR / "player_categorizations.parquet"


@dataclass(frozen=True)
class PlayerCategorizationResult:
    """Summary from building player categorization tags."""

    rows: int
    manual_review: int
    output_path: Path


def build_player_categorization(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    output_path: str | Path = PLAYER_CATEGORIZATIONS_PATH,
) -> PlayerCategorizationResult:
    """Build tag groups for every v2 candidate."""
    rankings = pd.read_parquet(rankings_path)
    rows = [_categorize(row) for row in rankings.to_dict(orient="records")]
    frame = pd.DataFrame(rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    write_metadata_for_artifact(
        output,
        run_id=new_run_id(),
        source_files=(rankings_path,),
        upstream_artifacts=(rankings_path,),
        known_limitations=(
            "Tags are derived from public-data recommendation artifacts.",
            "Manual review tags depend on transaction and contract freshness.",
        ),
    )
    return PlayerCategorizationResult(
        rows=len(frame),
        manual_review=int(frame["risk_tags"].str.contains("manual_review").sum()),
        output_path=output,
    )


def _categorize(row: dict[str, Any]) -> dict[str, Any]:
    acquisition = _acquisition_tags(row)
    role = _role_tags(row)
    fit = _fit_tags(row)
    need = _need_tags(row)
    risk = _risk_tags(row)
    return {
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "candidate_type": row.get("candidate_type"),
        "recommendation": row.get("recommendation"),
        "primary_roster_slot": row.get("primary_roster_slot"),
        "acquisition_tags": json.dumps(acquisition),
        "role_tags": json.dumps(role),
        "fit_tags": json.dumps(fit),
        "need_tags": json.dumps(need),
        "risk_tags": json.dumps(risk),
        "source": "candidate_fit_rankings_v2",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": row.get("missing_data_flags") or "none",
    }


def _acquisition_tags(row: dict[str, Any]) -> list[str]:
    candidate_type = str(row.get("candidate_type") or "")
    path = str(row.get("acquisition_path") or "")
    tags = []
    mapping = {
        "unrestricted_free_agent": "unrestricted_free_agent",
        "restricted_free_agent": "restricted_free_agent",
        "minimum_candidate": "minimum_candidate",
        "mle_candidate": "mle_candidate",
        "likely_free_agent": "mle_candidate",
        "realistic_trade_target": "medium_trade",
        "expensive_trade_target": "expensive_trade",
        "rookie_scale_trade_target": "rookie_scale_trade",
        "star_unrealistic": "theoretical_only",
        "core_unavailable": "unavailable_core",
        "unavailable_core_player": "unavailable_core",
        "missing_contract_status": "unknown_status",
        "manual_review_needed": "manual_review",
    }
    if candidate_type in mapping:
        tags.append(mapping[candidate_type])
    if path in {"small_trade", "medium_trade", "expensive_trade", "star_trade"}:
        tags.append(path)
    if path == "restricted_free_agent_offer":
        tags.append("restricted_free_agent")
    if bool(row.get("manual_review_required")):
        tags.append("manual_review")
    return _ordered_unique(tags or ["unknown_status"])


def _role_tags(row: dict[str, Any]) -> list[str]:
    slot = str(row.get("primary_roster_slot") or "")
    tags = []
    slot_map = {
        "backup_center": "backup_center",
        "non_embiid_center_minutes": "non_embiid_big",
        "matchup_big": "matchup_big",
        "double_big_stretch_partner": "double_big_partner",
        "stretch_forward": "stretch_big",
        "defensive_forward": "defensive_wing",
        "3_and_d_wing": "defensive_wing",
        "movement_shooter": "movement_shooter",
        "low_usage_spacer": "low_usage_spacer",
        "low_usage_connector": "connector",
        "point_of_attack_defender": "point_of_attack_defender",
        "secondary_creator": "secondary_creator",
        "bench_creator": "bench_creator",
        "regular_season_depth": "regular_season_depth",
        "theoretical_star_upgrade": "developmental_upside",
        "no_clear_role": "no_clear_role",
    }
    if slot in slot_map:
        tags.append(slot_map[slot])
    if bool(row.get("playoff_rotation_possible")):
        tags.append("playoff_rotation_piece")
    if bool(row.get("regular_season_depth_only")):
        tags.append("regular_season_depth")
    return _ordered_unique(tags or ["no_clear_role"])


def _fit_tags(row: dict[str, Any]) -> list[str]:
    score = _float(row.get("final_recommendation_score"))
    recommendation = str(row.get("recommendation") or "")
    tags = []
    if recommendation == "Avoid":
        tags.append("bad_fit")
    elif bool(row.get("manual_review_required")):
        tags.append("missing_data")
    elif score >= 75:
        tags.append("clean_fit")
    elif score >= 65:
        tags.append("role_clear_but_price_sensitive")
    elif score >= 55:
        tags.append("useful_but_limited")
    else:
        tags.append("scenario_dependent")
    if row.get("recommendation") == "Unrealistic / Unavailable":
        tags.append("theoretically_good_unrealistic")
    if row.get("primary_roster_slot") == "theoretical_star_upgrade":
        tags.append("blocked_by_current_roster")
    if _json_list(row.get("contradiction_flags")):
        tags.append("scenario_dependent")
    return _ordered_unique(tags)


def _need_tags(row: dict[str, Any]) -> list[str]:
    gaps = _json_list(row.get("gaps_addressed"))
    tags = []
    text = " ".join(gaps).lower()
    if "backup center" in text or "non-embiid" in text:
        tags.append("solves_backup_center")
    if "wing" in text:
        tags.append("solves_wing_defense")
    if "point-of-attack" in text:
        tags.append("solves_point_of_attack_defense")
    if "shooting" in text or "spacing" in text:
        tags.append("solves_shooting_volume")
    if "movement" in text:
        tags.append("solves_movement_shooting")
    if "bench creation" in text:
        tags.append("solves_bench_creation")
    if "connector" in text:
        tags.append("solves_low_usage_connector")
    if "rebounding" in text:
        tags.append("solves_rebounding")
    if "size" in text or "matchup big" in text:
        tags.append("solves_size")
    if "durability" in text or "depth" in text:
        tags.append("solves_durability_depth")
    return _ordered_unique(tags or ["does_not_solve_major_gap"])


def _risk_tags(row: dict[str, Any]) -> list[str]:
    risk = _float(row.get("risk_score"))
    tags = []
    if risk >= 75:
        tags.append("severe_risk")
    elif risk >= 55:
        tags.append("high_risk")
    elif risk >= 35:
        tags.append("medium_risk")
    else:
        tags.append("low_risk")
    flags = row.get("missing_data_flags") or ""
    if "manual_review" in flags or bool(row.get("manual_review_required")):
        tags.append("manual_review")
    if "stale" in flags:
        tags.append("stale_status_risk")
    if "contract" in flags or "salary" in flags:
        tags.append("contract_risk")
    if _json_list(row.get("contradiction_flags")):
        tags.append("role_risk")
    if not bool(row.get("playoff_rotation_possible")):
        tags.append("playoff_risk")
    if flags and flags != "none":
        tags.append("data_risk")
    return _ordered_unique(tags)


def _json_list(value: Any) -> list[str]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        return [str(item) for item in json.loads(value)]
    except (TypeError, json.JSONDecodeError):
        return [str(value)]


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
