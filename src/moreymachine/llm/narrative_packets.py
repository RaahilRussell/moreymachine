"""Build grounded narrative packets and summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import ensure_team_output_dirs, normalize_team
from moreymachine.data.lineage import make_run_id, write_json_artifact
from moreymachine.llm.narrative_cache import cache_key, read_cache, write_cache
from moreymachine.llm.ollama_client import (
    OllamaUnavailableError,
    load_ollama_config,
    summarize_with_ollama,
)
from moreymachine.llm.prompt_templates import GM_EXECUTIVE_SUMMARY_PROMPT
from moreymachine.utils.paths import REPORTS_DATA_DIR


@dataclass(frozen=True)
class NarrativeResult:
    """Summary from narrative build."""

    team: str
    source: str
    markdown_path: Path
    json_path: Path
    packet_path: Path


def build_team_narratives(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    no_ollama: bool = False,
) -> NarrativeResult:
    """Build team-scoped narratives from structured JSON only."""
    normalized = normalize_team(team)
    context = context or {}
    dirs = ensure_team_output_dirs(normalized)
    packet = build_narrative_packet(normalized, context)
    packet_path = dirs["narratives"] / "gm_narrative_packet.json"
    json_path = dirs["narratives"] / "gm_executive_summary.json"
    markdown_path = dirs["narratives"] / "gm_executive_summary.md"
    fallback_path = dirs["narratives"] / "deterministic_fallback_summary.md"
    run_id = make_run_id()
    metadata = _metadata(normalized, run_id, packet)
    write_json_artifact(packet, packet_path, metadata)

    config = load_ollama_config()
    summary_source = "deterministic_fallback"
    summary = deterministic_summary(packet)
    if not no_ollama and config.enabled:
        prompt = GM_EXECUTIVE_SUMMARY_PROMPT.format(
            packet_json=json.dumps(packet, indent=2, sort_keys=True)
        )
        cache_file = dirs["narratives"] / "narrative_cache.json"
        key = cache_key({"prompt": prompt, "model": config.model})
        cache = read_cache(cache_file) if config.cache_enabled else {}
        try:
            if key in cache:
                summary = str(cache[key])
                summary_source = "ollama_cache"
            else:
                summary = summarize_with_ollama(prompt, config)
                summary_source = "ollama"
                if config.cache_enabled:
                    cache[key] = summary
                    write_cache(cache_file, cache)
        except OllamaUnavailableError:
            summary = deterministic_summary(packet)
            summary_source = "deterministic_fallback"

    payload = {
        "team_abbr": normalized,
        "summary_source": summary_source,
        "summary_markdown": summary,
        "structured_packet_path": str(packet_path),
        "created_at": datetime.now(UTC).isoformat(),
        "missing_data_flags": packet.get("missing_data_flags", []),
    }
    write_json_artifact(payload, json_path, metadata)
    markdown_path.write_text(summary, encoding="utf-8")
    fallback_path.write_text(deterministic_summary(packet), encoding="utf-8")
    return NarrativeResult(
        team=normalized,
        source=summary_source,
        markdown_path=markdown_path,
        json_path=json_path,
        packet_path=packet_path,
    )


def build_narrative_packet(team: str, context: dict[str, Any]) -> dict[str, Any]:
    """Create the JSON packet that Ollama is allowed to summarize."""
    team_level = _read_json(_team_report_path(team, "team_level.json"))
    action_cards = _read_json(_team_report_path(team, "action_cards.json")) or []
    team_comparison = _read_json(_team_report_path(team, "team_comparison.json")) or []
    rankings = _top_rows(_team_report_path(team, "candidate_fit_rankings_v2.parquet"), 12)
    missing = []
    for name, value in (
        ("team_level", team_level),
        ("action_cards", action_cards),
        ("team_comparison", team_comparison),
        ("candidate_rankings", rankings),
    ):
        if not value:
            missing.append(f"{name}_missing")
    return {
        "team_abbr": team,
        "context": {
            "context_mode": context.get("context_mode", "unknown"),
            "core_players": context.get("core_players", []),
            "must_not_violate_rules": context.get("must_not_violate_rules", []),
        },
        "team_level": team_level or {},
        "action_cards": action_cards,
        "team_comparison": team_comparison[:8] if isinstance(team_comparison, list) else [],
        "top_ranked_candidates": rankings,
        "missing_data_flags": missing or ["none"],
        "source_rule": (
            "Narrative may only summarize this JSON. It cannot add salary, "
            "injury, availability, transaction, or team-intent claims."
        ),
    }


def deterministic_summary(packet: dict[str, Any]) -> str:
    """Build a readable fallback summary without an LLM."""
    team_level = packet.get("team_level") or {}
    cards = packet.get("action_cards") or []
    by_category = {card.get("action_category"): card for card in cards}
    top_actions = [
        by_category.get("best_overall_action"),
        by_category.get("best_realistic_free_agent"),
        by_category.get("best_realistic_trade"),
    ]
    lines = [
        f"# {packet.get('team_abbr')} GM Executive Summary",
        "",
        f"Level: {team_level.get('team_level', 'missing')} "
        f"({team_level.get('level_score', 'missing')}).",
        f"Closest benchmark/archetype: {team_level.get('closest_archetype', 'missing')}.",
        "",
        "## What To Do First",
    ]
    for card in [item for item in top_actions if item]:
        lines.append(f"- {card.get('action_title')}: {card.get('why_do_this')}")
    avoid = by_category.get("top_avoid_move")
    if avoid:
        lines.extend(["", "## What Not To Do", f"- {avoid.get('action_title')}: {avoid.get('why_not_do_this')}"])
    lines.extend(["", "## What Could Be Wrong"])
    flags = packet.get("missing_data_flags") or ["none"]
    if flags == ["none"]:
        lines.append("- No packet-level artifact is missing, but public salary/status data can still be incomplete.")
    else:
        lines.extend([f"- {flag}" for flag in flags])
    lines.extend(["", "## Evidence Boundary", f"- {packet.get('source_rule')}"])
    return "\n".join(lines)


def _team_report_path(team: str, filename: str) -> Path:
    team_path = ensure_team_output_dirs(team)["reports"] / filename
    if team_path.exists():
        return team_path
    return REPORTS_DATA_DIR / filename


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _top_rows(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    columns = [
        "rank",
        "player_id",
        "player_profile_id",
        "player_name",
        "board_type",
        "recommendation",
        "final_recommendation_score",
        "primary_roster_slot",
        "acquisition_path",
        "evidence_summary",
        "missing_data_flags",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame[available].head(limit).to_dict(orient="records")


def _metadata(team: str, run_id: str, packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_name": "gm_narrative",
        "team": team,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source_files": [],
        "upstream_artifacts": [
            "team_level.json",
            "team_comparison.json",
            "action_cards.json",
            "candidate_fit_rankings_v2.parquet",
        ],
        "data_mode": "derived",
        "known_limitations": [
            "Narrative is a summary of structured artifacts only.",
            "Ollama is optional and never the source of truth.",
            "Packet missing flags: " + ", ".join(packet.get("missing_data_flags", [])),
        ],
    }

