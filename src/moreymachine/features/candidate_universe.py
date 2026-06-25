"""Assign every real player exactly one acquisition candidate type + feasibility.

This rebuild keys candidate classification off the *explicit* contract schema
(cap hit, contract_status category, free-agency year) rather than a vague salary
number, and adds an acquisition-feasibility score, tier, and reason that weigh
contract status, salary, and how important the player is to his current team.

Hard rules enforced here:
* Current Sixers are pulled off the acquisition board into a roster reference.
* Stars and missing-contract players can never be a realistic/Priority target.
* Long-term high-quality core players are ``unavailable_core_player`` (not a
  realistic trade target) unless a manual override says otherwise.
* Unknown contracts are never silently turned into free agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    CANDIDATE_UNIVERSE_SUMMARY_PATH,
    CANDIDATES_PATH,
    CONTRACTS_PATH,
    CURRENT_ROSTER_REFERENCE_PATH,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
)

PHI_ROSTER_2025_26 = (
    "Adem Bona",
    "Andre Drummond",
    "Cameron Payne",
    "Dalen Terry",
    "Dominick Barlow",
    "Eric Gordon",
    "Hunter Sallis",
    "Jabari Walker",
    "Joel Embiid",
    "Johni Broome",
    "Justin Edwards",
    "Kelly Oubre Jr.",
    "Kyle Lowry",
    "MarJon Beauchamp",
    "Paul George",
    "Quentin Grimes",
    "Trendon Watford",
    "Tyrese Martin",
    "Tyrese Maxey",
    "VJ Edgecombe",
)

CANDIDATE_TYPES = (
    "current_sixers_player",
    "unrestricted_free_agent",
    "restricted_free_agent",
    "likely_free_agent",
    "minimum_candidate",
    "mle_candidate",
    "realistic_trade_target",
    "expensive_trade_target",
    "rookie_scale_trade_target",
    "star_unrealistic",
    "unavailable_core_player",
    "manual_watchlist",
    "missing_contract_status",
)

FREE_AGENT_TYPES = frozenset(
    {
        "unrestricted_free_agent",
        "restricted_free_agent",
        "likely_free_agent",
        "minimum_candidate",
        "mle_candidate",
    }
)
TRADE_TYPES = frozenset(
    {
        "realistic_trade_target",
        "expensive_trade_target",
        "rookie_scale_trade_target",
    }
)
REALISTIC_TYPES = FREE_AGENT_TYPES | TRADE_TYPES
WATCHLIST_TYPES = frozenset(
    {"star_unrealistic", "unavailable_core_player", "missing_contract_status"}
)

# Salary buckets in millions (cap hit).
MLE_MAX_M = 14.0
REALISTIC_TRADE_MAX_M = 25.0
EXPENSIVE_TRADE_MAX_M = 40.0
STAR_QUALITY_PCTL = 0.93
UNAVAILABLE_CORE_QUALITY_PCTL = 0.88

# Baseline acquisition feasibility (0-100) by candidate_type before adjustment.
FEASIBILITY_BASELINE = {
    "unrestricted_free_agent": 85.0,
    "minimum_candidate": 88.0,
    "mle_candidate": 78.0,
    "restricted_free_agent": 60.0,
    "likely_free_agent": 68.0,
    "rookie_scale_trade_target": 60.0,
    "realistic_trade_target": 58.0,
    "manual_watchlist": 55.0,
    "expensive_trade_target": 38.0,
    "missing_contract_status": 25.0,
    "unavailable_core_player": 18.0,
    "star_unrealistic": 10.0,
}

# candidate_types whose feasibility drops as the player matters more to his team.
IMPORTANCE_SENSITIVE = frozenset(TRADE_TYPES | {"unavailable_core_player"})

UNIVERSE_COLUMNS = (
    "player_id",
    "player_name",
    "current_team",
    "season",
    "position",
    "age",
    "minutes",
    "usage_rate",
    "quality_percentile",
    "cap_hit_millions",
    "base_salary_millions",
    "contract_aav_millions",
    "salary_millions",
    "contract_status",
    "free_agent_year",
    "option_status",
    "extension_status",
    "years_remaining",
    "draft_year",
    "salary_source",
    "candidate_type",
    "candidate_type_reason",
    "acquisition_feasibility",
    "feasibility_tier",
    "acquisition_reason",
    "on_acquisition_board",
    "realistic_board",
    "free_agent_board",
    "trade_board",
    "watchlist_board",
    "manual_override",
    "data_mode",
    "missing_data_flags",
)


@dataclass(frozen=True)
class CandidateUniverseResult:
    """Summary of a completed candidate-universe build."""

    universe_rows: int
    roster_rows: int
    type_counts: dict[str, int]
    feasibility_tier_counts: dict[str, int]
    universe_path: Path
    roster_path: Path
    summary_path: Path


def build_candidate_universe(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    contracts_path: str | Path = CONTRACTS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    candidates_path: str | Path = CANDIDATES_PATH,
    universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    roster_path: str | Path = CURRENT_ROSTER_REFERENCE_PATH,
    summary_path: str | Path = CANDIDATE_UNIVERSE_SUMMARY_PATH,
    season: str | None = None,
    team: str = "PHI",
) -> CandidateUniverseResult:
    """Classify every player, split out current Sixers, and write the tables."""
    universe = classify_candidate_universe(
        player_seasons=pd.read_parquet(player_seasons_path),
        contracts=_optional(contracts_path),
        player_bio=_optional(player_bio_path),
        manual_candidates=_optional_csv(candidates_path),
        season=season,
    )

    roster = universe[universe["candidate_type"] == "current_sixers_player"].copy()
    acquisition = universe[universe["candidate_type"] != "current_sixers_player"].copy()

    universe_path = Path(universe_path)
    roster_path = Path(roster_path)
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    acquisition.loc[:, list(UNIVERSE_COLUMNS)].to_parquet(universe_path, index=False)
    roster.loc[:, list(UNIVERSE_COLUMNS)].to_parquet(roster_path, index=False)

    type_counts = {
        str(k): int(v) for k, v in universe["candidate_type"].value_counts().items()
    }
    tier_counts = {
        str(k): int(v)
        for k, v in acquisition["feasibility_tier"].value_counts().items()
    }
    summary_path = Path(summary_path)
    summary_path.write_text(
        _summary_markdown(acquisition, roster, team), encoding="utf-8"
    )
    return CandidateUniverseResult(
        universe_rows=len(acquisition),
        roster_rows=len(roster),
        type_counts=type_counts,
        feasibility_tier_counts=tier_counts,
        universe_path=universe_path,
        roster_path=roster_path,
        summary_path=summary_path,
    )


def classify_candidate_universe(
    *,
    player_seasons: pd.DataFrame,
    contracts: pd.DataFrame | None = None,
    player_bio: pd.DataFrame | None = None,
    manual_candidates: pd.DataFrame | None = None,
    season: str | None = None,
) -> pd.DataFrame:
    """Return one classified row per player for the chosen season."""
    pool = _season_pool(player_seasons, season=season)
    if pool.empty:
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)

    pool = _merge_contracts(pool, contracts)
    pool = _merge_bio(pool, player_bio)
    pool = _attach_quality_percentile(pool)
    manual = _manual_overrides(manual_candidates)

    records = []
    for row in pool.to_dict(orient="records"):
        override = manual.get(_player_key(row))
        candidate_type, reason = classify_candidate_type(row, manual_override=override)
        feasibility, tier, acq_reason = acquisition_feasibility(row, candidate_type)
        records.append(
            _universe_record(
                row, candidate_type, reason, override, feasibility, tier, acq_reason
            )
        )

    frame = pd.DataFrame(records)
    return (
        frame.loc[:, list(UNIVERSE_COLUMNS)]
        .sort_values(["quality_percentile", "minutes"], ascending=False)
        .reset_index(drop=True)
    )


def classify_candidate_type(
    row: dict,
    *,
    manual_override: str | None = None,
) -> tuple[str, str]:
    """Assign exactly one candidate_type with a short human reason."""
    name = str(row.get("player_name") or "").strip()
    if name in PHI_ROSTER_2025_26:
        return "current_sixers_player", "On the 76ers 2025-26 roster."

    if manual_override == "manual_watchlist":
        return "manual_watchlist", "Explicitly tracked on the manual watchlist."
    if (
        manual_override in CANDIDATE_TYPES
        and manual_override != "current_sixers_player"
    ):
        return manual_override, "Manual candidate_type override."

    cap_hit = _cap_hit(row)
    status = str(row.get("contract_status") or "").lower()
    if cap_hit is None and status in ("", "unknown"):
        return (
            "missing_contract_status",
            "No contract row matched - cannot price an acquisition.",
        )

    if status == "unrestricted_free_agent":
        return "unrestricted_free_agent", "Listed as an unrestricted free agent."
    if status == "restricted_free_agent":
        return "restricted_free_agent", "Listed as a restricted free agent."

    quality = _quality(row)
    if status == "max_or_near_max" or (
        quality is not None and quality >= STAR_QUALITY_PCTL
    ):
        salary_text = f"${cap_hit:.1f}M cap hit" if cap_hit is not None else "max-tier"
        return "star_unrealistic", f"Max/near-max star ({salary_text}) - unrealistic."
    if (
        status == "signed_long_term"
        and quality is not None
        and quality >= UNAVAILABLE_CORE_QUALITY_PCTL
    ):
        return (
            "unavailable_core_player",
            "Core piece on a multi-year deal - not realistically available.",
        )

    if status == "minimum_contract":
        return "minimum_candidate", "On a minimum-range deal - cheap target."
    if status == "rookie_scale":
        return (
            "rookie_scale_trade_target",
            "On a rookie-scale deal - trade cost differs.",
        )
    if status == "signed_short_term":
        if cap_hit is not None and cap_hit <= MLE_MAX_M:
            return "mle_candidate", "Expiring mid-range deal - MLE-range target."
        return "likely_free_agent", "Expiring deal - likely reaches free agency."

    # signed_long_term / unknown-with-salary -> trade targets by cap hit.
    if cap_hit is None:
        return (
            "missing_contract_status",
            "Contract status known but no cap figure - cannot price.",
        )
    if cap_hit <= REALISTIC_TRADE_MAX_M:
        return "realistic_trade_target", f"Under contract at ${cap_hit:.1f}M - movable."
    if cap_hit <= EXPENSIVE_TRADE_MAX_M:
        return (
            "expensive_trade_target",
            f"Under contract at ${cap_hit:.1f}M - expensive but tradeable.",
        )
    return "star_unrealistic", f"Near-max ${cap_hit:.1f}M deal - unrealistic."


def acquisition_feasibility(row: dict, candidate_type: str) -> tuple[float, str, str]:
    """Return (0-100 feasibility, tier, reason) for acquiring this player."""
    if candidate_type == "missing_contract_status":
        return 25.0, "Unknown", "No contract data - feasibility cannot be assessed."

    base = FEASIBILITY_BASELINE.get(candidate_type, 45.0)
    quality = _quality(row) or 0.5
    reasons = [_FEASIBILITY_BLURB.get(candidate_type, "Feasibility unclear")]

    if candidate_type in IMPORTANCE_SENSITIVE:
        # A more important player is harder to pry loose from his team.
        penalty = 30.0 * max(0.0, quality - 0.5)
        base -= penalty
        if quality >= 0.8:
            reasons.append("a key piece for his current team, so harder to acquire")
        elif quality >= 0.6:
            reasons.append("a useful rotation player his team may want to keep")

    cap_hit = _cap_hit(row)
    if candidate_type in TRADE_TYPES and cap_hit is not None and cap_hit >= 25:
        base -= 6.0
        reasons.append("a large salary that complicates trade matching")

    score = round(max(0.0, min(100.0, base)), 1)
    tier = _feasibility_tier(score)
    return score, tier, "; ".join(reasons) + "."


def board_membership(candidate_type: str) -> dict[str, bool]:
    """Return the board flags implied by a candidate_type."""
    return {
        "realistic_board": candidate_type in REALISTIC_TYPES,
        "free_agent_board": candidate_type in FREE_AGENT_TYPES,
        "trade_board": candidate_type in TRADE_TYPES,
        "watchlist_board": candidate_type in WATCHLIST_TYPES,
        "on_acquisition_board": candidate_type
        in (REALISTIC_TYPES | WATCHLIST_TYPES | {"manual_watchlist"}),
    }


def _feasibility_tier(score: float) -> str:
    if score >= 80:
        return "Easy"
    if score >= 60:
        return "Possible"
    if score >= 40:
        return "Difficult"
    if score >= 25:
        return "Very Difficult"
    return "Unrealistic"


_FEASIBILITY_BLURB = {
    "unrestricted_free_agent": "An unrestricted free agent - signable outright",
    "restricted_free_agent": "A restricted free agent - his team can match an offer",
    "minimum_candidate": "Signable for the veteran minimum",
    "mle_candidate": "In MLE range as a free-agent target",
    "likely_free_agent": "On an expiring deal, likely available in free agency",
    "rookie_scale_trade_target": "On a cheap rookie-scale deal; needs a trade",
    "realistic_trade_target": "Movable in a realistic trade package",
    "expensive_trade_target": "Tradeable but expensive; needs salary matching",
    "manual_watchlist": "Tracked manually for situational interest",
    "unavailable_core_player": "A core piece; realistically not available",
    "star_unrealistic": "A max-tier star; not realistically acquirable",
}


def _universe_record(
    row: dict,
    candidate_type: str,
    reason: str,
    override: str | None,
    feasibility: float,
    tier: str,
    acq_reason: str,
) -> dict:
    boards = board_membership(candidate_type)
    cap_hit = _cap_hit(row)
    return {
        "player_id": row.get("player_id"),
        "player_name": str(row.get("player_name") or ""),
        "current_team": str(row.get("team_abbr") or row.get("current_team") or ""),
        "season": str(row.get("season") or ""),
        "position": str(row.get("position") or "")
        if pd.notna(row.get("position"))
        else "",
        "age": _num(row.get("age")),
        "minutes": _num(row.get("minutes")),
        "usage_rate": _num(row.get("usage_rate")),
        "quality_percentile": _num(row.get("quality_percentile")),
        "cap_hit_millions": cap_hit,
        "base_salary_millions": _num(row.get("base_salary_millions")),
        "contract_aav_millions": _num(row.get("contract_aav_millions")),
        "salary_millions": cap_hit,
        "contract_status": str(row.get("contract_status") or ""),
        "free_agent_year": _num(row.get("free_agent_year")),
        "option_status": str(row.get("option_status") or ""),
        "extension_status": str(row.get("extension_status") or ""),
        "years_remaining": _num(row.get("years_remaining")),
        "draft_year": _num(row.get("draft_year")),
        "salary_source": str(row.get("salary_source") or ""),
        "candidate_type": candidate_type,
        "candidate_type_reason": reason,
        "acquisition_feasibility": feasibility,
        "feasibility_tier": tier,
        "acquisition_reason": acq_reason,
        **boards,
        "manual_override": override or "",
        "data_mode": "derived",
        "missing_data_flags": _missing_flags(row, cap_hit),
    }


def _season_pool(player_seasons: pd.DataFrame, *, season: str | None) -> pd.DataFrame:
    frame = player_seasons.copy()
    if "season" not in frame.columns:
        return frame
    target = season or sorted(frame["season"].astype(str).unique())[-1]
    pool = frame[frame["season"].astype(str).eq(str(target))].copy()
    if "player_id" in pool.columns:
        pool = pool.drop_duplicates(subset=["player_id"], keep="first")
    pool["minutes"] = pd.to_numeric(pool.get("minutes"), errors="coerce").fillna(0.0)
    return pool.reset_index(drop=True)


def _merge_contracts(
    pool: pd.DataFrame, contracts: pd.DataFrame | None
) -> pd.DataFrame:
    cols = [
        "cap_hit_millions",
        "base_salary_millions",
        "contract_aav_millions",
        "contract_status",
        "free_agent_year",
        "option_status",
        "extension_status",
        "years_remaining",
        "salary_source",
    ]
    if contracts is None or contracts.empty:
        for col in cols:
            pool[col] = np.nan if col != "contract_status" else ""
        return pool
    keep = ["player_id", *[c for c in cols if c in contracts.columns]]
    merged = pool.merge(
        contracts.loc[:, keep].drop_duplicates("player_id"), on="player_id", how="left"
    )
    return merged


def _merge_bio(pool: pd.DataFrame, bio: pd.DataFrame | None) -> pd.DataFrame:
    if bio is None or bio.empty:
        if "draft_year" not in pool.columns:
            pool["draft_year"] = np.nan
        return pool
    cols = [c for c in ("player_id", "draft_year") if c in bio.columns]
    has_bio_position = "position" in bio.columns
    if has_bio_position:
        cols.append("position")
    rename = {"position": "bio_position"} if has_bio_position else {}
    merged = pool.merge(
        bio.loc[:, cols].drop_duplicates("player_id").rename(columns=rename),
        on="player_id",
        how="left",
    )
    if has_bio_position:
        season_pos = merged.get("position", pd.Series("", index=merged.index))
        season_pos = season_pos.fillna("").astype(str).str.strip()
        merged["position"] = season_pos.where(season_pos != "", merged["bio_position"])
        merged = merged.drop(columns=["bio_position"])
    return merged


def _attach_quality_percentile(pool: pd.DataFrame) -> pd.DataFrame:
    minutes = pd.to_numeric(pool.get("minutes"), errors="coerce").fillna(0.0)
    pts = pd.to_numeric(pool.get("pts"), errors="coerce").fillna(0.0)
    usage = pd.to_numeric(pool.get("usage_rate"), errors="coerce").fillna(0.0)
    ts = pd.to_numeric(pool.get("true_shooting"), errors="coerce")

    def pct(series: pd.Series) -> pd.Series:
        return series.rank(pct=True)

    ts_filled = ts.fillna(ts.median() if ts.notna().any() else 0.0)
    blend = (
        0.40 * pct(minutes)
        + 0.25 * pct(pts)
        + 0.20 * pct(usage)
        + 0.15 * pct(ts_filled)
    )
    pool["quality_percentile"] = blend.rank(pct=True).round(4)
    return pool


def _manual_overrides(manual: pd.DataFrame | None) -> dict:
    if manual is None or manual.empty:
        return {}
    overrides: dict = {}
    type_col = next(
        (
            c
            for c in ("candidate_type_override", "candidate_type")
            if c in manual.columns
        ),
        None,
    )
    if type_col is None:
        return overrides
    for record in manual.to_dict(orient="records"):
        value = str(record.get(type_col) or "").strip()
        if not value or value == "trade_target":
            continue
        overrides[_player_key(record)] = value
    return overrides


def _player_key(row: dict) -> tuple:
    pid = row.get("player_id")
    if pd.notna(pid):
        try:
            return ("id", int(pid))
        except (TypeError, ValueError):
            return ("id", str(pid))
    return ("name", str(row.get("player_name") or "").strip().lower())


def _missing_flags(row: dict, cap_hit: float | None) -> str:
    flags = []
    if cap_hit is None:
        flags.append("cap hit missing")
    if not str(row.get("position") or "").strip():
        flags.append("position missing")
    if _num(row.get("draft_year")) is None:
        flags.append("draft year missing")
    minutes = _num(row.get("minutes"))
    if minutes is not None and minutes < 500:
        flags.append("small minutes sample")
    return "; ".join(flags) if flags else "none"


def _cap_hit(row: dict) -> float | None:
    for key in ("cap_hit_millions", "salary_millions", "salary"):
        value = _num(row.get(key))
        if value is not None:
            return value / 1_000_000 if value > 1000 else value
    return None


def _quality(row: dict) -> float | None:
    return _num(row.get("quality_percentile"))


def _num(value) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else float(numeric)


def _summary_markdown(
    acquisition: pd.DataFrame, roster: pd.DataFrame, team: str
) -> str:
    built = datetime.now(UTC).date().isoformat()
    lines = [
        f"# Candidate Universe Summary ({team})",
        "",
        f"_Built {built} from real player seasons + contracts + bio (derived)._",
        "",
        f"- Acquisition candidates: **{len(acquisition)}**",
        f"- Current {team} roster (off board): **{len(roster)}**",
        "",
        "## candidate_type counts",
    ]
    for k, v in acquisition["candidate_type"].value_counts().items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Acquisition feasibility tiers"]
    for k, v in acquisition["feasibility_tier"].value_counts().items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Most feasible realistic candidates"]
    realistic = acquisition[acquisition["realistic_board"]]
    top = realistic.sort_values("acquisition_feasibility", ascending=False).head(15)
    for _, r in top.iterrows():
        lines.append(
            f"- {r['player_name']} ({r['current_team']}) - {r['candidate_type']}, "
            f"feasibility {r['acquisition_feasibility']:.0f} ({r['feasibility_tier']})"
        )
    return "\n".join(lines) + "\n"


def _optional(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None


def _optional_csv(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_csv(p) if p.exists() else None
