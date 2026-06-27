"""Team-level diagnosis for the GM operating system."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import team_name
from moreymachine.data.lineage import make_run_id, write_artifact, write_json_artifact
from moreymachine.features.contender_blueprints import (
    CONTENDER_BLUEPRINTS_PATH,
    TEAM_CONSTRUCTION_ARCHETYPES_PATH,
)
from moreymachine.features.gap_model import SIXERS_GAP_MODEL_PATH
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

TEAM_LEVEL_PATH = REPORTS_DATA_DIR / "team_level.parquet"
TEAM_LEVEL_JSON_PATH = REPORTS_DATA_DIR / "team_level.json"
TEAM_LEVEL_MARKDOWN_PATH = REPORTS_DATA_DIR / "team_level.md"


@dataclass(frozen=True)
class TeamLevelResult:
    """Summary for a team-level build."""

    team: str
    team_level: str
    level_score: float
    output_path: Path
    json_path: Path
    markdown_path: Path


def build_team_level(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    team_fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    blueprints_path: str | Path = CONTENDER_BLUEPRINTS_PATH,
    archetypes_path: str | Path = TEAM_CONSTRUCTION_ARCHETYPES_PATH,
    gap_model_path: str | Path = SIXERS_GAP_MODEL_PATH,
    output_path: str | Path = TEAM_LEVEL_PATH,
    json_path: str | Path = TEAM_LEVEL_JSON_PATH,
    markdown_path: str | Path = TEAM_LEVEL_MARKDOWN_PATH,
) -> TeamLevelResult:
    """Build a summary-first team-level diagnosis."""
    normalized = team.upper()
    context = context or {}
    fingerprints = _optional_parquet(team_fingerprints_path)
    blueprints = _optional_parquet(blueprints_path)
    archetypes = _optional_parquet(archetypes_path)
    gaps = _optional_parquet(gap_model_path)

    current = _latest_team_row(fingerprints, normalized)
    current_season = _same_season(fingerprints, current)
    archetype = _current_archetype(archetypes, normalized, current.get("season"))
    closest = _closest_blueprint(blueprints, archetype)
    missing_flags = _missing_flags(
        current=current,
        current_season=current_season,
        blueprints=blueprints,
        archetype=archetype,
        gaps=gaps,
    )

    score_components = _level_score_components(current, current_season, gaps)
    level_score = round(sum(score_components.values()) / len(score_components), 2)
    payload = {
        "team_abbr": normalized,
        "team_name": context.get("team_name") or team_name(normalized),
        "season": current.get("season") or context.get("season") or "unknown",
        "team_level": _team_level(level_score),
        "level_score": level_score,
        "contender_percentile": round(score_components["net_rating_percentile"], 2),
        "closest_archetype": closest.get("blueprint_name")
        or _pretty(archetype or "unknown"),
        "closest_benchmark_teams": _benchmark_teams(archetypes, archetype, normalized),
        "main_strengths": _main_strengths(current, current_season),
        "main_weaknesses": _main_weaknesses(gaps, current, current_season),
        "why_this_level": _why_this_level(current, score_components, gaps),
        "what_level_requires_next": _what_next(closest, gaps),
        "confidence": _confidence(missing_flags),
        "evidence": _evidence(current, closest, gaps),
        "missing_data_flags": missing_flags or ["none"],
        "source_summary": (
            "team_fingerprints; contender_blueprints; team_construction_archetypes; "
            "gap_model; manual_team_context"
        ),
        "created_at": datetime.now(UTC).isoformat(),
        "data_mode": "derived",
    }

    frame = pd.DataFrame([_parquet_row(payload)])
    output = Path(output_path)
    json_output = Path(json_path)
    markdown_output = Path(markdown_path)
    run_id = make_run_id()
    metadata = _metadata(normalized, run_id, (team_fingerprints_path, blueprints_path, archetypes_path, gap_model_path))
    write_artifact(frame, output, metadata)
    write_json_artifact(payload, json_output, metadata)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_render_markdown(payload), encoding="utf-8")

    return TeamLevelResult(
        team=normalized,
        team_level=str(payload["team_level"]),
        level_score=level_score,
        output_path=output,
        json_path=json_output,
        markdown_path=markdown_output,
    )


def _optional_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _latest_team_row(frame: pd.DataFrame, team: str) -> dict[str, Any]:
    if frame.empty or "team_abbr" not in frame.columns:
        return {"team_abbr": team}
    subset = frame[frame["team_abbr"].astype(str).str.upper() == team].copy()
    if subset.empty:
        return {"team_abbr": team}
    subset["_season_sort"] = subset["season"].astype(str)
    return subset.sort_values("_season_sort").drop(columns=["_season_sort"]).iloc[-1].to_dict()


def _same_season(frame: pd.DataFrame, current: dict[str, Any]) -> pd.DataFrame:
    if frame.empty or not current.get("season"):
        return pd.DataFrame()
    return frame[frame["season"].astype(str) == str(current["season"])].copy()


def _current_archetype(
    frame: pd.DataFrame,
    team: str,
    season: Any,
) -> str:
    if frame.empty or "team_abbr" not in frame.columns:
        return ""
    subset = frame[frame["team_abbr"].astype(str).str.upper() == team].copy()
    if season is not None and "season" in subset.columns:
        exact = subset[subset["season"].astype(str) == str(season)]
        if not exact.empty:
            subset = exact
    if subset.empty:
        return ""
    if "blueprint_id" in subset.columns:
        return str(subset.iloc[-1]["blueprint_id"])
    return str(subset.iloc[-1].get("team_construction_archetype") or "")


def _closest_blueprint(frame: pd.DataFrame, archetype: str) -> dict[str, Any]:
    if frame.empty:
        return {}
    if archetype and "blueprint_id" in frame.columns:
        match = frame[frame["blueprint_id"].astype(str) == archetype]
        if not match.empty:
            return match.iloc[0].to_dict()
    if "phi_distance" in frame.columns:
        return frame.sort_values("phi_distance", ascending=True).iloc[0].to_dict()
    return frame.iloc[0].to_dict()


def _level_score_components(
    current: dict[str, Any],
    season_frame: pd.DataFrame,
    gaps: pd.DataFrame,
) -> dict[str, float]:
    return {
        "net_rating_percentile": _season_percentile(
            season_frame,
            current,
            "net_rating",
        ),
        "offense_percentile": _season_percentile(
            season_frame,
            current,
            "offensive_rating",
        ),
        "defense_percentile": _season_percentile(
            season_frame,
            current,
            "defensive_rating",
            higher_is_better=False,
        ),
        "two_way_balance_percentile": _current_value_score(
            current,
            "estimated_two_way_balance",
            scale=100,
        ),
        "gap_health_score": _gap_health_score(gaps),
    }


def _season_percentile(
    season_frame: pd.DataFrame,
    current: dict[str, Any],
    column: str,
    *,
    higher_is_better: bool = True,
) -> float:
    if season_frame.empty or column not in season_frame.columns or column not in current:
        return 50.0
    values = pd.to_numeric(season_frame[column], errors="coerce").dropna()
    value = pd.to_numeric(pd.Series([current.get(column)]), errors="coerce").iloc[0]
    if pd.isna(value) or values.empty:
        return 50.0
    percentile = float((values <= value).mean() * 100)
    if not higher_is_better:
        percentile = 100 - percentile
    return round(percentile, 2)


def _current_value_score(current: dict[str, Any], column: str, *, scale: float) -> float:
    value = pd.to_numeric(pd.Series([current.get(column)]), errors="coerce").iloc[0]
    if pd.isna(value):
        return 50.0
    return round(max(0.0, min(100.0, float(value) * scale)), 2)


def _gap_health_score(gaps: pd.DataFrame) -> float:
    if gaps.empty or "severity" not in gaps.columns:
        return 50.0
    severities = pd.to_numeric(gaps["severity"], errors="coerce").dropna()
    if severities.empty:
        return 50.0
    top = severities.sort_values(ascending=False).head(6)
    return round(max(0.0, min(100.0, 100 - (float(top.mean()) * 2))), 2)


def _team_level(score: float) -> str:
    if score >= 85:
        return "Title Contender"
    if score >= 72:
        return "Contender"
    if score >= 60:
        return "Playoff-Plus"
    if score >= 48:
        return "Play-In / High-Variance"
    return "Developmental / Gap-Heavy"


def _main_strengths(current: dict[str, Any], season_frame: pd.DataFrame) -> list[str]:
    mapping = {
        "offensive_rating": "offense",
        "defensive_rating": "defense",
        "three_point_attempt_rate": "three-point volume",
        "three_point_percentage": "three-point accuracy",
        "estimated_two_way_balance": "two-way balance",
    }
    strengths = []
    for column, label in mapping.items():
        higher = column != "defensive_rating"
        percentile = _season_percentile(season_frame, current, column, higher_is_better=higher)
        if percentile >= 65:
            strengths.append(f"{label} rates above the current-season median")
    return strengths or ["No clear above-median team-strength signal in cached data"]


def _main_weaknesses(
    gaps: pd.DataFrame,
    current: dict[str, Any],
    season_frame: pd.DataFrame,
) -> list[str]:
    weaknesses = []
    if not gaps.empty and {"gap_name", "severity"}.issubset(gaps.columns):
        ordered = gaps.sort_values("severity", ascending=False).head(5)
        weaknesses.extend(str(name) for name in ordered["gap_name"].tolist())
    if _season_percentile(season_frame, current, "defensive_rating", higher_is_better=False) < 50:
        weaknesses.append("team defense trails contender-level benchmarks")
    return list(dict.fromkeys(weaknesses)) or ["Weakness detail is limited by missing gap data"]


def _why_this_level(
    current: dict[str, Any],
    components: dict[str, float],
    gaps: pd.DataFrame,
) -> list[str]:
    facts = [
        f"net rating is {current.get('net_rating', 'unknown')} in the latest cached season",
        f"net-rating percentile component is {components['net_rating_percentile']}",
        f"defense percentile component is {components['defense_percentile']}",
        f"gap-health component is {components['gap_health_score']}",
    ]
    if not gaps.empty and "gap_name" in gaps.columns:
        facts.append(
            "top gap priorities are "
            + ", ".join(str(x) for x in gaps.sort_values("severity", ascending=False)["gap_name"].head(3))
        )
    return facts


def _what_next(closest: dict[str, Any], gaps: pd.DataFrame) -> list[str]:
    actions = []
    if closest.get("what_moves_phi_closer"):
        actions.extend(_split_semicolon(str(closest["what_moves_phi_closer"])))
    if not gaps.empty and {"what_fixes_it", "gap_name"}.issubset(gaps.columns):
        for row in gaps.sort_values("severity", ascending=False).head(3).to_dict(orient="records"):
            fixes = _json_list(row.get("what_fixes_it"))
            if fixes:
                actions.append(f"{row['gap_name']}: {', '.join(fixes[:2])}")
    return list(dict.fromkeys(actions)) or ["Add validated role-player answers to the highest-severity gaps"]


def _evidence(
    current: dict[str, Any],
    closest: dict[str, Any],
    gaps: pd.DataFrame,
) -> list[str]:
    evidence = [
        f"latest cached team fingerprint for {current.get('team_abbr', 'team')}: season {current.get('season', 'unknown')}",
    ]
    if closest:
        evidence.append(
            f"closest benchmark archetype: {closest.get('blueprint_name') or closest.get('blueprint_id')}"
        )
    if not gaps.empty:
        evidence.append(f"{len(gaps)} gap-model rows available")
    return evidence


def _benchmark_teams(
    archetypes: pd.DataFrame,
    archetype: str,
    team: str,
) -> list[str]:
    if archetypes.empty or not archetype:
        return []
    subset = archetypes[
        (archetypes.get("blueprint_id", pd.Series(dtype=str)).astype(str) == archetype)
        & (archetypes["team_abbr"].astype(str).str.upper() != team)
    ].copy()
    if subset.empty:
        return []
    subset["_score"] = pd.to_numeric(subset.get("net_rating"), errors="coerce").fillna(0)
    subset = subset.sort_values(["_score", "season"], ascending=[False, False]).head(5)
    return [
        f"{row['season']} {row['team_abbr']}"
        for row in subset.to_dict(orient="records")
    ]


def _missing_flags(
    *,
    current: dict[str, Any],
    current_season: pd.DataFrame,
    blueprints: pd.DataFrame,
    archetype: str,
    gaps: pd.DataFrame,
) -> list[str]:
    flags = []
    if not current or current.get("season") is None:
        flags.append("team_fingerprint_missing")
    if current_season.empty:
        flags.append("current_season_peer_context_missing")
    if blueprints.empty:
        flags.append("contender_blueprints_missing")
    if not archetype:
        flags.append("team_archetype_missing")
    if gaps.empty:
        flags.append("gap_model_missing")
    return flags


def _confidence(flags: list[str]) -> str:
    if not flags:
        return "High"
    if len(flags) <= 2:
        return "Medium"
    return "Low"


def _parquet_row(payload: dict[str, Any]) -> dict[str, Any]:
    row = payload.copy()
    for key in (
        "closest_benchmark_teams",
        "main_strengths",
        "main_weaknesses",
        "why_this_level",
        "what_level_requires_next",
        "evidence",
        "missing_data_flags",
    ):
        row[key] = json.dumps(row[key], sort_keys=True)
    return row


def _render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {payload['team_abbr']} Team Level",
            "",
            f"**Level:** {payload['team_level']} ({payload['level_score']})",
            f"**Closest archetype:** {payload['closest_archetype']}",
            f"**Confidence:** {payload['confidence']}",
            "",
            "## What Matters",
            *_bullet_lines(payload["why_this_level"]),
            "",
            "## Next Level Requires",
            *_bullet_lines(payload["what_level_requires_next"]),
            "",
            "## Missing Data Flags",
            *_bullet_lines(payload["missing_data_flags"]),
            "",
        ]
    )


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _metadata(team: str, run_id: str, sources: tuple[str | Path, ...]) -> dict[str, Any]:
    return {
        "artifact_name": "team_level",
        "team": team,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source_files": [str(Path(source)) for source in sources],
        "upstream_artifacts": [str(Path(source)) for source in sources],
        "data_mode": "derived",
        "known_limitations": [
            "Team level is a deterministic diagnosis from cached public-data artifacts.",
            "Neutral 50 components are used when a component is missing.",
            "It does not know private team intent, injuries, or true trade availability.",
        ],
    }


def _json_list(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _pretty(value: str) -> str:
    return value.replace("_", " ").strip().title()
