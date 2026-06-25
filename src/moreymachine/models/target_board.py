"""Explanation-first target boards split by acquisition feasibility (max rebuild).

Turns the candidate universe + role engine + scoring engine + roster diagnosis
into the boards a front office reads. Every output row is explanation-first:
alongside the six scores it carries why_fit, concerns, the PHI gaps addressed,
the projected role next to the core, an explicit base/cap/AAV salary breakdown
with source + pulled_at, portability/risk/acquisition summaries, data sources,
missing-data flags, and an explanation-confidence grade.

Recommendation tiers are strict and capped: at most ten Priority targets, drawn
only from the realistic board, never a star, missing-contract, Unknown-role, or
Severe-risk player. The watchlist carries a *theoretical* fit only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.features.candidate_universe import (
    FREE_AGENT_TYPES,
    REALISTIC_TYPES,
    TRADE_TYPES,
    WATCHLIST_TYPES,
)
from moreymachine.features.player_roles import ROLE_DIMENSIONS
from moreymachine.models.scoring import score_candidates
from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_CSV_PATH,
    CANDIDATE_RANKINGS_FREE_AGENTS_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_RANKINGS_TRADE_TARGETS_PATH,
    CANDIDATE_RANKINGS_WATCHLIST_PATH,
    CANDIDATE_UNIVERSE_PATH,
    CONTRACTS_PATH,
    CURRENT_ROSTER_REFERENCE_PATH,
    PLAYER_ROLES_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    REPORTS_DATA_DIR,
)

ROSTER_GAPS_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.parquet"

MAX_PRIORITY_TARGETS = 10
PRIORITY_MIN_FIT = 58.0
STRONG_MIN_FIT = 54.0
ROLE_PLAYER_MIN_FIT = 48.0

PHI_CORE = ("Joel Embiid", "Tyrese Maxey", "Paul George", "VJ Edgecombe")

BOARD_COLUMNS = (
    "player_name",
    "current_team",
    "position",
    "role_archetype",
    "expected_role",
    "role_confidence",
    "candidate_type",
    "candidate_status_freshness",
    "transaction_review_reason",
    "latest_transaction_date",
    "latest_transaction_type",
    "latest_transaction_description",
    "transaction_source",
    "salary_pulled_at",
    "board_type",
    "recommendation",
    "final_fit",
    "theoretical_fit",
    "need_match",
    "contender_gain",
    "marginal_contender_delta",
    "expected_minutes_share",
    "portability",
    "portability_tier",
    "contract_value",
    "salary_bucket",
    "salary_percentile_within_role",
    "surplus_or_overpay_label",
    "risk_score",
    "risk_tier",
    "acquisition_feasibility",
    "feasibility_tier",
    "base_salary_millions",
    "cap_hit_millions",
    "contract_aav_millions",
    "contract_status",
    "free_agent_year",
    "salary_source",
    "source_url",
    "pulled_at",
    "gaps_addressed",
    "gap_specific_scores",
    "role_on_sixers",
    "why_fit",
    "why_need_match",
    "why_contender_gain",
    "concerns",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "acquisition_summary",
    "data_sources",
    "missing_data_flags",
    "explanation_confidence",
    "player_id",
    "season",
)


@dataclass(frozen=True)
class TargetBoardResult:
    """Summary of a target board build."""

    all_rows: int
    realistic_rows: int
    priority_targets: int
    outputs: dict[str, Path]
    csv_path: Path


def build_target_boards(
    *,
    universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    roles_path: str | Path = PLAYER_ROLES_PATH,
    seasons_path: str | Path = PLAYER_SEASONS_PATH,
    tracking_path: str | Path = PLAYER_TRACKING_PATH,
    contracts_path: str | Path = CONTRACTS_PATH,
    roster_gaps_path: str | Path = ROSTER_GAPS_PATH,
    roster_reference_path: str | Path = CURRENT_ROSTER_REFERENCE_PATH,
) -> TargetBoardResult:
    """Score the universe, attach explanations, and write the five split boards."""
    universe = pd.read_parquet(universe_path)
    roles = _optional(roles_path)
    seasons = _latest_seasons(_optional(seasons_path))
    tracking = _optional(tracking_path)
    contracts = _optional(contracts_path)
    roster_gaps = _optional(roster_gaps_path)

    merged = _merge_inputs(universe, roles, seasons, tracking, contracts)
    scored = score_candidates(merged, roster_gaps=roster_gaps)
    scored = _attach_explanations(scored)
    scored = _force_top50_transaction_review(scored)
    scored = _assign_recommendations(scored)

    board = scored.loc[:, [c for c in BOARD_COLUMNS if c in scored.columns]].copy()
    types = scored["candidate_type"]

    frames = {
        "all": board,
        "realistic": board[types.isin(REALISTIC_TYPES)].copy(),
        "free_agents": board[types.isin(FREE_AGENT_TYPES)].copy(),
        "trade_targets": board[types.isin(TRADE_TYPES)].copy(),
        "unrealistic_watchlist": board[types.isin(WATCHLIST_TYPES)].copy(),
    }
    outputs = {
        "all": Path(CANDIDATE_RANKINGS_ALL_PATH),
        "realistic": Path(CANDIDATE_RANKINGS_REALISTIC_PATH),
        "free_agents": Path(CANDIDATE_RANKINGS_FREE_AGENTS_PATH),
        "trade_targets": Path(CANDIDATE_RANKINGS_TRADE_TARGETS_PATH),
        "unrealistic_watchlist": Path(CANDIDATE_RANKINGS_WATCHLIST_PATH),
    }
    for key, path in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        frames[key].sort_values("final_fit", ascending=False).reset_index(
            drop=True
        ).to_parquet(path, index=False)

    csv_path = Path(CANDIDATE_RANKINGS_CSV_PATH)
    board.sort_values("final_fit", ascending=False).to_csv(csv_path, index=False)
    _write_roster_reference(roster_reference_path)

    realistic = frames["realistic"]
    priority = int((realistic["recommendation"] == "Priority Target").sum())
    return TargetBoardResult(
        all_rows=len(board),
        realistic_rows=len(realistic),
        priority_targets=priority,
        outputs=outputs,
        csv_path=csv_path,
    )


def _merge_inputs(universe, roles, seasons, tracking, contracts) -> pd.DataFrame:
    merged = universe.copy()
    if roles is not None and not roles.empty:
        role_cols = [
            c
            for c in (
                "player_id",
                "role_archetype",
                "expected_role",
                "role_confidence",
                "role_concerns",
                *ROLE_DIMENSIONS,
            )
            if c in roles.columns
        ]
        merged = merged.merge(
            roles.loc[:, role_cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    if seasons is not None and not seasons.empty:
        cols = [
            c for c in ("player_id", "three_pa", "turnover_pct") if c in seasons.columns
        ]
        merged = merged.merge(
            seasons.loc[:, cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    if tracking is not None and not tracking.empty and "catch_shoot_fg3a" in tracking:
        merged = merged.merge(
            tracking.loc[:, ["player_id", "catch_shoot_fg3a"]].drop_duplicates(
                "player_id"
            ),
            on="player_id",
            how="left",
        )
    if contracts is not None and not contracts.empty:
        cols = [
            c
            for c in ("player_id", "source_url", "pulled_at", "salary_context")
            if c in contracts.columns
        ]
        merged = merged.merge(
            contracts.loc[:, cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    for column, default in (
        ("role_archetype", "Unknown"),
        ("expected_role", "Unknown"),
        ("role_confidence", "low"),
    ):
        if column not in merged.columns:
            merged[column] = default
        merged[column] = merged[column].fillna(default)
    return merged


def _attach_explanations(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    frame["board_type"] = frame["candidate_type"].map(_board_type)
    frame["role_on_sixers"] = frame.apply(_role_on_sixers, axis=1)
    frame["acquisition_summary"] = frame.apply(_acquisition_summary, axis=1)
    frame["portability_summary"] = frame.apply(_portability_summary, axis=1)
    frame["risk_summary"] = frame.apply(_risk_summary, axis=1)
    frame["data_sources"] = frame.apply(_data_sources, axis=1)
    frame["explanation_confidence"] = frame.apply(_explanation_confidence, axis=1)
    frame["why_fit"] = frame.apply(_why_fit, axis=1)
    frame["concerns"] = frame.apply(_concerns, axis=1)
    if "salary_context" not in frame.columns:
        frame["salary_context"] = frame.apply(_fallback_salary_context, axis=1)
    frame["salary_context"] = frame["salary_context"].fillna(
        frame.apply(_fallback_salary_context, axis=1)
    )
    return frame


def _board_type(candidate_type: str) -> str:
    if candidate_type in FREE_AGENT_TYPES:
        return "free_agent"
    if candidate_type in TRADE_TYPES:
        return "trade_target"
    if candidate_type in WATCHLIST_TYPES:
        return "unrealistic_watchlist"
    return "other"


def _role_on_sixers(row: pd.Series) -> str:
    archetype = str(row.get("role_archetype") or "Unknown")
    role = str(row.get("expected_role") or "Rotation Player")
    gaps = str(row.get("gaps_addressed") or "none")
    notes = []
    if "shooting" in gaps or "spacing" in gaps:
        notes.append("spaces the floor for Embiid post-ups and Maxey drives")
    if "defense" in gaps or "rim protection" in gaps:
        notes.append("adds the perimeter/rim defense PHI lacks")
    if "rebounding" in gaps:
        notes.append("helps the glass")
    if "connector" in gaps or "turnover" in gaps:
        notes.append("a secure connector when the stars are blitzed")
    if not notes:
        notes.append("rotation depth that does not directly answer the top gaps")
    return f"Projected {role} as a {archetype}; " + "; ".join(notes) + "."


def _acquisition_summary(row: pd.Series) -> str:
    tier = str(row.get("feasibility_tier") or "Unknown")
    score = _f(row.get("acquisition_feasibility"))
    reason = str(row.get("acquisition_reason") or "")
    return f"{tier} to acquire ({score:.0f}/100). {reason}".strip()


def _portability_summary(row: pd.Series) -> str:
    tier = str(row.get("portability_tier") or "")
    score = _f(row.get("portability"))
    reasons = str(row.get("portability_reasons") or "")
    concerns = str(row.get("portability_concerns") or "")
    return f"{tier} ({score:.0f}/100). Holds up: {reasons}. Watch: {concerns}."


def _risk_summary(row: pd.Series) -> str:
    tier = str(row.get("risk_tier") or "")
    score = _f(row.get("risk_score"))
    reasons = str(row.get("risk_reasons") or "")
    return f"{tier} risk ({score:.0f}/100). Drivers: {reasons}."


def _data_sources(row: pd.Series) -> str:
    sources = [
        "Stats: nba_api LeagueDash (NBA.com Stats)",
        "Roles: real bio + tracking role engine",
        "Gaps: PHI roster diagnosis",
    ]
    salary_source = str(row.get("salary_source") or "")
    if salary_source:
        sources.append(f"Salary: {salary_source.split('(')[0].strip()}")
    transaction_source = str(row.get("transaction_source") or "")
    if transaction_source:
        sources.append(f"Transactions: {transaction_source}")
    return "; ".join(sources)


def _explanation_confidence(row: pd.Series) -> str:
    confidence = str(row.get("role_confidence") or "medium").lower()
    missing = str(row.get("missing_data_flags") or "none")
    minutes = _f(row.get("minutes"))
    if confidence == "low" or missing.count(";") >= 2 or minutes < 400:
        return "low"
    if confidence == "high" and missing in ("none", "") and minutes >= 1200:
        return "high"
    return "medium"


def _why_fit(row: pd.Series) -> str:
    parts = [str(row.get("why_need_match") or "")]
    if str(row.get("portability_tier")) in ("Elite", "Strong"):
        parts.append(f"{str(row.get('portability_tier')).lower()} playoff portability")
    if str(row.get("surplus_or_overpay_label")) in ("Steal", "Bargain"):
        parts.append(f"a {str(row.get('surplus_or_overpay_label')).lower()} on salary")
    if str(row.get("expected_role")) in ("Starter", "High-Level Starter", "Star"):
        parts.append(f"projects to {str(row.get('expected_role')).lower()} minutes")
    return "; ".join(p for p in parts if p) + "."


def _concerns(row: pd.Series) -> str:
    concerns = []
    if str(row.get("risk_tier")) in ("High", "Severe"):
        concerns.append(
            f"{row.get('risk_tier')} risk ({_f(row.get('risk_score')):.0f})"
        )
    pconc = str(row.get("portability_concerns") or "")
    if pconc and "no major" not in pconc:
        concerns.append(pconc)
    rconc = str(row.get("role_concerns") or "")
    if rconc and "no major" not in rconc:
        concerns.append(rconc)
    missing = str(row.get("missing_data_flags") or "none")
    if missing not in ("none", ""):
        concerns.append(f"missing data ({missing})")
    freshness = str(row.get("candidate_status_freshness") or "verified_current")
    if freshness != "verified_current":
        reason = row.get("transaction_review_reason", "")
        concerns.append(
            f"transaction freshness {freshness}: {reason}"
        )
    return "; ".join(concerns) if concerns else "No major rule-based concerns."


def _fallback_salary_context(row: pd.Series) -> str:
    cap = row.get("cap_hit_millions")
    status = str(row.get("contract_status") or "unknown").replace("_", " ")
    if cap is None or pd.isna(cap):
        return f"No cap figure matched; status {status}."
    return f"${float(cap):.1f}M cap hit ({status})."


# --------------------------------------------------------------------------- #
# Recommendation tiers (strict + capped)
# --------------------------------------------------------------------------- #
def _assign_recommendations(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    frame["recommendation"] = "Avoid"

    is_realistic = frame["candidate_type"].isin(REALISTIC_TYPES)
    watch = frame["candidate_type"].isin(WATCHLIST_TYPES) & (
        frame["candidate_type"] != "missing_contract_status"
    )
    missing = frame["candidate_type"] == "missing_contract_status"
    frame.loc[watch, "recommendation"] = "Unrealistic / Unavailable"
    frame.loc[
        frame["candidate_type"].eq("manual_review_needed"),
        "recommendation",
    ] = "Manual Review Required"
    frame.loc[
        frame["candidate_type"].eq("contract_blocked"),
        "recommendation",
    ] = "Contract Blocked"
    frame.loc[missing, "recommendation"] = "Missing Data / Cannot Evaluate"

    realistic = frame[is_realistic].sort_values("final_fit", ascending=False)
    priority_eligible = realistic[
        (realistic["final_fit"] >= PRIORITY_MIN_FIT)
        & (~realistic["risk_tier"].isin(("Severe", "Unknown")))
        & (realistic["expected_role"] != "Unknown")
        & (
            ~realistic.get(
                "candidate_status_freshness", pd.Series("", index=realistic.index)
            ).isin(("stale_needs_review", "manual_verification_required"))
        )
    ]
    priority_idx = priority_eligible.head(MAX_PRIORITY_TARGETS).index
    frame.loc[priority_idx, "recommendation"] = "Priority Target"

    for idx, row in realistic.iterrows():
        if idx in priority_idx:
            continue
        fit = float(row["final_fit"])
        contract = float(row["contract_value"])
        if fit >= STRONG_MIN_FIT and contract >= 50:
            frame.loc[idx, "recommendation"] = "Strong Fit If Affordable"
        elif fit >= ROLE_PLAYER_MIN_FIT:
            frame.loc[idx, "recommendation"] = "Role-Player Target"
        elif contract >= 60:
            frame.loc[idx, "recommendation"] = "Only If Cheap"
        else:
            frame.loc[idx, "recommendation"] = "Avoid"
    return frame


def _force_top50_transaction_review(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    if "candidate_status_freshness" not in frame.columns:
        frame["candidate_status_freshness"] = "verified_current"
    if "transaction_review_reason" not in frame.columns:
        frame["transaction_review_reason"] = "No transaction review data."

    top_indexes: set = set()
    realistic = frame[frame["candidate_type"].isin(REALISTIC_TYPES)].sort_values(
        "final_fit",
        ascending=False,
    )
    top_indexes.update(realistic.head(50).index)
    free_agents = frame[frame["candidate_type"].isin(FREE_AGENT_TYPES)].sort_values(
        "final_fit",
        ascending=False,
    )
    top_indexes.update(free_agents.head(50).index)
    if not top_indexes:
        return frame

    for idx in top_indexes:
        if _transaction_after_salary(frame.loc[idx]):
            prior_type = str(frame.at[idx, "candidate_type"])
            frame.at[idx, "candidate_status_freshness"] = "manual_verification_required"
            frame.at[idx, "transaction_review_reason"] = (
                "Top-50 realistic/free-agent target has a transaction newer than "
                "the salary pull date; manual verification required before ranking."
            )
            frame.at[idx, "candidate_type"] = "manual_review_needed"
            frame.at[idx, "candidate_type_reason"] = (
                str(frame.loc[idx].get("candidate_type_reason") or "")
                + f" Moved from {prior_type} by transaction freshness review."
            ).strip()
    frame["board_type"] = frame["candidate_type"].map(_board_type)
    return frame


def _transaction_after_salary(row: pd.Series) -> bool:
    tx_date = pd.to_datetime(
        row.get("latest_transaction_date"), errors="coerce", utc=True
    )
    salary_date = pd.to_datetime(row.get("salary_pulled_at"), errors="coerce", utc=True)
    if pd.isna(tx_date) or pd.isna(salary_date):
        return False
    return tx_date.date() > salary_date.date()


def _write_roster_reference(roster_reference_path: str | Path) -> None:
    reference = _optional(roster_reference_path)
    if reference is None or reference.empty:
        return
    roles = _optional(PLAYER_ROLES_PATH)
    if roles is not None and not roles.empty:
        role_cols = [
            c
            for c in ("player_id", "role_archetype", "expected_role", *ROLE_DIMENSIONS)
            if c in roles.columns
        ]
        reference = reference.merge(
            roles.loc[:, role_cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    Path(roster_reference_path).parent.mkdir(parents=True, exist_ok=True)
    reference.to_parquet(roster_reference_path, index=False)


def _latest_seasons(seasons: pd.DataFrame | None) -> pd.DataFrame | None:
    if seasons is None or seasons.empty or "season" not in seasons.columns:
        return seasons
    return seasons.sort_values("season").drop_duplicates("player_id", keep="last")


def _optional(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None


def _f(value: object) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(numeric) else float(numeric)


def gap_scores_dict(value: object) -> dict:
    """Parse a gap_specific_scores JSON string into a dict (for the app)."""
    try:
        return json.loads(value) if isinstance(value, str) and value else {}
    except json.JSONDecodeError:
        return {}


def build_timestamp() -> str:
    return datetime.now(UTC).isoformat()
