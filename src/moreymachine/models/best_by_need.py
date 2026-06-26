"""Best-by-need rankings."""

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

BEST_BY_NEED_PATH = REPORTS_DATA_DIR / "best_by_need.parquet"

NEEDS = {
    "backup_center": ("backup center", "non-embiid", "matchup big"),
    "non_embiid_rim_protection": ("rim protection without embiid",),
    "wing_defense": ("wing defense",),
    "point_of_attack_defense": ("point-of-attack defense",),
    "shooting_volume": ("shooting", "spacing"),
    "movement_shooting": ("movement shooting",),
    "bench_creation": ("bench creation",),
    "low_usage_connector": ("connector", "turnover control", "usage balance"),
    "rebounding": ("rebounding",),
    "size": ("size", "matchup big"),
    "regular_season_depth": ("depth", "durability"),
    "playoff_rotation_piece": ("closing lineup", "playoff"),
    "stretch_forward": ("stretch-forward",),
    "matchup_big": ("matchup big",),
}


@dataclass(frozen=True)
class BestByNeedResult:
    """Summary from building best-by-need rankings."""

    rows: int
    output_path: Path


def build_best_by_need(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    output_path: str | Path = BEST_BY_NEED_PATH,
) -> BestByNeedResult:
    """Build best-by-need ranking rows."""
    rankings = pd.read_parquet(rankings_path)
    rows = [
        _need_row(need_id, keywords, rankings) for need_id, keywords in NEEDS.items()
    ]
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
            "Need rankings only include gaps the v2 engine says are supported.",
        ),
    )
    return BestByNeedResult(rows=len(frame), output_path=output)


def _need_row(
    need_id: str, keywords: tuple[str, ...], rankings: pd.DataFrame
) -> dict[str, Any]:
    mask = (
        rankings["gaps_addressed"]
        .fillna("")
        .str.lower()
        .apply(lambda text: any(keyword in text for keyword in keywords))
    )
    pool = rankings[mask].sort_values("final_recommendation_score", ascending=False)
    realistic = pool[
        pool["board_type"].isin(["realistic", "free_agent", "trade_target"])
    ]
    free_agents = pool[pool["board_type"] == "free_agent"]
    trade = pool[pool["board_type"] == "trade_target"]
    low_cost = pool[_low_cost_mask(pool)]
    high_upside = pool[pool["recommendation"].isin(["Strong Fit If Affordable"])]
    return {
        "need_id": need_id,
        "need_name": need_id.replace("_", " ").title(),
        "top_players": json.dumps(_players(pool)),
        "realistic_only_top_players": json.dumps(_players(realistic)),
        "free_agent_top_players": json.dumps(_players(free_agents)),
        "trade_target_top_players": json.dumps(_players(trade)),
        "low_cost_top_players": json.dumps(_players(low_cost)),
        "high_upside_top_players": json.dumps(_players(high_upside)),
        "why_these_players_fit": _why_fit(pool, need_id),
        "what_to_watch_out_for": _watch(pool),
        "source": "candidate_fit_rankings_v2",
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": _missing(pool),
    }


def _players(frame: pd.DataFrame, limit: int = 10) -> list[dict[str, Any]]:
    cols = [
        "player_id",
        "player_name",
        "recommendation",
        "final_recommendation_score",
        "primary_roster_slot",
        "acquisition_path",
        "board_type",
    ]
    return frame.head(limit)[cols].to_dict(orient="records")


def _low_cost_mask(frame: pd.DataFrame) -> pd.Series:
    if "cap_hit_millions" in frame.columns:
        return (
            pd.to_numeric(frame["cap_hit_millions"], errors="coerce").fillna(99) <= 14
        )
    path = frame["acquisition_path"].fillna("").astype(str)
    candidate_type = frame["candidate_type"].fillna("").astype(str)
    return path.isin(["minimum_signing", "mle_or_exception_signing", "small_trade"]) | (
        candidate_type.isin(["minimum_candidate", "mle_candidate"])
    )


def _why_fit(frame: pd.DataFrame, need_id: str) -> str:
    if frame.empty:
        return f"No supported candidates for {need_id} from current evidence."
    names = ", ".join(frame["player_name"].head(3).astype(str).tolist())
    return f"Top options for {need_id} have supported gap claims: {names}."


def _watch(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Need may require manual sourcing or different candidate pool."
    flagged = int(frame["manual_review_required"].sum())
    return (
        f"Watch acquisition price, role specificity, and stale data. "
        f"{flagged} listed options require manual review."
    )


def _missing(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "no_supported_players"
    flags = set()
    for value in frame["missing_data_flags"].head(20):
        flags.update(str(value).split(";"))
    flags.discard("none")
    return ";".join(sorted(flag for flag in flags if flag)) or "none"
