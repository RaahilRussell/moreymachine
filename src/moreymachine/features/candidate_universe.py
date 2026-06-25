"""Assign every real player exactly one acquisition candidate type.

The previous board lumped 261 players into a single ``trade_target`` bucket and
never separated current Sixers, untouchable stars, or genuine free-agency
targets from realistic trade pieces. This module rebuilds the *candidate
universe*: it joins the latest real player season pool with Basketball-Reference
contracts and nba_api bio, then assigns each player exactly one
``candidate_type`` from a closed taxonomy. Current Sixers are pulled out into a
separate roster-reference table and excluded from the acquisition board.

The classification is deterministic and transparent (first matching rule wins)
so every label can be explained from real salary, contract status, draft year,
and a percentile-scaled quality proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    CANDIDATES_PATH,
    CONTRACTS_PATH,
    CURRENT_ROSTER_REFERENCE_PATH,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
)

# Philadelphia 76ers 2025-26 roster - excluded from the acquisition board and
# surfaced in the Current Roster reference table instead. Matched on name.
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

# The closed candidate-type taxonomy. Every classified player gets exactly one.
CANDIDATE_TYPES = (
    "free_agent",
    "likely_free_agent",
    "minimum_candidate",
    "mle_candidate",
    "realistic_trade_target",
    "expensive_trade_target",
    "rookie_scale_trade_target",
    "star_unrealistic",
    "unavailable_core_player",
    "current_sixers_player",
    "manual_watchlist",
    "missing_contract_status",
)

# Board membership derived from candidate_type. A player can sit on the umbrella
# realistic board and on exactly one of the free-agent / trade sub-boards.
FREE_AGENT_TYPES = frozenset(
    {"free_agent", "likely_free_agent", "minimum_candidate", "mle_candidate"}
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

# Salary thresholds in millions, anchored to real CBA mechanisms.
ROOKIE_SCALE_MAX_M = 6.0
MIN_SALARY_MAX_M = 2.6
MLE_MAX_M = 14.0
REALISTIC_TRADE_MAX_M = 25.0
EXPENSIVE_TRADE_MAX_M = 35.0
STAR_SALARY_M = 35.0
STAR_QUALITY_PCTL = 0.93
UNAVAILABLE_CORE_QUALITY_PCTL = 0.90
ROOKIE_DRAFT_YEAR = 2023

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
    "salary_millions",
    "salary_source",
    "contract_status",
    "years_remaining",
    "draft_year",
    "candidate_type",
    "candidate_type_reason",
    "on_acquisition_board",
    "realistic_board",
    "free_agent_board",
    "trade_board",
    "watchlist_board",
    "manual_override",
    "missing_data_flags",
)


@dataclass(frozen=True)
class CandidateUniverseResult:
    """Summary of a completed candidate-universe build."""

    universe_rows: int
    roster_rows: int
    type_counts: dict[str, int]
    universe_path: Path
    roster_path: Path


def build_candidate_universe(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    contracts_path: str | Path = CONTRACTS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    candidates_path: str | Path = CANDIDATES_PATH,
    universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    roster_path: str | Path = CURRENT_ROSTER_REFERENCE_PATH,
    season: str | None = None,
    team: str = "PHI",
) -> CandidateUniverseResult:
    """Classify every player, split out current Sixers, and write both tables."""
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
    acquisition.loc[:, list(UNIVERSE_COLUMNS)].to_parquet(universe_path, index=False)
    roster.loc[:, list(UNIVERSE_COLUMNS)].to_parquet(roster_path, index=False)

    type_counts = universe["candidate_type"].value_counts().sort_index().to_dict()
    return CandidateUniverseResult(
        universe_rows=len(acquisition),
        roster_rows=len(roster),
        type_counts={str(k): int(v) for k, v in type_counts.items()},
        universe_path=universe_path,
        roster_path=roster_path,
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
        records.append(_universe_record(row, candidate_type, reason, override))

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
    """Assign exactly one candidate_type with a short human reason.

    First matching rule wins. Order encodes priority: roster status and explicit
    manual labels beat derived salary buckets; missing contracts and stars are
    pulled off the realistic board before the trade/free-agent buckets apply.
    """
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

    salary = _salary_millions(row)
    if salary is None:
        return (
            "missing_contract_status",
            "No contract row matched - cannot price an acquisition.",
        )

    quality = _quality_percentile(row)
    if salary >= STAR_SALARY_M:
        return (
            "star_unrealistic",
            f"Max-tier salary (${salary:.1f}M) - not a realistic acquisition.",
        )
    if quality is not None and quality >= STAR_QUALITY_PCTL:
        top_pct = (1 - STAR_QUALITY_PCTL) * 100
        return (
            "star_unrealistic",
            f"Top-{top_pct:.0f}% quality star - effectively unavailable.",
        )
    if (
        quality is not None
        and quality >= UNAVAILABLE_CORE_QUALITY_PCTL
        and _years_remaining(row) >= 2
    ):
        return (
            "unavailable_core_player",
            "High-quality young core piece on a multi-year deal - not for trade.",
        )

    status = str(row.get("contract_status") or "").lower()
    if status == "expiring":
        if salary <= MIN_SALARY_MAX_M:
            return (
                "minimum_candidate",
                f"Expiring minimum-range deal (${salary:.1f}M) - cheap FA target.",
            )
        if salary <= MLE_MAX_M:
            return (
                "mle_candidate",
                f"Expiring mid-range deal (${salary:.1f}M) - MLE-range FA target.",
            )
        return (
            "likely_free_agent",
            f"Expiring ${salary:.1f}M deal - likely hits free agency.",
        )

    if (
        _draft_year(row) is not None
        and _draft_year(row) >= ROOKIE_DRAFT_YEAR
        and (salary <= ROOKIE_SCALE_MAX_M)
    ):
        return (
            "rookie_scale_trade_target",
            f"Recent draftee on a ${salary:.1f}M rookie-scale deal.",
        )
    if salary <= REALISTIC_TRADE_MAX_M:
        return (
            "realistic_trade_target",
            f"Under contract at ${salary:.1f}M - movable in a realistic trade.",
        )
    if salary <= EXPENSIVE_TRADE_MAX_M:
        return (
            "expensive_trade_target",
            f"Under contract at ${salary:.1f}M - expensive but tradeable.",
        )
    return (
        "star_unrealistic",
        f"Large ${salary:.1f}M deal near max territory - unrealistic.",
    )


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


def _universe_record(
    row: dict,
    candidate_type: str,
    reason: str,
    override: str | None,
) -> dict:
    boards = board_membership(candidate_type)
    return {
        "player_id": row.get("player_id"),
        "player_name": str(row.get("player_name") or ""),
        "current_team": str(row.get("team_abbr") or row.get("team") or ""),
        "season": str(row.get("season") or ""),
        "position": str(row.get("position") or "")
        if pd.notna(row.get("position"))
        else "",
        "age": _num(row.get("age")),
        "minutes": _num(row.get("minutes")),
        "usage_rate": _num(row.get("usage_rate")),
        "quality_percentile": _num(row.get("quality_percentile")),
        "salary_millions": _salary_millions(row),
        "salary_source": str(row.get("salary_source") or row.get("source") or ""),
        "contract_status": str(row.get("contract_status") or ""),
        "years_remaining": _num(row.get("years_remaining")),
        "draft_year": _num(row.get("draft_year")),
        "candidate_type": candidate_type,
        "candidate_type_reason": reason,
        **boards,
        "manual_override": override or "",
        "missing_data_flags": _missing_flags(row),
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
    if contracts is None or contracts.empty:
        for col in ("salary", "contract_status", "years_remaining", "salary_source"):
            pool[col] = np.nan if col != "contract_status" else ""
        return pool
    c = contracts.copy()
    c = c.rename(columns={"source": "salary_source"})
    keep = [
        col
        for col in (
            "player_id",
            "salary",
            "contract_status",
            "years_remaining",
            "salary_source",
        )
        if col in c.columns
    ]
    c = c.loc[:, keep].drop_duplicates("player_id")
    return pool.merge(c, on="player_id", how="left")


def _merge_bio(pool: pd.DataFrame, bio: pd.DataFrame | None) -> pd.DataFrame:
    if bio is None or bio.empty:
        if "draft_year" not in pool.columns:
            pool["draft_year"] = np.nan
        return pool
    cols = [c for c in ("player_id", "draft_year") if c in bio.columns]
    has_bio_position = "position" in bio.columns
    if has_bio_position:
        cols.append("position")
    merged = pool.merge(
        bio.loc[:, cols]
        .drop_duplicates("player_id")
        .rename(columns={"position": "bio_position"} if has_bio_position else {}),
        on="player_id",
        how="left",
    )
    if has_bio_position:
        # player_seasons.position is empty for most rows; prefer the real bio
        # position and fall back to whatever the season pool carried.
        season_pos = merged.get("position", pd.Series("", index=merged.index))
        season_pos = season_pos.fillna("").astype(str).str.strip()
        merged["position"] = season_pos.where(season_pos != "", merged["bio_position"])
        merged = merged.drop(columns=["bio_position"])
    return merged


def _attach_quality_percentile(pool: pd.DataFrame) -> pd.DataFrame:
    """Percentile-scale a transparent quality proxy within the season pool.

    Quality = blend of rotation load (minutes), scoring volume (pts), shot
    creation (usage), and efficiency (true shooting). Percentile-ranking the
    blend keeps it bounded and avoids any single raw stat saturating.
    """
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
    type_col = None
    for col in ("candidate_type_override", "candidate_type"):
        if col in manual.columns:
            type_col = col
            break
    if type_col is None:
        return overrides
    for record in manual.to_dict(orient="records"):
        value = str(record.get(type_col) or "").strip()
        if not value or value == "trade_target":
            # Generic 'trade_target' is the old pool label, not a manual intent;
            # let the salary-based classifier decide instead.
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


def _missing_flags(row: dict) -> str:
    flags = []
    if _salary_millions(row) is None:
        flags.append("salary missing")
    if not (str(row.get("position") or "").strip()):
        flags.append("position missing")
    if _draft_year(row) is None:
        flags.append("draft year missing")
    minutes = _num(row.get("minutes"))
    if minutes is not None and minutes < 500:
        flags.append("small minutes sample")
    return "; ".join(flags) if flags else "none"


def _salary_millions(row: dict) -> float | None:
    for key in ("salary_millions", "salary", "expected_salary"):
        value = _num(row.get(key))
        if value is not None:
            return value / 1_000_000 if value > 1000 else value
    return None


def _quality_percentile(row: dict) -> float | None:
    return _num(row.get("quality_percentile"))


def _years_remaining(row: dict) -> float:
    value = _num(row.get("years_remaining"))
    return value if value is not None else 0.0


def _draft_year(row: dict) -> float | None:
    return _num(row.get("draft_year"))


def _num(value) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _optional(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None


def _optional_csv(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_csv(p) if p.exists() else None
