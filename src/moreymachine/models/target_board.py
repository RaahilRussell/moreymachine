"""Assemble explanation-first target boards split by acquisition feasibility.

This is the orchestration layer that turns the candidate universe + role engine
+ scoring engine into the boards a front office actually reads. Every output row
is explanation-first: alongside the numeric scores it carries why_fit, concerns,
the specific Sixers gaps addressed, the projected role next to the PHI core,
salary context, portability/risk summaries, real data sources, missing-data
flags, and an explanation-confidence grade.

Recommendation tiers are strict and capped: at most ten Priority targets, drawn
only from the realistic board, never a current Sixer, star, or missing-contract
player. The unrealistic watchlist is explicitly labelled "theoretical fit only -
not a recommendation".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.features.candidate_universe import (
    FREE_AGENT_TYPES,
    REALISTIC_TYPES,
    TRADE_TYPES,
    WATCHLIST_TYPES,
)
from moreymachine.features.player_roles import ROLE_DIMENSIONS
from moreymachine.models.candidate_scoring import score_candidates
from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_FREE_AGENTS_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_RANKINGS_TRADE_TARGETS_PATH,
    CANDIDATE_RANKINGS_WATCHLIST_PATH,
    CANDIDATE_UNIVERSE_PATH,
    CURRENT_ROSTER_REFERENCE_PATH,
    PLAYER_ROLE_EXPLANATIONS_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    REPORTS_DATA_DIR,
)

ROSTER_GAPS_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.parquet"

MAX_PRIORITY_TARGETS = 10
PRIORITY_MIN_FIT = 60.0
STRONG_MIN_FIT = 56.0
ROLE_PLAYER_MIN_FIT = 50.0

# PHI core pieces a new acquisition is judged next to.
PHI_CORE = ("Joel Embiid", "Tyrese Maxey", "Paul George")

BOARD_COLUMNS = (
    "player_name",
    "current_team",
    "position",
    "role_archetype",
    "candidate_type",
    "recommendation",
    "final_fit",
    "need_match",
    "contender_gain",
    "portability",
    "portability_tier",
    "contract_value",
    "contract_value_tier",
    "acquisition_feasibility_score",
    "risk_score",
    "risk_tier",
    "expected_rotation_role",
    "salary_millions",
    "why_fit",
    "concerns",
    "gaps_addressed",
    "role_on_sixers",
    "acquisition_feasibility",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "data_sources",
    "missing_data_flags",
    "explanation_confidence",
    "gap_specific_scores",
    "player_id",
    "season",
)


@dataclass(frozen=True)
class TargetBoardResult:
    """Summary of a completed target board build."""

    all_rows: int
    realistic_rows: int
    priority_targets: int
    outputs: dict[str, Path]


def build_target_boards(
    *,
    universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    roles_path: str | Path = PLAYER_ROLE_EXPLANATIONS_PATH,
    seasons_path: str | Path = PLAYER_SEASONS_PATH,
    tracking_path: str | Path = PLAYER_TRACKING_PATH,
    roster_gaps_path: str | Path = ROSTER_GAPS_PATH,
    roster_reference_path: str | Path = CURRENT_ROSTER_REFERENCE_PATH,
) -> TargetBoardResult:
    """Score the universe, attach explanations, and write the five split boards."""
    universe = pd.read_parquet(universe_path)
    roles = _optional(roles_path)
    seasons = _latest_seasons(_optional(seasons_path))
    tracking = _optional(tracking_path)
    roster_gaps = _optional(roster_gaps_path)

    merged = _merge_inputs(universe, roles, seasons, tracking)
    scored = score_candidates(merged, roster_gaps=roster_gaps)
    scored = scored.rename(
        columns={"acquisition_feasibility": "acquisition_feasibility_score"}
    )
    scored = _attach_explanations(scored)
    scored = _assign_recommendations(scored)

    board = scored.loc[:, [c for c in BOARD_COLUMNS if c in scored.columns]].copy()

    realistic = board[scored["candidate_type"].isin(REALISTIC_TYPES)].copy()
    free_agents = board[scored["candidate_type"].isin(FREE_AGENT_TYPES)].copy()
    trade = board[scored["candidate_type"].isin(TRADE_TYPES)].copy()
    watchlist = board[scored["candidate_type"].isin(WATCHLIST_TYPES)].copy()

    outputs = {
        "all": Path(CANDIDATE_RANKINGS_ALL_PATH),
        "realistic": Path(CANDIDATE_RANKINGS_REALISTIC_PATH),
        "free_agents": Path(CANDIDATE_RANKINGS_FREE_AGENTS_PATH),
        "trade_targets": Path(CANDIDATE_RANKINGS_TRADE_TARGETS_PATH),
        "unrealistic_watchlist": Path(CANDIDATE_RANKINGS_WATCHLIST_PATH),
    }
    frames = {
        "all": board,
        "realistic": realistic,
        "free_agents": free_agents,
        "trade_targets": trade,
        "unrealistic_watchlist": watchlist,
    }
    for key, path in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        frames[key].sort_values("final_fit", ascending=False).reset_index(
            drop=True
        ).to_parquet(path, index=False)

    _write_roster_reference(universe_path, roster_reference_path)

    priority = int((realistic["recommendation"] == "Priority target").sum())
    return TargetBoardResult(
        all_rows=len(board),
        realistic_rows=len(realistic),
        priority_targets=priority,
        outputs=outputs,
    )


# --------------------------------------------------------------------------- #
# Merge + explanations
# --------------------------------------------------------------------------- #
def _merge_inputs(
    universe: pd.DataFrame,
    roles: pd.DataFrame | None,
    seasons: pd.DataFrame | None,
    tracking: pd.DataFrame | None,
) -> pd.DataFrame:
    merged = universe.copy()
    if roles is not None and not roles.empty:
        role_cols = ["player_id", "role_archetype", "role_confidence", *ROLE_DIMENSIONS]
        role_cols = [c for c in role_cols if c in roles.columns]
        merged = merged.merge(
            roles.loc[:, role_cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    if seasons is not None and not seasons.empty:
        season_cols = [
            c for c in ("player_id", "three_pa", "turnover_pct") if c in seasons.columns
        ]
        merged = merged.merge(
            seasons.loc[:, season_cols].drop_duplicates("player_id"),
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
    if "role_archetype" not in merged.columns:
        merged["role_archetype"] = "Unknown"
    merged["role_archetype"] = merged["role_archetype"].fillna("Unknown")
    return merged


def _attach_explanations(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    frame["role_on_sixers"] = frame.apply(_role_on_sixers, axis=1)
    frame["acquisition_feasibility"] = frame.apply(
        _acquisition_feasibility_text, axis=1
    )
    frame["salary_context"] = frame.apply(_salary_context, axis=1)
    frame["portability_summary"] = frame.apply(_portability_summary, axis=1)
    frame["risk_summary"] = frame.apply(_risk_summary, axis=1)
    frame["data_sources"] = frame.apply(_data_sources, axis=1)
    frame["explanation_confidence"] = frame.apply(_explanation_confidence, axis=1)
    frame["why_fit"] = frame.apply(_why_fit, axis=1)
    frame["concerns"] = frame.apply(_concerns, axis=1)
    if "missing_data_flags" not in frame.columns:
        frame["missing_data_flags"] = "none"
    return frame


def _role_on_sixers(row: pd.Series) -> str:
    archetype = str(row.get("role_archetype") or "Unknown")
    role = str(row.get("expected_rotation_role") or "Rotation")
    gaps = str(row.get("gaps_addressed") or "none")
    notes = []
    if "shooting pressure" in gaps or "role player shooting" in gaps:
        notes.append("spaces the floor for Embiid post-ups and Maxey drives")
    if "defense" in gaps:
        notes.append("adds the wing/rim defense PHI lacks next to Maxey")
    if "rebounding" in gaps:
        notes.append("helps the glass alongside Embiid")
    if "playoff portability proxy" in gaps:
        notes.append("a low-variance piece that holds up in a playoff series")
    if not notes:
        notes.append("depth that does not directly answer the top Sixers gaps")
    return f"Projected {role} minutes as a {archetype}; " + "; ".join(notes) + "."


def _acquisition_feasibility_text(row: pd.Series) -> str:
    candidate_type = str(row.get("candidate_type") or "")
    score = _f(row.get("acquisition_feasibility_score"))
    blurbs = {
        "minimum_candidate": "Signable for the veteran minimum",
        "free_agent": "An unrestricted free agent",
        "mle_candidate": "In MLE range as a free-agent target",
        "likely_free_agent": "On an expiring deal, likely available in free agency",
        "rookie_scale_trade_target": "On a cheap rookie-scale deal; needs a trade",
        "realistic_trade_target": "Movable in a realistic trade package",
        "expensive_trade_target": "Tradeable but expensive; needs salary matching",
        "manual_watchlist": "Tracked manually for situational interest",
        "missing_contract_status": "No contract data - feasibility cannot be priced",
        "unavailable_core_player": "A core piece; realistically not available",
        "star_unrealistic": "A star on a max-tier deal; not realistically acquirable",
    }
    blurb = blurbs.get(candidate_type, "Feasibility unclear")
    return f"{blurb} (feasibility {score:.0f}/100)."


def _salary_context(row: pd.Series) -> str:
    salary = row.get("salary_millions")
    status = str(row.get("contract_status") or "")
    tier = str(row.get("contract_value_tier") or "")
    if salary is None or pd.isna(salary):
        return "No contract row matched; salary unknown."
    status_text = f", {status.replace('_', ' ')}" if status else ""
    return (
        f"${float(salary):.1f}M{status_text}; "
        f"{tier.lower()} relative to projected role value."
    )


def _portability_summary(row: pd.Series) -> str:
    tier = str(row.get("portability_tier") or "")
    score = _f(row.get("portability"))
    return (
        f"{tier} playoff portability ({score:.0f}/100): shooting, low-usage fit, "
        "two-way value and sample size, percentile-scaled within the pool."
    )


def _risk_summary(row: pd.Series) -> str:
    tier = str(row.get("risk_tier") or "")
    score = _f(row.get("risk_score"))
    drivers = []
    minutes = _f(row.get("minutes"))
    age = row.get("age")
    if minutes < 800:
        drivers.append("thin minutes sample")
    if age is not None and pd.notna(age) and (float(age) >= 31 or float(age) < 22):
        drivers.append("age profile")
    if str(row.get("candidate_type")) in ("expensive_trade_target", "star_unrealistic"):
        drivers.append("high acquisition cost")
    if str(row.get("missing_data_flags") or "none") not in ("none", ""):
        drivers.append("missing inputs")
    driver_text = (
        f" Main drivers: {', '.join(drivers)}."
        if drivers
        else " No dominant risk driver."
    )
    return f"{tier} risk ({score:.0f}/100).{driver_text}"


def _data_sources(row: pd.Series) -> str:
    sources = [
        "Stats: nba_api LeagueDash (NBA.com Stats)",
        "Roles: bio + tracking role engine",
    ]
    salary_source = str(row.get("salary_source") or "")
    if salary_source:
        sources.append(f"Salary: {salary_source.split('(')[0].strip()}")
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
    tier = str(row.get("portability_tier") or "")
    if tier in ("Elite", "Strong"):
        parts.append(f"{tier.lower()} playoff portability")
    value_tier = str(row.get("contract_value_tier") or "")
    if value_tier in ("Steal", "Bargain"):
        parts.append(f"a {value_tier.lower()} on its contract")
    role = str(row.get("expected_rotation_role") or "")
    if role in ("Starter", "Star"):
        parts.append(f"projects to {role.lower()}-level minutes")
    return "; ".join(p for p in parts if p) + "."


def _concerns(row: pd.Series) -> str:
    concerns = []
    if str(row.get("risk_tier")) in ("High", "Severe"):
        concerns.append(
            f"{row.get('risk_tier')} risk ({_f(row.get('risk_score')):.0f})"
        )
    if _f(row.get("contract_value")) < 45:
        concerns.append("contract value below market")
    if str(row.get("portability_tier")) in ("Low", "Questionable"):
        concerns.append("portability questionable in a playoff series")
    if str(row.get("gaps_addressed") or "none") == "none":
        concerns.append("does not answer the top Sixers gaps")
    missing = str(row.get("missing_data_flags") or "none")
    if missing not in ("none", ""):
        concerns.append(f"missing data ({missing})")
    return "; ".join(concerns) if concerns else "No major rule-based concerns."


# --------------------------------------------------------------------------- #
# Recommendation tiers (strict + capped)
# --------------------------------------------------------------------------- #
def _assign_recommendations(scored: pd.DataFrame) -> pd.DataFrame:
    frame = scored.copy()
    frame["recommendation"] = "Avoid"

    is_realistic = frame["candidate_type"].isin(REALISTIC_TYPES)
    watch = frame["candidate_type"].isin(
        ("star_unrealistic", "unavailable_core_player")
    )
    missing = frame["candidate_type"] == "missing_contract_status"
    frame.loc[watch, "recommendation"] = "Unrealistic / unavailable"
    frame.loc[missing, "recommendation"] = "Missing data / cannot evaluate"

    realistic = frame[is_realistic].sort_values("final_fit", ascending=False)
    priority_eligible = realistic[
        (realistic["final_fit"] >= PRIORITY_MIN_FIT)
        & (~realistic["risk_tier"].isin(("Severe", "Unknown")))
    ]
    priority_idx = priority_eligible.head(MAX_PRIORITY_TARGETS).index
    frame.loc[priority_idx, "recommendation"] = "Priority target"

    for idx, candidate in realistic.iterrows():
        if idx in priority_idx:
            continue
        fit = float(candidate["final_fit"])
        contract = float(candidate["contract_value"])
        if fit >= STRONG_MIN_FIT and contract >= 50:
            frame.loc[idx, "recommendation"] = "Strong fit if affordable"
        elif fit >= ROLE_PLAYER_MIN_FIT:
            frame.loc[idx, "recommendation"] = "Role-player target"
        elif contract >= 60:
            frame.loc[idx, "recommendation"] = "Only if cheap"
        else:
            frame.loc[idx, "recommendation"] = "Avoid"
    return frame


def _write_roster_reference(
    universe_path: str | Path, roster_reference_path: str | Path
) -> None:
    """Re-emit the current roster reference with role context for the diagnosis page."""
    reference = _optional(roster_reference_path)
    if reference is None or reference.empty:
        return
    roles = _optional(PLAYER_ROLE_EXPLANATIONS_PATH)
    if roles is not None and not roles.empty:
        role_cols = ["player_id", "role_archetype", "role_confidence", *ROLE_DIMENSIONS]
        role_cols = [c for c in role_cols if c in roles.columns]
        reference = reference.merge(
            roles.loc[:, role_cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    Path(roster_reference_path).parent.mkdir(parents=True, exist_ok=True)
    reference.to_parquet(roster_reference_path, index=False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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
