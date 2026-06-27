"""Benchmark comparison layer for team-scoped GM diagnosis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import make_run_id, write_artifact, write_json_artifact
from moreymachine.features.contender_blueprints import CONTENDER_BLUEPRINTS_PATH
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

TEAM_COMPARISON_PATH = REPORTS_DATA_DIR / "team_comparison.parquet"
TEAM_COMPARISON_JSON_PATH = REPORTS_DATA_DIR / "team_comparison.json"

METRICS = (
    ("net_rating", "net_rating", False),
    ("offensive_rating", "off_rating", False),
    ("defensive_rating", "def_rating", True),
    ("three_point_attempt_rate", "three_pa_rate", False),
    ("three_point_percentage", "three_p_pct", False),
    ("estimated_shooting_pressure", "role_player_spacing_proxy", False),
    ("estimated_two_way_balance", "playoff_portability_proxy", False),
)


@dataclass(frozen=True)
class TeamComparisonResult:
    """Summary for a team-comparison build."""

    team: str
    rows: int
    output_path: Path
    json_path: Path


def build_team_comparison(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    team_fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    blueprints_path: str | Path = CONTENDER_BLUEPRINTS_PATH,
    output_path: str | Path = TEAM_COMPARISON_PATH,
    json_path: str | Path = TEAM_COMPARISON_JSON_PATH,
) -> TeamComparisonResult:
    """Compare the selected team to contender and style benchmarks."""
    normalized = team.upper()
    teams = _optional_parquet(team_fingerprints_path)
    blueprints = _optional_parquet(blueprints_path)
    current = _latest_team_row(teams, normalized)
    latest_season = current.get("season")

    rows: list[dict[str, Any]] = []
    rows.extend(_blueprint_rows(current, blueprints))
    rows.extend(_style_rows(current, teams, latest_season))
    rows.extend(_current_peer_rows(current, teams, latest_season))
    if not rows:
        rows.append(_partial_row(normalized))

    frame = pd.DataFrame(rows)
    output = Path(output_path)
    json_output = Path(json_path)
    run_id = make_run_id()
    metadata = _metadata(normalized, run_id, (team_fingerprints_path, blueprints_path))
    write_artifact(frame, output, metadata)
    write_json_artifact(frame.to_dict(orient="records"), json_output, metadata)
    return TeamComparisonResult(
        team=normalized,
        rows=len(frame),
        output_path=output,
        json_path=json_output,
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


def _blueprint_rows(current: dict[str, Any], blueprints: pd.DataFrame) -> list[dict[str, Any]]:
    if blueprints.empty:
        return []
    names = {
        "champions": "Champion average",
        "finalists": "Finalist average",
        "conference_finalists": "Conference finalist average",
        "top_5_net_rating": "Top 5 net-rating average",
        "top_10_net_rating": "Top 10 net-rating average",
        "wing_depth_switchable": "Wing-depth archetype",
        "star_center_anchor": "Star-center archetype",
        "shooting_pressure": "Shooting-pressure archetype",
    }
    rows = []
    for blueprint_id, label in names.items():
        match = blueprints[blueprints["blueprint_id"].astype(str) == blueprint_id]
        if not match.empty:
            rows.append(_comparison_row(current, match.iloc[0].to_dict(), label, "contender_blueprint"))
    return rows


def _style_rows(
    current: dict[str, Any],
    teams: pd.DataFrame,
    latest_season: Any,
) -> list[dict[str, Any]]:
    if teams.empty or latest_season is None:
        return []
    labels = {
        "BOS": "Boston-style current benchmark",
        "DEN": "Denver-style current benchmark",
        "OKC": "OKC-style current benchmark",
    }
    rows = []
    for abbr, label in labels.items():
        row = _team_row_for_season(teams, abbr, latest_season)
        if row:
            rows.append(_comparison_row(current, row, label, "current_team_style"))
    return rows


def _current_peer_rows(
    current: dict[str, Any],
    teams: pd.DataFrame,
    latest_season: Any,
) -> list[dict[str, Any]]:
    if teams.empty or latest_season is None:
        return []
    season = teams[teams["season"].astype(str) == str(latest_season)].copy()
    if season.empty or "net_rating" not in season.columns:
        return []
    top = season.sort_values("net_rating", ascending=False).head(5)
    rows = []
    for row in top.to_dict(orient="records"):
        rows.append(
            _comparison_row(
                current,
                row,
                f"{row.get('team_abbr')} current top-net-rating peer",
                "current_team",
            )
        )
    return rows


def _team_row_for_season(
    teams: pd.DataFrame,
    abbr: str,
    season: Any,
) -> dict[str, Any]:
    subset = teams[
        (teams["team_abbr"].astype(str).str.upper() == abbr)
        & (teams["season"].astype(str) == str(season))
    ]
    if subset.empty:
        return {}
    return subset.iloc[0].to_dict()


def _comparison_row(
    current: dict[str, Any],
    benchmark: dict[str, Any],
    label: str,
    benchmark_type: str,
) -> dict[str, Any]:
    metric_rows = []
    total_gap = 0.0
    available = 0
    for team_metric, benchmark_metric, lower_is_better in METRICS:
        team_value = _number(current.get(team_metric))
        benchmark_value = _number(benchmark.get(benchmark_metric, benchmark.get(team_metric)))
        if team_value is None or benchmark_value is None:
            metric_rows.append(
                {
                    "metric": team_metric,
                    "team_value": None,
                    "benchmark_value": benchmark_value,
                    "gap": None,
                    "direction": "missing",
                }
            )
            continue
        gap = benchmark_value - team_value
        if lower_is_better:
            gap = team_value - benchmark_value
        total_gap += abs(float(gap))
        available += 1
        metric_rows.append(
            {
                "metric": team_metric,
                "team_value": round(float(team_value), 3),
                "benchmark_value": round(float(benchmark_value), 3),
                "gap": round(float(gap), 3),
                "direction": "needs improvement" if gap > 0 else "at or above benchmark",
            }
        )
    missing_flags = [] if available == len(METRICS) else ["partial_metric_coverage"]
    return {
        "team_abbr": current.get("team_abbr"),
        "season": current.get("season"),
        "benchmark": label,
        "benchmark_type": benchmark_type,
        "benchmark_id": benchmark.get("blueprint_id") or benchmark.get("team_abbr") or label,
        "overall_gap_score": round(total_gap / available, 3) if available else 50.0,
        "net_rating_gap": _metric_gap(metric_rows, "net_rating"),
        "offense_gap": _metric_gap(metric_rows, "offensive_rating"),
        "defense_gap": _metric_gap(metric_rows, "defensive_rating"),
        "shooting_gap": _metric_gap(metric_rows, "estimated_shooting_pressure"),
        "two_way_gap": _metric_gap(metric_rows, "estimated_two_way_balance"),
        "metric_comparison": json.dumps(metric_rows, sort_keys=True),
        "why_it_matters": _why_it_matters(label, metric_rows),
        "confidence": "Medium" if missing_flags else "High",
        "evidence": (
            "Comparison uses cached team fingerprints and contender-blueprint averages."
        ),
        "missing_data_flags": ";".join(missing_flags) if missing_flags else "none",
        "created_at": datetime.now(UTC).isoformat(),
        "data_mode": "derived",
    }


def _partial_row(team: str) -> dict[str, Any]:
    return {
        "team_abbr": team,
        "season": "unknown",
        "benchmark": "No benchmark available",
        "benchmark_type": "partial",
        "benchmark_id": "partial",
        "overall_gap_score": 50.0,
        "net_rating_gap": None,
        "offense_gap": None,
        "defense_gap": None,
        "shooting_gap": None,
        "two_way_gap": None,
        "metric_comparison": "[]",
        "why_it_matters": "Benchmark comparison could not be built from cached artifacts.",
        "confidence": "Low",
        "evidence": "Partial artifact written instead of inventing benchmark data.",
        "missing_data_flags": "team_fingerprints_or_blueprints_missing",
        "created_at": datetime.now(UTC).isoformat(),
        "data_mode": "derived",
    }


def _metric_gap(metric_rows: list[dict[str, Any]], metric: str) -> float | None:
    for row in metric_rows:
        if row["metric"] == metric:
            return row["gap"]
    return None


def _why_it_matters(label: str, metric_rows: list[dict[str, Any]]) -> str:
    gaps = [
        row["metric"].replace("_", " ")
        for row in metric_rows
        if row.get("direction") == "needs improvement"
    ][:3]
    if not gaps:
        return f"{label} does not show a major measured gap in available metrics."
    return f"{label} highlights improvement needs in {', '.join(gaps)}."


def _number(value: Any) -> float | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def _metadata(team: str, run_id: str, sources: tuple[str | Path, ...]) -> dict[str, Any]:
    return {
        "artifact_name": "team_comparison",
        "team": team,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source_files": [str(Path(source)) for source in sources],
        "upstream_artifacts": [str(Path(source)) for source in sources],
        "data_mode": "derived",
        "known_limitations": [
            "Benchmark comparison uses cached public-data metrics.",
            "Style benchmarks are current-team proxies, not statements of team intent.",
        ],
    }
