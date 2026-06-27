"""Evidence-backed player skill profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.schemas.skills import SKILL_DIMENSIONS
from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    FEATURES_DATA_DIR,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    REPORTS_DATA_DIR,
)

PLAYER_SKILL_PROFILES_PATH = FEATURES_DATA_DIR / "player_skill_profiles.parquet"
PLAYER_SKILL_PROFILE_EXAMPLES_PATH = (
    REPORTS_DATA_DIR / "player_skill_profile_examples.md"
)

EXTRA_DIMENSIONS = ("foul_risk", "minutes_context", "age_curve_context")
ALL_DIMENSIONS = tuple(SKILL_DIMENSIONS) + EXTRA_DIMENSIONS


@dataclass(frozen=True)
class SkillProfileResult:
    """Summary from building skill profiles."""

    rows: int
    spacing_claims_allowed: int
    defense_claims_allowed: int
    rim_claims_allowed: int
    output_path: Path
    report_path: Path


def build_player_skill_profiles(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    output_path: str | Path = PLAYER_SKILL_PROFILES_PATH,
    report_path: str | Path = PLAYER_SKILL_PROFILE_EXAMPLES_PATH,
    season: str | None = None,
) -> SkillProfileResult:
    """Build one evidence-backed skill row per latest player."""
    target_team = str(team or "PHI").upper()
    context = context or {}
    seasons = pd.read_parquet(player_seasons_path)
    bio = _optional_parquet(player_bio_path)
    candidates = _optional_parquet(candidate_universe_path)
    players = _latest_player_rows(seasons, season=season)
    players = _merge_bio(players, bio)
    players = _merge_candidate_context(players, candidates)
    rows = [
        _profile_row(row, target_team=target_team, context_mode=str(context.get("context_mode") or "unknown"))
        for row in players.to_dict(orient="records")
    ]
    frame = pd.DataFrame(rows)
    frame = _add_percentiles(frame)
    frame["evidence"] = frame.apply(_evidence_json, axis=1)
    frame["claim_allowed"] = frame.apply(_claim_allowed_json, axis=1)
    frame["missing_data_flags"] = frame.apply(_aggregate_missing_flags, axis=1)
    frame["confidence"] = frame.apply(_overall_confidence, axis=1)

    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    report.write_text(_render_report(frame), encoding="utf-8")

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                player_seasons_path,
                player_bio_path,
                candidate_universe_path,
            ),
            upstream_artifacts=(
                player_seasons_path,
                player_bio_path,
                candidate_universe_path,
            ),
            known_limitations=(
                "Shot-type, matchup-tracking, fouls, and injury context are "
                "incomplete.",
                "Defense and movement shooting use conservative public-stat proxies.",
                "Claim-allowed booleans are guards for explanations, not scouting "
                "truth.",
            ),
        )

    return SkillProfileResult(
        rows=len(frame),
        spacing_claims_allowed=int(frame["spot_up_spacing_claim_allowed"].sum()),
        defense_claims_allowed=int(frame["wing_defense_proxy_claim_allowed"].sum()),
        rim_claims_allowed=int(frame["rim_protection_claim_allowed"].sum()),
        output_path=output,
        report_path=report,
    )


def _optional_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _latest_player_rows(frame: pd.DataFrame, *, season: str | None) -> pd.DataFrame:
    if season is None:
        season = sorted(frame["season"].astype(str).unique())[-1]
    latest = frame[frame["season"].astype(str) == str(season)].copy()
    latest = latest.sort_values(["minutes", "player_name"], ascending=[False, True])
    latest = latest.drop_duplicates("player_id", keep="first")
    return latest.reset_index(drop=True)


def _merge_bio(players: pd.DataFrame, bio: pd.DataFrame) -> pd.DataFrame:
    if bio.empty:
        players["height_inches"] = pd.NA
        players["weight"] = pd.NA
        return players
    cols = ["player_id", "position", "height_inches", "weight", "team_abbr"]
    available = [col for col in cols if col in bio.columns]
    merged = players.merge(
        bio[available].drop_duplicates("player_id"),
        on="player_id",
        how="left",
        suffixes=("", "_bio"),
    )
    if "position_bio" in merged.columns:
        merged["position"] = merged["position"].fillna(merged["position_bio"])
        merged = merged.drop(columns=["position_bio"])
    if "team_abbr_bio" in merged.columns:
        merged["team_abbr"] = merged["team_abbr"].fillna(merged["team_abbr_bio"])
        merged = merged.drop(columns=["team_abbr_bio"])
    return merged


def _merge_candidate_context(
    players: pd.DataFrame, candidates: pd.DataFrame
) -> pd.DataFrame:
    if candidates.empty:
        players["candidate_type"] = "not_in_candidate_universe"
        return players
    cols = ["player_id", "candidate_type", "candidate_status_freshness"]
    available = [col for col in cols if col in candidates.columns]
    merged = players.merge(
        candidates[available].drop_duplicates("player_id"),
        on="player_id",
        how="left",
    )
    merged["candidate_type"] = merged["candidate_type"].fillna(
        "not_in_candidate_universe"
    )
    if "candidate_status_freshness" not in merged.columns:
        merged["candidate_status_freshness"] = "not_applicable"
    merged["candidate_status_freshness"] = merged["candidate_status_freshness"].fillna(
        "not_applicable"
    )
    return merged


def _profile_row(
    row: dict[str, Any],
    *,
    target_team: str,
    context_mode: str,
) -> dict[str, Any]:
    details = _dimension_details(row)
    out: dict[str, Any] = {
        "target_team": target_team,
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "season": row.get("season"),
        "current_team": row.get("team_abbr"),
        "position": row.get("position"),
        "age": _float(row.get("age")),
        "minutes": _float(row.get("minutes")),
        "games": _float(row.get("games")),
        "candidate_type": row.get("candidate_type"),
        "candidate_status_freshness": row.get("candidate_status_freshness"),
        "source": "player_seasons + player_bio + candidate_universe",
        "source_url": "",
        "source_note": (
            "NBA.com public stats plus derived candidate context; "
            f"context_mode={context_mode}"
        ),
        "pulled_at": datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
    }
    for dimension in ALL_DIMENSIONS:
        detail = details[dimension]
        out[dimension] = detail["score"]
        out[f"{dimension}_confidence"] = detail["confidence"]
        out[f"{dimension}_claim_allowed"] = detail["claim_allowed"]
        out[f"{dimension}_evidence_stat_1"] = detail["evidence_stat_1"]
        out[f"{dimension}_evidence_stat_2"] = detail["evidence_stat_2"]
        out[f"{dimension}_evidence_stat_3"] = detail["evidence_stat_3"]
        out[f"{dimension}_missing_data_flags"] = (
            ";".join(detail["missing_data_flags"]) or "none"
        )
    return out


def _dimension_details(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    minutes = _float(row.get("minutes"))
    games = _float(row.get("games"))
    usage = _float(row.get("usage_rate"))
    ts = _float(row.get("true_shooting"))
    three_pa = _float(row.get("three_pa"))
    three_rate = _float(row.get("three_pa_rate"))
    three_pct = _float(row.get("three_p_pct"))
    assist = _float(row.get("assist_pct"))
    turnover = _float(row.get("turnover_pct"))
    rebound = _float(row.get("rebound_pct"))
    stl = _float(row.get("stl"))
    blk = _float(row.get("blk"))
    age = _float(row.get("age"))
    height = _float(row.get("height_inches"))
    position = str(row.get("position") or "")
    stocks_per_100 = ((stl + blk) / minutes * 100) if minutes else 0.0
    blocks_per_100 = (blk / minutes * 100) if minutes else 0.0
    steals_per_100 = (stl / minutes * 100) if minutes else 0.0
    is_big = "C" in position
    is_wing = "F" in position or "G-F" in position or "F-G" in position
    is_guard = "G" in position

    spacing_score = _shooting_score(three_pa, three_rate, three_pct, minutes)
    spacing_allowed = (
        minutes >= 700 and three_pa >= 150 and three_rate >= 0.30 and three_pct >= 0.33
    )
    movement_score = _score(
        0.45 * _scale(three_pa, 120, 450)
        + 0.35 * _scale(three_rate, 0.30, 0.60)
        + 0.20 * _scale(three_pct, 0.32, 0.40)
    )
    movement_allowed = (
        minutes >= 900 and three_pa >= 250 and three_rate >= 0.38 and three_pct >= 0.35
    )
    pull_up_score = _score(
        0.35 * _scale(usage, 0.18, 0.32)
        + 0.35 * _scale(three_pa, 150, 500)
        + 0.30 * _scale(three_pct, 0.32, 0.39)
    )
    creation_score = _score(
        0.50 * _scale(usage, 0.18, 0.34)
        + 0.35 * _scale(assist, 0.10, 0.32)
        + 0.15 * _scale(ts, 0.52, 0.62)
        - 0.20 * _scale(turnover, 13.0, 20.0)
    )
    secondary_score = _score(
        0.45 * _scale(assist, 0.10, 0.28)
        + 0.30 * _scale(usage, 0.14, 0.24)
        + 0.25 * _scale(ts, 0.52, 0.62)
        - 0.15 * _scale(turnover, 12.0, 18.0)
    )
    connector_score = _score(
        0.45 * _scale(assist, 0.08, 0.22)
        + 0.35 * (100 - _scale(turnover, 8.0, 18.0))
        + 0.20 * (100 - _scale(usage, 0.16, 0.30))
    )
    low_usage_score = _score(
        0.45 * (100 - _scale(usage, 0.14, 0.28))
        + 0.30 * _scale(ts, 0.52, 0.62)
        + 0.25 * (100 - _scale(turnover, 8.0, 18.0))
    )
    rebound_score = _score(_scale(rebound, 0.05, 0.18))
    rim_score = _score(
        0.45 * _scale(blocks_per_100, 1.0, 5.0)
        + 0.25 * _scale(rebound, 0.08, 0.18)
        + 0.20 * _scale(height, 78.0, 84.0)
        + (10 if is_big else 0)
    )
    defense_score = _score(
        0.35 * _scale(stocks_per_100, 2.0, 5.0)
        + 0.30 * _scale(height, 76.0, 82.0)
        + 0.20 * _scale(minutes, 700, 1800)
        + (15 if is_wing else 0)
    )
    poa_score = _score(
        0.40 * _scale(steals_per_100, 1.0, 4.0)
        + 0.25 * _scale(minutes, 700, 1800)
        + 0.20 * _scale(height, 74.0, 80.0)
        + (15 if is_guard or is_wing else 0)
    )
    switch_score = _score(
        0.40 * _scale(height, 76.0, 82.0)
        + 0.30 * _scale(stocks_per_100, 1.8, 4.5)
        + 0.20 * _scale(minutes, 700, 1800)
        + (10 if is_wing else 0)
    )
    sample_score = _score(
        0.55 * _scale(minutes, 500, 2200) + 0.45 * _scale(games, 25, 70)
    )
    ball_security_score = _score(100 - _scale(turnover, 8.0, 20.0))
    portability_score = _score(
        0.25 * spacing_score
        + 0.20 * max(defense_score, rim_score)
        + 0.20 * ball_security_score
        + 0.20 * low_usage_score
        + 0.15 * sample_score
    )
    role_stability = _score(0.65 * sample_score + 0.35 * _scale(minutes, 700, 2000))
    age_score = _score(100 - _scale(abs(age - 27), 0, 10))

    shot_missing = ["shot_type_data_missing"]
    tracking_missing = ["tracking_data_missing"]
    foul_missing = ["foul_data_missing"]

    return {
        "spot_up_spacing": _detail(
            spacing_score,
            spacing_allowed,
            _conf(minutes, three_pa),
            (
                f"3PA {three_pa:.0f}",
                f"3PA rate {three_rate:.3f}",
                f"3P% {three_pct:.3f}",
            ),
        ),
        "movement_shooting": _detail(
            movement_score,
            movement_allowed,
            "medium" if movement_allowed else "low",
            (
                f"3PA {three_pa:.0f}",
                f"3PA rate {three_rate:.3f}",
                f"3P% {three_pct:.3f}",
            ),
            [] if movement_allowed else shot_missing,
        ),
        "pull_up_shooting": _detail(
            pull_up_score,
            minutes >= 900 and usage >= 0.22 and three_pa >= 200 and three_pct >= 0.34,
            "low",
            (f"usage {usage:.3f}", f"3PA {three_pa:.0f}", f"3P% {three_pct:.3f}"),
            shot_missing,
        ),
        "shooting_gravity": _detail(
            _score(0.60 * spacing_score + 0.40 * _scale(three_pa, 150, 500)),
            spacing_allowed and three_pa >= 200,
            _conf(minutes, three_pa),
            (
                f"3PA {three_pa:.0f}",
                f"3PA rate {three_rate:.3f}",
                f"3P% {three_pct:.3f}",
            ),
        ),
        "fake_spacing_risk": _detail(
            _score(100 - spacing_score),
            minutes >= 500
            and (three_pa < 120 or three_rate < 0.25 or three_pct < 0.32),
            _conf(minutes, max(three_pa, 1)),
            (
                f"3PA {three_pa:.0f}",
                f"3PA rate {three_rate:.3f}",
                f"3P% {three_pct:.3f}",
            ),
        ),
        "primary_creation": _detail(
            creation_score,
            minutes >= 900 and usage >= 0.25 and assist >= 0.18,
            _conf(minutes, games),
            (f"usage {usage:.3f}", f"AST% {assist:.3f}", f"TOV% {turnover:.1f}"),
        ),
        "secondary_creation": _detail(
            secondary_score,
            minutes >= 700 and usage >= 0.16 and assist >= 0.13,
            _conf(minutes, games),
            (f"usage {usage:.3f}", f"AST% {assist:.3f}", f"TOV% {turnover:.1f}"),
        ),
        "connector_passing": _detail(
            connector_score,
            minutes >= 700 and assist >= 0.12 and turnover <= 12 and usage <= 0.22,
            _conf(minutes, games),
            (f"AST% {assist:.3f}", f"TOV% {turnover:.1f}", f"usage {usage:.3f}"),
        ),
        "low_usage_fit": _detail(
            low_usage_score,
            minutes >= 500 and usage <= 0.18 and turnover <= 12,
            _conf(minutes, games),
            (f"usage {usage:.3f}", f"TS {ts:.3f}", f"TOV% {turnover:.1f}"),
        ),
        "rim_pressure": _detail(
            _score(0.55 * _scale(ts, 0.52, 0.65) + 0.45 * _scale(usage, 0.18, 0.30)),
            False,
            "low",
            (f"usage {usage:.3f}", f"TS {ts:.3f}", "rim attempts not sourced"),
            tracking_missing,
        ),
        "transition_pressure": _detail(
            0,
            False,
            "low",
            ("transition possessions not sourced", "transition PPP not sourced", ""),
            tracking_missing,
        ),
        "ball_security": _detail(
            ball_security_score,
            minutes >= 500 and turnover <= 11,
            _conf(minutes, games),
            (f"TOV% {turnover:.1f}", f"usage {usage:.3f}", f"AST% {assist:.3f}"),
        ),
        "offensive_rebounding": _detail(
            rebound_score,
            minutes >= 700 and rebound >= 0.11 and is_big,
            _conf(minutes, games),
            (f"REB% {rebound:.3f}", f"position {position}", f"minutes {minutes:.0f}"),
        ),
        "defensive_rebounding": _detail(
            rebound_score,
            minutes >= 700 and rebound >= 0.10 and (is_big or is_wing),
            _conf(minutes, games),
            (f"REB% {rebound:.3f}", f"position {position}", f"minutes {minutes:.0f}"),
        ),
        "rim_protection": _detail(
            rim_score,
            minutes >= 700 and is_big and blocks_per_100 >= 2.0 and rim_score >= 60,
            _conf(minutes, games),
            (
                f"BLK/100 {blocks_per_100:.2f}",
                f"height {height:.0f}",
                f"REB% {rebound:.3f}",
            ),
        ),
        "vertical_spacing": _detail(
            0,
            False,
            "low",
            (
                "roll-man/dunk data not sourced",
                f"height {height:.0f}",
                f"position {position}",
            ),
            tracking_missing,
        ),
        "wing_defense_proxy": _detail(
            defense_score,
            minutes >= 700
            and is_wing
            and stocks_per_100 >= 2.2
            and height >= 76
            and defense_score >= 65,
            "medium",
            (
                f"stocks/100 {stocks_per_100:.2f}",
                f"height {height:.0f}",
                f"position {position}",
            ),
        ),
        "point_of_attack_defense_proxy": _detail(
            poa_score,
            minutes >= 700
            and (is_guard or is_wing)
            and steals_per_100 >= 1.2
            and poa_score >= 60,
            "medium",
            (
                f"STL/100 {steals_per_100:.2f}",
                f"height {height:.0f}",
                f"position {position}",
            ),
        ),
        "defensive_event_proxy": _detail(
            _score(_scale(stocks_per_100, 1.5, 5.0)),
            minutes >= 700 and stocks_per_100 >= 2.5,
            "medium",
            (
                f"stocks/100 {stocks_per_100:.2f}",
                f"steals {stl:.0f}",
                f"blocks {blk:.0f}",
            ),
        ),
        "switchability_proxy": _detail(
            switch_score,
            minutes >= 700 and is_wing and 76 <= height <= 82 and switch_score >= 60,
            "medium",
            (
                f"height {height:.0f}",
                f"position {position}",
                f"stocks/100 {stocks_per_100:.2f}",
            ),
        ),
        "playoff_portability_base": _detail(
            portability_score,
            minutes >= 700
            and sample_score >= 45
            and (spacing_allowed or defense_score >= 60 or rim_score >= 60),
            "medium",
            (
                f"spacing {spacing_score:.1f}",
                f"def/rim {max(defense_score, rim_score):.1f}",
                f"TOV score {ball_security_score:.1f}",
            ),
        ),
        "sample_reliability": _detail(
            sample_score,
            minutes >= 700 and games >= 35,
            _conf(minutes, games),
            (
                f"minutes {minutes:.0f}",
                f"games {games:.0f}",
                f"season {row.get('season')}",
            ),
        ),
        "role_stability": _detail(
            role_stability,
            role_stability >= 45,
            _conf(minutes, games),
            (f"minutes {minutes:.0f}", f"games {games:.0f}", f"usage {usage:.3f}"),
        ),
        "foul_risk": _detail(
            0,
            False,
            "low",
            ("personal fouls not sourced", "", ""),
            foul_missing,
        ),
        "minutes_context": _detail(
            _score(_scale(minutes, 500, 2200)),
            minutes >= 700,
            _conf(minutes, games),
            (
                f"minutes {minutes:.0f}",
                f"games {games:.0f}",
                f"team {row.get('team_abbr')}",
            ),
        ),
        "age_curve_context": _detail(
            age_score,
            age > 0,
            "medium" if age > 0 else "low",
            (f"age {age:.1f}", f"minutes {minutes:.0f}", f"position {position}"),
        ),
    }


def _detail(
    score: float,
    claim_allowed: bool,
    confidence: str,
    evidence_stats: tuple[str, str, str],
    missing_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "score": round(_score(score), 2),
        "claim_allowed": bool(claim_allowed),
        "confidence": confidence,
        "evidence_stat_1": evidence_stats[0],
        "evidence_stat_2": evidence_stats[1],
        "evidence_stat_3": evidence_stats[2],
        "missing_data_flags": missing_flags or [],
    }


def _shooting_score(
    three_pa: float, three_rate: float, three_pct: float, minutes: float
) -> float:
    if minutes <= 0:
        return 0.0
    return _score(
        0.45 * _scale(three_pa, 50, 400)
        + 0.35 * _scale(three_rate, 0.15, 0.55)
        + 0.20 * _scale(three_pct, 0.30, 0.40)
    )


def _scale(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.0
    return _score(((value - low) / (high - low)) * 100)


def _score(value: float) -> float:
    if pd.isna(value):
        return 0.0
    return float(max(0.0, min(100.0, value)))


def _float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _conf(minutes: float, sample: float) -> str:
    if minutes >= 1200 and sample >= 50:
        return "high"
    if minutes >= 500:
        return "medium"
    return "low"


def _add_percentiles(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for dimension in ALL_DIMENSIONS:
        out[f"{dimension}_percentile"] = (
            pd.to_numeric(out[dimension], errors="coerce")
            .rank(pct=True, method="average")
            .fillna(0)
            .mul(100)
            .round(2)
        )
    return out


def _evidence_json(row: pd.Series) -> str:
    payload = {}
    for dimension in ALL_DIMENSIONS:
        payload[dimension] = {
            "score": row[dimension],
            "percentile": row[f"{dimension}_percentile"],
            "evidence_stat_1": row[f"{dimension}_evidence_stat_1"],
            "evidence_stat_2": row[f"{dimension}_evidence_stat_2"],
            "evidence_stat_3": row[f"{dimension}_evidence_stat_3"],
            "confidence": row[f"{dimension}_confidence"],
            "claim_allowed": bool(row[f"{dimension}_claim_allowed"]),
            "missing_data_flags": _split_flags(row[f"{dimension}_missing_data_flags"]),
        }
    return json.dumps(payload, sort_keys=True)


def _claim_allowed_json(row: pd.Series) -> str:
    payload = {
        dimension: bool(row[f"{dimension}_claim_allowed"])
        for dimension in ALL_DIMENSIONS
    }
    return json.dumps(payload, sort_keys=True)


def _aggregate_missing_flags(row: pd.Series) -> str:
    flags: set[str] = set()
    for dimension in ALL_DIMENSIONS:
        flags.update(_split_flags(row[f"{dimension}_missing_data_flags"]))
    return ";".join(sorted(flags)) if flags else "none"


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or pd.isna(value):
        return []
    return [part for part in str(value).split(";") if part and part != "none"]


def _overall_confidence(row: pd.Series) -> str:
    high_value_claims = (
        row["spot_up_spacing_claim_allowed"],
        row["secondary_creation_claim_allowed"],
        row["rim_protection_claim_allowed"],
        row["wing_defense_proxy_claim_allowed"],
        row["sample_reliability_claim_allowed"],
    )
    if row["minutes"] >= 1200 and any(high_value_claims):
        return "high"
    if row["minutes"] >= 500:
        return "medium"
    return "low"


def _render_report(frame: pd.DataFrame) -> str:
    spacing = frame[frame["spot_up_spacing_claim_allowed"]].sort_values(
        "spot_up_spacing", ascending=False
    )
    rim = frame[frame["rim_protection_claim_allowed"]].sort_values(
        "rim_protection", ascending=False
    )
    defense = frame[frame["wing_defense_proxy_claim_allowed"]].sort_values(
        "wing_defense_proxy", ascending=False
    )
    lines = [
        "# Player Skill Profile Examples",
        "",
        "Every skill claim is backed by public-stat evidence and a claim-allowed flag.",
        "",
        "## Top Spacing Claims",
        "",
        _table(spacing, "spot_up_spacing"),
        "",
        "## Top Rim-Protection Claims",
        "",
        _table(rim, "rim_protection"),
        "",
        "## Top Wing-Defense Proxy Claims",
        "",
        _table(defense, "wing_defense_proxy"),
        "",
        "## Limits",
        "",
        "- Movement shooting, rim pressure, vertical spacing, fouls, and transition "
        "pressure need richer tracking data.",
        "- Defense claims require more than steals: position, size, minutes, and "
        "defensive-event evidence are all checked.",
        "- These profiles allow or block claims. They do not replace scouting.",
    ]
    return "\n".join(lines)


def _table(frame: pd.DataFrame, dimension: str) -> str:
    if frame.empty:
        return "No players passed this claim gate."
    cols = [
        "player_name",
        "current_team",
        "position",
        dimension,
        f"{dimension}_evidence_stat_1",
        f"{dimension}_evidence_stat_2",
        f"{dimension}_evidence_stat_3",
    ]
    lines = ["| Player | Team | Pos | Score | Evidence 1 | Evidence 2 | Evidence 3 |"]
    lines.append("| --- | --- | --- | ---: | --- | --- | --- |")
    for row in frame.head(10)[cols].to_dict(orient="records"):
        lines.append(
            f"| {row['player_name']} | {row['current_team']} | {row['position']} | "
            f"{row[dimension]:.1f} | {row[f'{dimension}_evidence_stat_1']} | "
            f"{row[f'{dimension}_evidence_stat_2']} | "
            f"{row[f'{dimension}_evidence_stat_3']} |"
        )
    return "\n".join(lines)
