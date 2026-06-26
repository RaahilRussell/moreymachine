"""Markdown scouting report exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.models.player_profile_builder import PLAYER_PROFILES_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

SCOUTING_REPORTS_DIR = REPORTS_DATA_DIR / "scouting_reports"


@dataclass(frozen=True)
class ScoutingReportExportResult:
    """Summary from scouting report export."""

    reports: int
    output_dir: Path


def export_scouting_reports(
    *,
    profiles_path: str | Path = PLAYER_PROFILES_PATH,
    output_dir: str | Path = SCOUTING_REPORTS_DIR,
) -> ScoutingReportExportResult:
    """Export one markdown scouting report per player profile."""
    profiles = pd.read_parquet(profiles_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for row in profiles.to_dict(orient="records"):
        path = destination / f"{row['player_profile_id']}.md"
        path.write_text(render_scouting_report(row), encoding="utf-8")
    metadata_file = destination / "_metadata.md"
    metadata_file.write_text(
        f"# Scouting Reports\n\nGenerated {len(profiles)} reports.\n",
        encoding="utf-8",
    )
    write_metadata_for_artifact(
        metadata_file,
        run_id=new_run_id(),
        source_files=(profiles_path,),
        upstream_artifacts=(profiles_path,),
        known_limitations=("Markdown reports mirror generated profile data.",),
    )
    return ScoutingReportExportResult(reports=len(profiles), output_dir=destination)


def render_scouting_report(profile: dict[str, Any]) -> str:
    """Render one player profile as markdown."""
    evidence = _json_list(profile.get("evidence_objects"))
    lines = [
        f"# {profile.get('player_name')}",
        "",
        "## Executive Summary",
        "",
        _text(profile.get("executive_summary")),
        "",
        "## Recommendation",
        "",
        f"- Recommendation: {_text(profile.get('recommendation'))}",
        f"- Fit score: {_text(profile.get('final_fit_score'))}",
        f"- Confidence: {_text(profile.get('recommendation_confidence'))}",
        f"- Completeness: {_text(profile.get('profile_completeness'))}",
        "",
        "## Fit Score Breakdown",
        "",
        _text(profile.get("evidence_summary")),
        "",
        "## What He Helps Most",
        "",
        _text(profile.get("what_he_helps_most")),
        "",
        "## What He Does Not Solve",
        "",
        _text(profile.get("what_he_does_not_solve")),
        "",
        "## Role on Sixers",
        "",
        f"- Role: {_text(profile.get('role_on_sixers'))}",
        f"- Primary slot: {_text(profile.get('primary_roster_slot'))}",
        f"- Minutes context: {_text(profile.get('expected_minutes_context'))}",
        f"- Starter possible: {_text(profile.get('starter_possible'))}",
        f"- Closing possible: {_text(profile.get('closing_possible'))}",
        (
            f"- Playoff rotation possible: "
            f"{_text(profile.get('playoff_rotation_possible'))}"
        ),
        "",
        "## Fit with Embiid/Maxey/George",
        "",
        f"- Embiid: {_text(profile.get('fit_with_embiid'))}",
        f"- Maxey: {_text(profile.get('fit_with_maxey'))}",
        f"- George: {_text(profile.get('fit_with_george'))}",
        "",
        "## Salary and Acquisition",
        "",
        _text(profile.get("salary_and_acquisition_explanation")),
        "",
        "## Scenarios",
        "",
        _scenario_line("Best case", profile.get("best_case_scenario")),
        _scenario_line("Realistic", profile.get("realistic_scenario")),
        _scenario_line("Downside", profile.get("downside_scenario")),
        _scenario_line("Playoff", profile.get("playoff_scenario")),
        "",
        "## Evidence",
        "",
        _evidence_table(evidence),
        "",
        "## Concerns",
        "",
        _text(profile.get("main_concerns")),
        "",
        "## Missing Data",
        "",
        _text(profile.get("missing_or_stale_data")),
        "",
        "## Why This Could Be Wrong",
        "",
        _text(profile.get("why_this_could_be_wrong")),
    ]
    return "\n".join(lines).strip() + "\n"


def _scenario_line(label: str, payload: Any) -> str:
    data = _json_obj(payload)
    if not data:
        return f"- {label}: missing"
    return f"- {label}: {data.get('upside_case', '')} Risk: {data.get('risk_case', '')}"


def _evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "No evidence objects generated."
    lines = [
        "| Claim | Evidence Type | Confidence | Missing Data |",
        "| --- | --- | --- | --- |",
    ]
    for item in evidence[:20]:
        lines.append(
            f"| {_text(item.get('claim'))} | {_text(item.get('evidence_type'))} | "
            f"{_text(item.get('confidence'))} | "
            f"{_text(item.get('missing_data_flags'))} |"
        )
    return "\n".join(lines)


def _json_obj(value: Any) -> dict[str, Any]:
    if not value or pd.isna(value):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _json_list(value: Any) -> list[dict[str, Any]]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _text(value: Any) -> str:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return "missing"
    return str(value).replace("\n", " ").strip()
