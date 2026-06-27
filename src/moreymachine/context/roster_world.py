"""Build the current Sixers roster world.

The roster world converts "current roster rows" into explicit role-slot context.
It is the first layer that prevents general player quality from becoming a
Philadelphia-specific role projection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.utils.paths import (
    CURRENT_ROSTER_REFERENCE_PATH,
    MANUAL_DATA_DIR,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    PROCESSED_DATA_DIR,
    REPORTS_DATA_DIR,
)

TEAM_CONTEXT_PATH = MANUAL_DATA_DIR / "team_context" / "PHI.yml"
ROSTER_WORLD_PATH = PROCESSED_DATA_DIR / "roster_world_phi.parquet"
ROSTER_WORLD_REPORT_PATH = REPORTS_DATA_DIR / "roster_world_phi.md"


@dataclass(frozen=True)
class RosterWorldResult:
    """Summary from a roster-world build."""

    rows: int
    core_players: int
    open_slots: int
    blocked_slots: int
    output_path: Path
    report_path: Path


def build_roster_world(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
    no_ollama: bool = False,
    skip_refresh: bool = False,
    force: bool = False,
    roster_reference_path: str | Path = CURRENT_ROSTER_REFERENCE_PATH,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    team_context_path: str | Path = TEAM_CONTEXT_PATH,
    output_path: str | Path = ROSTER_WORLD_PATH,
    report_path: str | Path = ROSTER_WORLD_REPORT_PATH,
) -> RosterWorldResult:
    """Build the PHI roster-world artifact."""
    del no_ollama, skip_refresh, force
    context = context or load_team_context(team_context_path)
    context = _normalize_context(context, team)
    roster = pd.read_parquet(roster_reference_path)
    seasons = _latest_seasons(pd.read_parquet(player_seasons_path))
    bio = _optional_parquet(player_bio_path)
    frame = _merge_roster_inputs(roster, seasons, bio)
    world = _build_world_rows(frame, context)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    world.to_parquet(output, index=False)

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_render_report(world, context))

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                roster_reference_path,
                player_seasons_path,
                player_bio_path,
                team_context_path,
            ),
            upstream_artifacts=(roster_reference_path, player_seasons_path),
            known_limitations=(
                "Roster context includes manual basketball assumptions.",
                "Injury status and private team intent are not sourced.",
            ),
        )

    core_names = set(_core_roles(context))
    return RosterWorldResult(
        rows=len(world),
        core_players=int(world["player_name"].isin(core_names).sum()),
        open_slots=len(_open_slots(context)),
        blocked_slots=len(_blocked_slots(context)),
        output_path=output,
        report_path=report,
    )


def load_team_context(path: str | Path = TEAM_CONTEXT_PATH) -> dict[str, Any]:
    """Load manual team context."""
    with Path(path).open() as file:
        payload = yaml.safe_load(file) or {}
    return payload


def _merge_roster_inputs(
    roster: pd.DataFrame,
    seasons: pd.DataFrame,
    bio: pd.DataFrame | None,
) -> pd.DataFrame:
    frame = roster.copy()
    stat_cols = [
        "player_id",
        "true_shooting",
        "three_pa",
        "three_pa_rate",
        "assist_pct",
        "turnover_pct",
        "rebound_pct",
        "stl",
        "blk",
    ]
    frame = frame.merge(
        seasons[[c for c in stat_cols if c in seasons.columns]].drop_duplicates(
            "player_id"
        ),
        on="player_id",
        how="left",
    )
    if bio is not None and not bio.empty:
        bio_cols = [
            c
            for c in ("player_id", "height_inches", "weight", "source", "pulled_at")
            if c in bio.columns
        ]
        frame = frame.merge(
            bio[bio_cols].drop_duplicates("player_id"),
            on="player_id",
            how="left",
            suffixes=("", "_bio"),
        )
    return frame


def _build_world_rows(frame: pd.DataFrame, context: dict[str, Any]) -> pd.DataFrame:
    core_roles = _core_roles(context)
    likely_starters = set(context.get("likely_starters", []))
    high_rotation = set(context.get("high_rotation_players", []))
    assumptions = "; ".join(
        str(item)
        for item in (
            context.get("assumptions")
            or context.get("lineup_constraints")
            or context.get("manual_notes")
            or []
        )
    )
    source = "current_roster_reference; player_seasons; player_bio; team_context"
    pulled_at = datetime.now(UTC).date().isoformat()

    records = []
    for row in frame.to_dict(orient="records"):
        name = str(row.get("player_name", ""))
        core = core_roles.get(name, {})
        roster_slot = _roster_slot(row, core)
        current_role = _current_role(name, row, core, likely_starters, high_rotation)
        evidence = _evidence(row, roster_slot=roster_slot)
        record = {
            "player_id": row.get("player_id"),
            "player_name": name,
            "team": row.get("current_team") or row.get("team_abbr") or "PHI",
            "position": row.get("position"),
            "height": row.get("height_inches"),
            "weight": row.get("weight"),
            "age": row.get("age"),
            "current_minutes": row.get("minutes"),
            "usage_rate": row.get("usage_rate"),
            "true_shooting": row.get("true_shooting"),
            "three_pa": row.get("three_pa"),
            "three_pa_rate": row.get("three_pa_rate"),
            "assist_pct": row.get("assist_pct"),
            "turnover_pct": row.get("turnover_pct"),
            "rebound_pct": row.get("rebound_pct"),
            "stl": row.get("stl"),
            "blk": row.get("blk"),
            "role_archetype": row.get("role_archetype") or "Unknown",
            "current_role": current_role,
            "locked_role_status": _locked_role_status(name, core),
            "roster_slot": roster_slot,
            "usage_burden": _usage_burden(row.get("usage_rate")),
            "shooting_gravity": _shooting_gravity(row),
            "defensive_role": _defensive_role(row, roster_slot),
            "creation_role": _creation_role(row),
            "replaceability": _replaceability(name, row, core),
            "role_scarcity": _role_scarcity(roster_slot),
            "role_confidence": _role_confidence(row),
            "evidence": json.dumps(evidence, sort_keys=True),
            "assumptions": assumptions,
            "source": source,
            "pulled_at": pulled_at,
            "data_mode": "derived",
            "missing_data_flags": _missing_flags(row),
        }
        records.append(record)
    return pd.DataFrame(records)


def _roster_slot(row: dict, core: dict) -> str:
    name = str(row.get("player_name", ""))
    position = str(row.get("position") or "")
    archetype = str(row.get("role_archetype") or "")
    if name == "Joel Embiid":
        return "starting_center"
    if name == "Tyrese Maxey":
        return "secondary_creator"
    if name == "Paul George":
        return "defensive_forward"
    locked_role = str(core.get("locked_role") or "")
    if locked_role == "starting_forward":
        return "defensive_forward"
    if "C" in position:
        return "backup_center"
    if "Movement Shooter" in archetype:
        return "movement_shooter"
    if "Defensive Wing" in archetype:
        return "defensive_forward"
    if "Point-of-Attack" in archetype:
        return "point_of_attack_defender"
    if "Creator" in archetype:
        return "secondary_creator"
    if "Stretch" in archetype:
        return "stretch_forward"
    return "regular_season_depth"


def _current_role(
    name: str,
    row: dict,
    core: dict,
    likely_starters: set[str],
    high_rotation: set[str],
) -> str:
    if core:
        return str(core.get("locked_role") or "core_player")
    if name in likely_starters:
        return "likely_starter"
    if name in high_rotation:
        return "high_rotation"
    expected = str(row.get("expected_role") or "")
    if expected:
        return expected
    return "depth"


def _locked_role_status(name: str, core: dict) -> str:
    if core:
        return "locked_core_role"
    if name in {"Andre Drummond", "Kyle Lowry"}:
        return "veteran_rotation_context"
    return "not_locked"


def _usage_burden(usage_rate: object) -> str:
    usage = _num(usage_rate)
    if usage >= 0.28:
        return "primary_high"
    if usage >= 0.22:
        return "secondary"
    if usage >= 0.17:
        return "moderate"
    return "low"


def _shooting_gravity(row: dict) -> str:
    three_pa = _num(row.get("three_pa"))
    three_rate = _num(row.get("three_pa_rate"))
    spacing = _num(row.get("spacing_score"))
    if three_pa >= 250 or three_rate >= 0.45 or spacing >= 75:
        return "high"
    if three_pa >= 100 or three_rate >= 0.25 or spacing >= 55:
        return "moderate"
    return "low"


def _defensive_role(row: dict, roster_slot: str) -> str:
    if roster_slot == "starting_center":
        return "rim_anchor"
    if roster_slot in {"backup_center", "non_embiid_center_minutes"}:
        return "center_depth"
    wing = _num(row.get("wing_defense_proxy"))
    poa = _num(row.get("point_of_attack_defense_proxy"))
    rim = _num(row.get("rim_protection_proxy"))
    if rim >= 70:
        return "rim_protection"
    if wing >= 65:
        return "wing_defense"
    if poa >= 65:
        return "point_of_attack"
    return "unverified_or_team_defense"


def _creation_role(row: dict) -> str:
    usage = _num(row.get("usage_rate"))
    assist = _num(row.get("assist_pct"))
    creation = _num(row.get("creation_score"))
    if usage >= 0.28 or creation >= 85:
        return "primary_creation"
    if usage >= 0.20 or assist >= 0.18 or creation >= 65:
        return "secondary_creation"
    if _num(row.get("connector_score")) >= 60:
        return "connector"
    return "low_creation"


def _replaceability(name: str, row: dict, core: dict) -> str:
    if core:
        return "not_replaceable"
    minutes = _num(row.get("minutes"))
    quality = _num(row.get("quality_percentile"))
    if minutes >= 1800 or quality >= 0.8:
        return "hard_to_replace"
    if minutes >= 800 or quality >= 0.5:
        return "replaceable_with_rotation_piece"
    return "replaceable_depth"


def _role_scarcity(roster_slot: str) -> str:
    scarce = {
        "starting_center",
        "backup_center",
        "point_of_attack_defender",
        "movement_shooter",
        "secondary_creator",
    }
    return "scarce" if roster_slot in scarce else "common"


def _role_confidence(row: dict) -> str:
    if str(row.get("missing_data_flags") or "none") not in {"", "none"}:
        return "medium"
    if _num(row.get("minutes")) < 250:
        return "low"
    return "high"


def _evidence(row: dict, *, roster_slot: str) -> dict:
    return {
        "roster_slot": roster_slot,
        "minutes": _safe(row.get("minutes")),
        "usage_rate": _safe(row.get("usage_rate")),
        "true_shooting": _safe(row.get("true_shooting")),
        "three_pa": _safe(row.get("three_pa")),
        "three_pa_rate": _safe(row.get("three_pa_rate")),
        "assist_pct": _safe(row.get("assist_pct")),
        "rebound_pct": _safe(row.get("rebound_pct")),
        "stl": _safe(row.get("stl")),
        "blk": _safe(row.get("blk")),
        "role_archetype": row.get("role_archetype"),
    }


def _missing_flags(row: dict) -> str:
    missing = []
    for column in (
        "height_inches",
        "weight",
        "true_shooting",
        "three_pa",
        "assist_pct",
        "turnover_pct",
        "rebound_pct",
    ):
        value = row.get(column)
        if value is None or pd.isna(value):
            missing.append(column)
    existing = str(row.get("missing_data_flags") or "none")
    if existing not in {"", "none"}:
        missing.extend(flag.strip() for flag in existing.split(";") if flag.strip())
    return "; ".join(dict.fromkeys(missing)) if missing else "none"


def _render_report(world: pd.DataFrame, context: dict[str, Any]) -> str:
    slot_counts = world["roster_slot"].value_counts().to_dict()
    core = world[world["locked_role_status"] == "locked_core_role"]
    team_label = context.get("team_abbr") or context.get("target_team") or "PHI"
    team_name = context.get("team_name") or team_label
    lines = [
        f"# Current {team_name} Roster World",
        "",
        f"- Team: `{team_label}`",
        f"- Season: `{context.get('season', '')}`",
        f"- Players: `{len(world)}`",
        f"- Core players represented: `{len(core)}`",
        "",
        "## Core Players",
        "",
    ]
    for row in core.to_dict(orient="records"):
        lines.append(
            f"- **{row['player_name']}**: `{row['current_role']}`; "
            f"slot `{row['roster_slot']}`; usage burden `{row['usage_burden']}`"
        )
    lines.extend(
        [
            "",
            "## Open Slots",
            "",
            *[f"- {slot}" for slot in _open_slots(context)],
            "",
            "## Blocked Slots",
            "",
            *[f"- {slot}" for slot in _blocked_slots(context)],
            "",
            "## Roster Slot Counts",
            "",
            "| Slot | Players |",
            "| --- | ---: |",
        ]
    )
    for slot, count in slot_counts.items():
        lines.append(f"| {slot} | {count} |")
    lines.extend(
        [
            "",
            "## Must-Not-Violate Rules",
            "",
            *[f"- {rule}" for rule in context.get("must_not_violate_rules", [])],
            "",
            "## Lineup Constraints",
            "",
            *[f"- {rule}" for rule in context.get("lineup_constraints", [])],
            "",
            "## Limitations",
            "",
            "- This artifact models roster context and constraints, not private "
            "team intent.",
            "- Injury and medical risk are not fully sourced.",
            "- Role labels should be refreshed when roster/status data changes.",
        ]
    )
    return "\n".join(lines)


def _normalize_context(context: dict[str, Any], team: str) -> dict[str, Any]:
    normalized = dict(context)
    normalized.setdefault("team_abbr", team)
    if "open_roster_slots" not in normalized and "open_slots" in normalized:
        normalized["open_roster_slots"] = normalized["open_slots"]
    if "blocked_roster_slots" not in normalized and "blocked_slots" in normalized:
        normalized["blocked_roster_slots"] = normalized["blocked_slots"]
    return normalized


def _core_roles(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    locked_roles = context.get("locked_roles") or {}
    if isinstance(locked_roles, dict):
        for name, payload in locked_roles.items():
            if isinstance(payload, dict):
                role = dict(payload)
            else:
                role = {"role": payload}
            role["player_name"] = name
            role.setdefault("locked_role", role.get("role") or "core_player")
            roles[str(name)] = role

    core_players = context.get("core_players") or []
    if isinstance(core_players, list):
        for item in core_players:
            if isinstance(item, dict):
                name = item.get("player_name")
                if name:
                    role = dict(item)
                    role.setdefault("locked_role", role.get("role") or "core_player")
                    roles.setdefault(str(name), role)
            elif item:
                name = str(item)
                roles.setdefault(
                    name,
                    {"player_name": name, "locked_role": "core_player"},
                )
    return roles


def _open_slots(context: dict[str, Any]) -> list[str]:
    slots = context.get("open_roster_slots") or context.get("open_slots") or []
    return [str(slot) for slot in slots]


def _blocked_slots(context: dict[str, Any]) -> list[str]:
    slots = context.get("blocked_roster_slots") or context.get("blocked_slots") or []
    return [str(slot) for slot in slots]


def _latest_seasons(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "season" not in frame.columns:
        return frame
    season = sorted(frame["season"].dropna().astype(str).unique())[-1]
    return frame[frame["season"].astype(str) == season].copy()


def _optional_parquet(path: str | Path) -> pd.DataFrame | None:
    path = Path(path)
    return pd.read_parquet(path) if path.exists() else None


def _num(value: object) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe(value: object):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
