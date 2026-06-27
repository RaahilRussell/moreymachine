"""Team-context loading for team-scoped product builds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from moreymachine.config.teams import (
    GENERIC_TEAM_CONTEXT,
    TEAM_CONTEXT_DIR,
    normalize_team,
    team_name,
)


def load_team_context(team: str) -> dict[str, Any]:
    """Load custom team context or generic fallback."""
    normalized = normalize_team(team)
    path = _context_path(normalized)
    if not path.exists():
        path = _context_path(GENERIC_TEAM_CONTEXT)
    payload = _read_yaml(path)
    payload.setdefault("team_abbr", normalized)
    if payload.get("team_abbr") == GENERIC_TEAM_CONTEXT:
        payload["team_abbr"] = normalized
        payload.setdefault("team_name", team_name(normalized))
    payload.setdefault("team_name", team_name(normalized))
    payload.setdefault("context_mode", "generic")
    payload.setdefault("core_players", [])
    payload.setdefault("locked_roles", {})
    payload.setdefault("open_slots", payload.get("open_roster_slots", []))
    payload.setdefault("blocked_slots", payload.get("blocked_roster_slots", []))
    payload.setdefault("must_not_violate_rules", [])
    payload.setdefault("manual_notes", [])
    payload["_context_path"] = str(path)
    return payload


def get_core_players(context: dict[str, Any]) -> list[str]:
    """Return core player names from either old or new context shape."""
    players = context.get("core_players") or []
    names: list[str] = []
    for item in players:
        if isinstance(item, dict):
            name = item.get("player_name") or item.get("name")
        else:
            name = item
        if name:
            names.append(str(name))
    return names


def get_open_slots(context: dict[str, Any]) -> list[str]:
    """Return open roster-slot names."""
    slots = context.get("open_slots") or context.get("open_roster_slots") or []
    return [str(slot) for slot in slots]


def get_blocked_slots(context: dict[str, Any]) -> list[str]:
    """Return blocked roster-slot names."""
    slots = context.get("blocked_slots") or context.get("blocked_roster_slots") or []
    return [str(slot) for slot in slots]


def is_custom_context(context: dict[str, Any]) -> bool:
    """Return whether context is a custom team file."""
    return str(context.get("context_mode", "")).lower() == "custom"


def _context_path(team: str) -> Path:
    return TEAM_CONTEXT_DIR / f"{normalize_team(team)}.yml"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}
