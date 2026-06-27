"""GM action-card builder."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_json_artifact, write_metadata_for_artifact
from moreymachine.models.move_recommendations import MOVE_RECOMMENDATIONS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

ACTION_CARDS_PATH = REPORTS_DATA_DIR / "action_cards.parquet"
ACTION_CARDS_JSON_PATH = REPORTS_DATA_DIR / "action_cards.json"

ACTION_CATEGORIES = (
    "best_overall_action",
    "best_realistic_free_agent",
    "best_realistic_trade",
    "best_low_cost_depth",
    "best_backup_center_route",
    "best_wing_defense_route",
    "best_shooting_route",
    "best_internal_or_stay_put",
    "top_avoid_move",
    "manual_review_action",
)


@dataclass(frozen=True)
class ActionCardResult:
    """Summary for action-card build."""

    rows: int
    output_path: Path
    json_path: Path


def build_action_cards(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    move_recommendations_path: str | Path = MOVE_RECOMMENDATIONS_PATH,
    output_path: str | Path = ACTION_CARDS_PATH,
    json_path: str | Path = ACTION_CARDS_JSON_PATH,
) -> ActionCardResult:
    """Build one card per required executive action category."""
    normalized_team = str(team or "PHI").upper()
    context = context or {}
    moves = pd.read_parquet(move_recommendations_path)
    rows = [
        _card_for_category(category, moves, normalized_team, context)
        for category in ACTION_CATEGORIES
    ]
    frame = pd.DataFrame(rows)
    output = Path(output_path)
    json_output = Path(json_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    write_json_artifact(frame.to_dict(orient="records"), json_output, _metadata(normalized_team, new_run_id(), (move_recommendations_path,)))
    run_id = new_run_id()
    write_metadata_for_artifact(
        output,
        run_id=run_id,
        source_files=(move_recommendations_path,),
        upstream_artifacts=(move_recommendations_path,),
        known_limitations=(
            "Action cards are deterministic summaries of structured move rows.",
            "Missing action categories are explicit partial cards, not invented moves.",
        ),
    )
    return ActionCardResult(rows=len(frame), output_path=output, json_path=json_output)


def _card_for_category(
    category: str,
    moves: pd.DataFrame,
    team: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    selectors: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "best_overall_action": _best_overall,
        "best_realistic_free_agent": lambda frame: _best_where(frame, frame["action_type"].eq("free_agent")),
        "best_realistic_trade": lambda frame: _best_where(frame, frame["action_type"].eq("trade")),
        "best_low_cost_depth": _best_low_cost,
        "best_backup_center_route": lambda frame: _best_text_match(frame, "roster_slot", ("backup_center", "non_embiid_center", "matchup_big")),
        "best_wing_defense_route": lambda frame: _best_text_match(frame, "why_do_this", ("wing", "defense", "3_and_d")),
        "best_shooting_route": lambda frame: _best_text_match(frame, "why_do_this", ("shooting", "spacer", "spacing", "movement")),
        "top_avoid_move": lambda frame: _best_where(frame, frame["action_type"].eq("avoid")),
        "manual_review_action": lambda frame: _best_where(frame, frame["action_type"].eq("manual_review")),
    }
    if category == "best_internal_or_stay_put":
        return _stay_put_card(team, context)
    selector = selectors[category]
    selected = selector(moves)
    if selected.empty:
        return _partial_card(category, team)
    row = selected.to_dict()
    return {
        "team_abbr": team,
        "action_category": category,
        "action_title": _title(category, row),
        "player_id": row.get("player_id"),
        "player_profile_id": row.get("player_profile_id"),
        "player_name": row.get("player_name"),
        "recommendation": row.get("recommendation"),
        "action_type": row.get("action_type"),
        "move_score": row.get("move_score"),
        "priority": _priority(category, row),
        "why_do_this": row.get("why_do_this"),
        "why_not_do_this": row.get("why_not_do_this"),
        "evidence": row.get("evidence"),
        "confidence": row.get("confidence"),
        "status": "ready",
        "missing_data_flags": row.get("missing_data_flags") or "none",
        "source": "move_recommendations",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
    }


def _best_overall(frame: pd.DataFrame) -> pd.Series:
    mask = ~frame["action_type"].isin(["avoid", "manual_review"])
    mask &= ~frame["recommendation"].isin(["Avoid", "Unrealistic / Unavailable"])
    return _best_where(frame, mask)


def _best_low_cost(frame: pd.DataFrame) -> pd.Series:
    mask = frame["acquisition_path"].fillna("").str.contains("minimum|small_trade|exception", case=False)
    mask &= ~frame["action_type"].isin(["avoid", "manual_review"])
    return _best_where(frame, mask)


def _best_text_match(
    frame: pd.DataFrame,
    column: str,
    terms: tuple[str, ...],
) -> pd.Series:
    text = frame[column].fillna("").astype(str).str.lower()
    mask = pd.Series(False, index=frame.index)
    for term in terms:
        mask |= text.str.contains(term, regex=False)
    mask &= ~frame["action_type"].isin(["avoid", "manual_review"])
    return _best_where(frame, mask)


def _best_where(frame: pd.DataFrame, mask: pd.Series) -> pd.Series:
    subset = frame[mask].copy()
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.sort_values(["move_score", "player_name"], ascending=[False, True]).iloc[0]


def _stay_put_card(team: str, context: dict[str, Any]) -> dict[str, Any]:
    evidence = {
        "context_mode": context.get("context_mode", "unknown"),
        "rule": "stay_put_when_role_or_status_is_unclear",
    }
    return {
        "team_abbr": team,
        "action_category": "best_internal_or_stay_put",
        "action_title": "Stay put before spending assets on unclear roles",
        "player_id": None,
        "player_profile_id": "",
        "player_name": "Internal / stay put",
        "recommendation": "Internal / Stay Put",
        "action_type": "internal_or_stay_put",
        "move_score": 50.0,
        "priority": "medium",
        "why_do_this": "Preserve flexibility when the board shows high opportunity cost, stale status, or no clear role.",
        "why_not_do_this": "Staying put does not solve the highest roster gaps by itself.",
        "evidence": json.dumps(evidence, sort_keys=True),
        "confidence": "Medium",
        "status": "ready",
        "missing_data_flags": "none",
        "source": "manual_team_context + move_recommendations",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
    }


def _partial_card(category: str, team: str) -> dict[str, Any]:
    evidence = {
        "category": category,
        "reason": "No candidate row satisfied the category filters.",
    }
    return {
        "team_abbr": team,
        "action_category": category,
        "action_title": _title(category, {}),
        "player_id": None,
        "player_profile_id": "",
        "player_name": "",
        "recommendation": "No supported action",
        "action_type": "partial",
        "move_score": 0.0,
        "priority": "low",
        "why_do_this": "No supported player action exists for this category in the current structured board.",
        "why_not_do_this": "Creating a player recommendation here would require unsupported availability, role, or evidence assumptions.",
        "evidence": json.dumps(evidence, sort_keys=True),
        "confidence": "Low",
        "status": "partial",
        "missing_data_flags": "no_supported_candidate_for_category",
        "source": "move_recommendations",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
    }


def _title(category: str, row: dict[str, Any]) -> str:
    labels = {
        "best_overall_action": "Best overall action",
        "best_realistic_free_agent": "Best realistic free-agent action",
        "best_realistic_trade": "Best realistic trade action",
        "best_low_cost_depth": "Best low-cost depth action",
        "best_backup_center_route": "Best backup-center route",
        "best_wing_defense_route": "Best wing-defense route",
        "best_shooting_route": "Best shooting route",
        "top_avoid_move": "Top avoid move",
        "manual_review_action": "Manual review action",
    }
    label = labels.get(category, category.replace("_", " ").title())
    player = row.get("player_name") if row else ""
    return f"{label}: {player}" if player else label


def _priority(category: str, row: dict[str, Any]) -> str:
    if category in {"best_overall_action", "top_avoid_move"}:
        return "high"
    if float(row.get("move_score") or 0) >= 65:
        return "high"
    return "medium"


def _metadata(team: str, run_id: str, sources: tuple[str | Path, ...]) -> dict[str, Any]:
    return {
        "artifact_name": "action_cards",
        "team": team,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source_files": [str(Path(source)) for source in sources],
        "upstream_artifacts": [str(Path(source)) for source in sources],
        "data_mode": "derived",
        "known_limitations": [
            "Action-card JSON is generated from structured move recommendations.",
        ],
    }
