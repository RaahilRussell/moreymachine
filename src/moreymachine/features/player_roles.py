"""Role-dimension and archetype engine built from real bio + tracking data.

The previous archetype labels were assigned from box-score stats alone, with no
position or tracking input, which produced basketball-wrong labels (e.g. 6'7"
wings tagged "Rim Protector"). This module rebuilds roles from three real
tables - player season stats, player bio (position/height), and player tracking
(catch-and-shoot, pull-up, drives, passing, touches, rebounding chances, rim
defense) - and scales every role dimension to a *percentile within the season
pool* so no single raw stat saturates.

Outputs, per player, eleven role dimensions on 0-100 and one of fifteen
archetypes, plus a confidence and a missing-data flag. ``build_player_roles``
also writes ``data/reports/player_role_explanations.parquet``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from moreymachine.utils.paths import (
    PLAYER_BIO_PATH,
    PLAYER_ROLE_EXPLANATIONS_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
)

# Minutes below this make a season sample unreliable for role inference.
RELIABLE_MINUTES = 600.0
THIN_MINUTES = 250.0

ROLE_DIMENSIONS = (
    "creation_score",
    "spacing_score",
    "movement_shooting_score",
    "rim_pressure_score",
    "connector_score",
    "wing_defense_proxy",
    "rim_protection_proxy",
    "rebounding_score",
    "usage_dependency",
    "low_usage_fit",
    "sample_reliability",
)

ARCHETYPES = (
    "Primary Creator",
    "Secondary Creator",
    "Scoring Guard",
    "Movement Shooter",
    "Stationary Spacer",
    "3-and-D Wing",
    "Connector Wing",
    "Defensive Wing",
    "Stretch Big",
    "Rim Protector",
    "Rebounding Big",
    "Backup Center",
    "Developmental Prospect",
    "Fringe Rotation",
    "Unknown / Missing Data",
)

ROLE_OUTPUT_COLUMNS = (
    "player_id",
    "player_name",
    "team_abbr",
    "season",
    "position",
    "height_inches",
    "role_archetype",
    *ROLE_DIMENSIONS,
    "top_role_dimensions",
    "why_archetype",
    "role_confidence",
    "missing_role_data",
)


@dataclass(frozen=True)
class PlayerRolesResult:
    """Summary of a player roles build."""

    rows: int
    season: str
    output_path: Path


def build_player_roles(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    player_tracking_path: str | Path = PLAYER_TRACKING_PATH,
    output_path: str | Path = PLAYER_ROLE_EXPLANATIONS_PATH,
    season: str | None = None,
) -> PlayerRolesResult:
    """Compute role dimensions/archetypes for a season and save explanations."""
    roles = compute_player_roles(
        player_seasons=pd.read_parquet(player_seasons_path),
        player_bio=_optional(player_bio_path),
        player_tracking=_optional(player_tracking_path),
        season=season,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    roles.loc[:, list(ROLE_OUTPUT_COLUMNS)].to_parquet(output, index=False)
    season_label = str(roles["season"].iloc[0]) if not roles.empty else (season or "")
    return PlayerRolesResult(rows=len(roles), season=season_label, output_path=output)


def compute_player_roles(
    *,
    player_seasons: pd.DataFrame,
    player_bio: pd.DataFrame | None = None,
    player_tracking: pd.DataFrame | None = None,
    season: str | None = None,
) -> pd.DataFrame:
    """Return one role row per player for the chosen season."""
    pool = _season_pool(player_seasons, season=season)
    if pool.empty:
        return pd.DataFrame(columns=ROLE_OUTPUT_COLUMNS)

    pool = _merge_bio(pool, player_bio)
    pool = _merge_tracking(pool, player_tracking)

    eligible = pool["minutes"] >= THIN_MINUTES
    dims = _role_dimensions(pool, eligible_mask=eligible)
    pool = pd.concat([pool.reset_index(drop=True), dims.reset_index(drop=True)], axis=1)

    records = []
    for row in pool.to_dict(orient="records"):
        archetype, why, confidence, missing = _assign_archetype(row)
        top_dims = _top_dimensions(row)
        records.append(
            {
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "team_abbr": row.get("team_abbr", ""),
                "season": row.get("season", ""),
                "position": row.get("position") if pd.notna(row.get("position")) else "",
                "height_inches": row.get("height_inches"),
                "role_archetype": archetype,
                **{dim: round(float(row.get(dim, 50.0)), 1) for dim in ROLE_DIMENSIONS},
                "top_role_dimensions": ", ".join(top_dims),
                "why_archetype": why,
                "role_confidence": confidence,
                "missing_role_data": missing,
            }
        )
    return pd.DataFrame(records)


def _season_pool(player_seasons: pd.DataFrame, *, season: str | None) -> pd.DataFrame:
    frame = player_seasons.copy()
    if "season" not in frame.columns:
        return frame
    target = season or sorted(frame["season"].astype(str).unique())[-1]
    pool = frame[frame["season"].astype(str).eq(str(target))].copy()
    # One row per player (defensive against any duplicates).
    if "player_id" in pool.columns:
        pool = pool.drop_duplicates(subset=["player_id"], keep="first")
    pool["minutes"] = pd.to_numeric(pool.get("minutes"), errors="coerce").fillna(0.0)
    return pool.reset_index(drop=True)


def _merge_bio(pool: pd.DataFrame, bio: pd.DataFrame | None) -> pd.DataFrame:
    if bio is None or bio.empty:
        pool["position"] = pool.get("position", pd.NA)
        pool["height_inches"] = np.nan
        return pool
    cols = [c for c in ("player_id", "position", "height_inches", "weight",
                        "draft_year") if c in bio.columns]
    merged = pool.drop(columns=[c for c in ("position",) if c in pool.columns]).merge(
        bio.loc[:, cols].drop_duplicates("player_id"), on="player_id", how="left"
    )
    return merged


def _merge_tracking(pool: pd.DataFrame, tracking: pd.DataFrame | None) -> pd.DataFrame:
    if tracking is None or tracking.empty:
        return pool
    drop = {"player_name", "team_abbr", "source", "pulled_at", "missing_data_flags", "min"}
    cols = [c for c in tracking.columns if c == "player_id" or c not in pool.columns]
    cols = [c for c in cols if c not in drop or c == "player_id"]
    return pool.merge(
        tracking.loc[:, cols].drop_duplicates("player_id"), on="player_id", how="left"
    )


def _role_dimensions(pool: pd.DataFrame, *, eligible_mask: pd.Series) -> pd.DataFrame:
    """Build 0-100 role dimensions, percentile-scaled within the eligible pool."""
    g = lambda name: pd.to_numeric(pool.get(name), errors="coerce")  # noqa: E731
    minutes = g("minutes").clip(lower=1.0)
    per36 = lambda s: (s / minutes) * 36.0  # noqa: E731

    usage = g("usage_rate")
    three_pa_rate = g("three_pa_rate")
    three_p_pct = g("three_p_pct")
    three_pa = g("three_pa")
    ast_pct = g("assist_pct")
    tov_pct = g("turnover_pct")
    reb_pct = g("rebound_pct")
    stl36 = per36(g("stl"))
    blk36 = per36(g("blk"))
    height = g("height_inches")

    # Tracking (may be missing for some players).
    cs_fg3a = g("catch_shoot_fg3a")
    cs_fg3_pct = g("catch_shoot_fg3_pct")
    pull_up_fga = g("pull_up_fga")
    drives = g("drives")
    passes_made = g("passes_made")
    potential_ast = g("potential_ast")
    touches = g("touches")
    time_of_poss = g("time_of_poss")
    avg_sec_per_touch = g("avg_sec_per_touch")
    reb_chances = g("reb_chances")
    def_rim_fga = g("def_rim_fga")
    def_rim_fg_pct = g("def_rim_fg_pct")

    pct = lambda s: _percentile_score(s, eligible_mask)  # noqa: E731
    inv = lambda s: 100.0 - _percentile_score(s, eligible_mask)  # noqa: E731

    out = pd.DataFrame(index=pool.index)
    out["creation_score"] = _avg(
        pct(usage), pct(pull_up_fga), pct(drives), pct(time_of_poss), pct(potential_ast)
    )
    out["spacing_score"] = _avg(
        pct(three_pa), pct(three_pa_rate), _shooting_quality(three_p_pct, three_pa)
    )
    out["movement_shooting_score"] = _avg(
        pct(cs_fg3a), _shooting_quality(cs_fg3_pct, cs_fg3a)
    )
    out["rim_pressure_score"] = _avg(pct(drives), pct(g("drive_pts")))
    out["connector_score"] = _avg(
        pct(passes_made), pct(potential_ast), pct(ast_pct), inv(tov_pct)
    )
    out["wing_defense_proxy"] = _avg(
        pct(stl36), pct(blk36), _guard_wing_bonus(pool.get("position"))
    )
    out["rim_protection_proxy"] = _avg(
        pct(blk36), pct(def_rim_fga), inv(def_rim_fg_pct), _height_score(height)
    )
    out["rebounding_score"] = _avg(pct(reb_pct), pct(reb_chances))
    out["usage_dependency"] = _avg(
        pct(usage), pct(time_of_poss), pct(avg_sec_per_touch), pct(touches)
    )
    out["low_usage_fit"] = _avg(
        inv(usage), inv(time_of_poss), inv(tov_pct), pct(cs_fg3a)
    )
    out["sample_reliability"] = _sample_reliability(minutes, g("games"))
    return out.fillna(50.0)


def _assign_archetype(row: dict) -> tuple[str, str, str, str]:
    """Rule-based archetype from role dimensions + position/height."""
    minutes = float(row.get("minutes") or 0.0)
    position = str(row.get("position") or "").upper()
    height = row.get("height_inches")
    height = float(height) if pd.notna(height) else None
    missing = _role_missing(row, position=position, height=height)

    if minutes < THIN_MINUTES:
        label = "Developmental Prospect" if _is_young(row) else "Fringe Rotation"
        return (
            label,
            f"Only {minutes:.0f} regular-season minutes - below the {THIN_MINUTES:.0f} "
            "minute threshold for a reliable role read.",
            "low",
            missing,
        )
    if not position and height is None:
        return (
            "Unknown / Missing Data",
            "No position or height available and stats alone are not enough to label "
            "a basketball role.",
            "low",
            missing,
        )

    d = {dim: float(row.get(dim, 50.0)) for dim in ROLE_DIMENSIONS}
    is_big = _is_big(position, height)
    is_guard = position.startswith("G") or (height is not None and height <= 76)
    confidence = "high" if minutes >= RELIABLE_MINUTES and not missing.startswith(
        "position"
    ) else "medium"

    if is_big:
        label = _big_archetype(d)
    elif is_guard:
        label = _guard_archetype(d)
    else:  # forward / wing
        label = _wing_archetype(d)
    return label, _why(label, d), confidence, missing


def _big_archetype(d: dict) -> str:
    if d["rim_protection_proxy"] >= 65 and d["spacing_score"] < 55:
        return "Rim Protector"
    if d["spacing_score"] >= 60 or d["movement_shooting_score"] >= 60:
        return "Stretch Big"
    if d["rebounding_score"] >= 60 and d["rim_protection_proxy"] >= 50:
        return "Rebounding Big"
    if d["rim_protection_proxy"] >= 55:
        return "Rim Protector"
    return "Backup Center"


def _guard_archetype(d: dict) -> str:
    if d["creation_score"] >= 75 and d["usage_dependency"] >= 65:
        return "Primary Creator"
    if d["creation_score"] >= 58:
        return "Secondary Creator"
    if d["movement_shooting_score"] >= 62 and d["usage_dependency"] < 55:
        return "Movement Shooter"
    if d["usage_dependency"] >= 60:
        return "Scoring Guard"
    if d["spacing_score"] >= 58 and d["wing_defense_proxy"] >= 55:
        return "3-and-D Wing"
    if d["connector_score"] >= 60:
        return "Connector Wing"
    return "Scoring Guard"


def _wing_archetype(d: dict) -> str:
    if d["creation_score"] >= 70:
        return "Secondary Creator"
    if d["spacing_score"] >= 55 and d["wing_defense_proxy"] >= 55:
        return "3-and-D Wing"
    if d["wing_defense_proxy"] >= 65 and d["spacing_score"] < 50:
        return "Defensive Wing"
    if d["movement_shooting_score"] >= 60 or d["spacing_score"] >= 62:
        return "Movement Shooter" if d["movement_shooting_score"] >= d["spacing_score"] else "Stationary Spacer"
    if d["connector_score"] >= 60:
        return "Connector Wing"
    if d["spacing_score"] >= 52:
        return "Stationary Spacer"
    return "Defensive Wing"


def _why(label: str, d: dict) -> str:
    top = sorted(d.items(), key=lambda kv: kv[1], reverse=True)
    top = [k for k, v in top if k != "sample_reliability"][:3]
    pretty = ", ".join(t.replace("_", " ") for t in top)
    return f"Labeled {label}; strongest role signals: {pretty}."


def _top_dimensions(row: dict) -> list[str]:
    scored = [
        (dim, float(row.get(dim, 50.0)))
        for dim in ROLE_DIMENSIONS
        if dim != "sample_reliability"
    ]
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return [f"{dim} {value:.0f}" for dim, value in scored[:3]]


def _role_missing(row: dict, *, position: str, height: float | None) -> str:
    flags = []
    if not position:
        flags.append("position missing")
    if height is None:
        flags.append("height missing")
    if pd.isna(row.get("catch_shoot_fg3a")) and pd.isna(row.get("drives")):
        flags.append("tracking missing")
    return "; ".join(flags) if flags else "none"


def _is_big(position: str, height: float | None) -> bool:
    if position:
        return position.startswith("C") or position in {"F-C", "C-F"}
    return height is not None and height >= 82


def _is_young(row: dict) -> bool:
    age = pd.to_numeric(pd.Series([row.get("age")]), errors="coerce").iloc[0]
    draft = row.get("draft_year")
    if pd.notna(age):
        return float(age) <= 23
    if pd.notna(draft):
        return int(draft) >= 2022
    return False


def _shooting_quality(pct_made: pd.Series, volume: pd.Series) -> pd.Series:
    """Reward 3P% only when volume is real; thin-volume high % is discounted."""
    made = pd.to_numeric(pct_made, errors="coerce")
    vol = pd.to_numeric(volume, errors="coerce")
    quality = ((made - 0.30) / (0.42 - 0.30) * 100).clip(0, 100)
    vol_weight = (vol / 3.0).clip(0, 1)  # full weight at ~3 attempts
    return (quality * vol_weight + 50.0 * (1 - vol_weight)).where(made.notna(), np.nan)


def _guard_wing_bonus(position: pd.Series | None) -> pd.Series:
    if position is None:
        return pd.Series(np.nan)
    pos = position.astype(str).str.upper()
    return pd.Series(
        np.where(pos.str.startswith("G") | pos.str.startswith("F"), 60.0, 45.0),
        index=position.index,
    )


def _height_score(height: pd.Series) -> pd.Series:
    h = pd.to_numeric(height, errors="coerce")
    return ((h - 78) / (86 - 78) * 100).clip(0, 100)


def _sample_reliability(minutes: pd.Series, games: pd.Series) -> pd.Series:
    min_score = (minutes / 2000.0 * 100).clip(0, 100)
    gp = pd.to_numeric(games, errors="coerce")
    game_score = (gp / 70.0 * 100).clip(0, 100)
    return _avg(min_score, game_score)


def _percentile_score(series: pd.Series, eligible_mask: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    eligible = values.where(eligible_mask)
    ranks = eligible.rank(pct=True) * 100
    # Players outside the eligible pool are scored against the eligible distribution.
    if eligible.notna().sum() >= 5:
        thresholds = eligible.dropna()
        for idx in values.index[~eligible_mask.fillna(False)]:
            v = values.loc[idx]
            if pd.notna(v):
                ranks.loc[idx] = float((thresholds <= v).mean() * 100)
    return ranks


def _avg(*series: pd.Series) -> pd.Series:
    frame = pd.concat([pd.to_numeric(s, errors="coerce") for s in series], axis=1)
    return frame.mean(axis=1, skipna=True)


def _optional(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None
