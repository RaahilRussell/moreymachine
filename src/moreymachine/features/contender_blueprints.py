"""Structural contender blueprint engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import (
    FEATURES_DATA_DIR,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    REPORTS_DATA_DIR,
)

CONTENDER_BLUEPRINTS_PATH = FEATURES_DATA_DIR / "contender_blueprints.parquet"
TEAM_CONSTRUCTION_ARCHETYPES_PATH = (
    FEATURES_DATA_DIR / "team_construction_archetypes.parquet"
)
CONTENDER_BLUEPRINTS_REPORT_PATH = REPORTS_DATA_DIR / "contender_blueprints.md"

BLUEPRINT_ORDER = (
    "champions",
    "finalists",
    "conference_finalists",
    "top_5_net_rating",
    "top_10_net_rating",
    "star_center_anchor",
    "heliocentric_guard",
    "wing_depth_switchable",
    "balanced_two_way",
    "defense_first",
    "shooting_pressure",
    "depth_heavy",
    "dual_big",
    "creator_committee",
)


@dataclass(frozen=True)
class ContenderBlueprintResult:
    """Summary from a contender-blueprint build."""

    blueprints: int
    team_archetypes: int
    blueprint_path: Path
    archetype_path: Path
    report_path: Path


def build_contender_blueprints(
    *,
    team_fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    blueprint_path: str | Path = CONTENDER_BLUEPRINTS_PATH,
    archetype_path: str | Path = TEAM_CONSTRUCTION_ARCHETYPES_PATH,
    report_path: str | Path = CONTENDER_BLUEPRINTS_REPORT_PATH,
) -> ContenderBlueprintResult:
    """Build structural contender blueprints and team archetypes."""
    teams = pd.read_parquet(team_fingerprints_path)
    players = pd.read_parquet(player_seasons_path)
    bio = _optional_parquet(player_bio_path)
    team_structure = _team_structure(players, bio)
    enriched = teams.merge(team_structure, on=["season", "team_abbr"], how="left")
    enriched = _fill_structure_defaults(enriched)
    archetypes = _team_archetypes(enriched)
    blueprints = _blueprints(enriched)

    blueprint_output = Path(blueprint_path)
    archetype_output = Path(archetype_path)
    report_output = Path(report_path)
    for path in (blueprint_output, archetype_output, report_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    blueprints.to_parquet(blueprint_output, index=False)
    archetypes.to_parquet(archetype_output, index=False)
    report_output.write_text(_render_report(blueprints))

    run_id = new_run_id()
    for path in (blueprint_output, archetype_output, report_output):
        write_metadata_for_artifact(
            path,
            run_id=run_id,
            source_files=(team_fingerprints_path, player_seasons_path, player_bio_path),
            upstream_artifacts=(
                team_fingerprints_path,
                player_seasons_path,
                player_bio_path,
            ),
            known_limitations=(
                "Blueprints are structural public-data proxies, not scouting truth.",
                "Historical position roles use current static bio positions when "
                "player-season position is missing.",
                "Lineup-level and possession-level context is not fully sourced.",
            ),
        )

    return ContenderBlueprintResult(
        blueprints=len(blueprints),
        team_archetypes=len(archetypes),
        blueprint_path=blueprint_output,
        archetype_path=archetype_output,
        report_path=report_output,
    )


def _optional_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _team_structure(
    players: pd.DataFrame, bio: pd.DataFrame | None = None
) -> pd.DataFrame:
    frame = players.copy()
    bio_has_positions = (
        bio is not None
        and not bio.empty
        and {"player_id", "position"}.issubset(bio.columns)
    )
    if bio_has_positions:
        bio_positions = (
            bio[["player_id", "position"]]
            .dropna(subset=["player_id"])
            .drop_duplicates("player_id")
            .rename(columns={"position": "bio_position"})
        )
        frame = frame.merge(bio_positions, on="player_id", how="left")
        frame["position"] = frame["position"].fillna(frame["bio_position"])
        frame = frame.drop(columns=["bio_position"])
    frame["minutes"] = pd.to_numeric(frame["minutes"], errors="coerce").fillna(0)
    frame["usage_rate"] = pd.to_numeric(frame["usage_rate"], errors="coerce").fillna(0)
    frame["three_pa"] = pd.to_numeric(frame["three_pa"], errors="coerce").fillna(0)
    frame["three_pa_rate"] = pd.to_numeric(
        frame["three_pa_rate"], errors="coerce"
    ).fillna(0)
    frame["assist_pct"] = pd.to_numeric(frame["assist_pct"], errors="coerce").fillna(0)
    frame["rebound_pct"] = pd.to_numeric(
        frame["rebound_pct"], errors="coerce"
    ).fillna(0)

    records = []
    for (season, team), group in frame.groupby(["season", "team_abbr"], dropna=False):
        rotation = group[group["minutes"] >= 700].copy()
        usage_weight = group["usage_rate"] * group["minutes"]
        total_usage = float(usage_weight.sum()) or 1.0
        usage_shares = (usage_weight / total_usage).sort_values(ascending=False)
        wings = rotation[
            rotation["position"].fillna("").str.contains("F|G-F|F-G", regex=True)
        ]
        bigs = rotation[rotation["position"].fillna("").str.contains("C")]
        shooters = rotation[
            (rotation["three_pa"] >= 150)
            | ((rotation["three_pa_rate"] >= 0.35) & (rotation["minutes"] >= 900))
        ]
        bench = group.sort_values("minutes", ascending=False).iloc[5:]
        records.append(
            {
                "season": season,
                "team_abbr": team,
                "top_1_usage_share": _usage_share(usage_shares, 0),
                "top_2_usage_share": _usage_share(usage_shares, 1),
                "top_3_usage_share": _usage_share(usage_shares, 2),
                "number_of_rotation_shooters": int(len(shooters)),
                "number_of_playable_wings": int(len(wings)),
                "number_of_big_minutes_players": int(len(bigs)),
                "backup_center_quality_proxy": _backup_center_proxy(bigs),
                "bench_creation_proxy": float(
                    bench["assist_pct"].head(6).mean() if not bench.empty else 0
                ),
                "role_player_spacing_proxy": float(
                    shooters["three_pa_rate"].mean() if not shooters.empty else 0
                ),
                "depth_balance_proxy": float(len(rotation)),
                "star_dependency_proxy": float(usage_shares.head(2).sum()),
                "lineup_versatility_proxy": float(len(wings) + len(shooters)),
            }
        )
    return pd.DataFrame(records)


def _fill_structure_defaults(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in (
        "top_1_usage_share",
        "top_2_usage_share",
        "top_3_usage_share",
        "number_of_rotation_shooters",
        "number_of_playable_wings",
        "number_of_big_minutes_players",
        "backup_center_quality_proxy",
        "bench_creation_proxy",
        "role_player_spacing_proxy",
        "depth_balance_proxy",
        "star_dependency_proxy",
        "lineup_versatility_proxy",
    ):
        if column not in out.columns:
            out[column] = 0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0)
    out["defensive_rebounding_proxy"] = out.get(
        "defensive_rebounding_percentage", pd.Series(0, index=out.index)
    )
    out["turnover_control_proxy"] = 1 - out.get(
        "turnover_percentage", pd.Series(0, index=out.index)
    )
    out["playoff_portability_proxy"] = out.get(
        "estimated_two_way_balance", pd.Series(0, index=out.index)
    )
    return out


def _team_archetypes(enriched: pd.DataFrame) -> pd.DataFrame:
    records = []
    now = datetime.now(UTC).date().isoformat()
    for row in enriched.to_dict(orient="records"):
        archetype = _classify_team(row)
        records.append(
            {
                "team_abbr": row["team_abbr"],
                "season": row["season"],
                "team_construction_archetype": archetype,
                "blueprint_id": archetype,
                "net_rating": row.get("net_rating"),
                "off_rating": row.get("offensive_rating"),
                "def_rating": row.get("defensive_rating"),
                "source": "team_fingerprints + player_seasons",
                "pulled_at": now,
                "data_mode": "derived",
                "missing_data_flags": "none",
            }
        )
    return pd.DataFrame(records)


def _blueprints(enriched: pd.DataFrame) -> pd.DataFrame:
    phi = _latest_phi(enriched)
    now = datetime.now(UTC).date().isoformat()
    records = []
    for cohort in BLUEPRINT_ORDER:
        subset = _cohort_subset(enriched, cohort)
        if subset.empty:
            continue
        metrics = _metric_means(subset)
        phi_distance = _phi_distance(phi, metrics)
        records.append(
            {
                "blueprint_id": cohort,
                "blueprint_name": _pretty(cohort),
                "cohort": cohort,
                **metrics,
                "required_roles": json.dumps(_required_roles(cohort)),
                "redundant_roles": json.dumps(_redundant_roles(cohort)),
                "failure_modes": json.dumps(_failure_modes(cohort)),
                "phi_distance": round(phi_distance, 3),
                "what_moves_phi_closer": "; ".join(_moves_phi_closer(cohort)),
                "what_this_team_type_usually_has": _usually_has(cohort),
                "what_weaknesses_show_up": "; ".join(_failure_modes(cohort)),
                "source": "team_fingerprints + player_seasons structural proxies",
                "pulled_at": now,
                "data_mode": "derived",
                "missing_data_flags": "none",
            }
        )
    return pd.DataFrame(records)


def _cohort_subset(frame: pd.DataFrame, cohort: str) -> pd.DataFrame:
    if cohort == "champions":
        return frame[frame["champion"] == True]  # noqa: E712
    if cohort == "finalists":
        return frame[frame["finals_team"] == True]  # noqa: E712
    if cohort == "conference_finalists":
        return frame[pd.to_numeric(frame["playoff_tier"], errors="coerce") >= 3]
    if cohort == "top_5_net_rating":
        return _top_n_by_season(frame, 5)
    if cohort == "top_10_net_rating":
        return _top_n_by_season(frame, 10)
    archetype = frame.apply(_classify_team, axis=1)
    subset = frame[archetype == cohort]
    if not subset.empty:
        return subset
    return _proxy_cohort_subset(frame, cohort)


def _proxy_cohort_subset(frame: pd.DataFrame, cohort: str) -> pd.DataFrame:
    proxy_columns = {
        "star_center_anchor": "defensive_rebounding_proxy",
        "heliocentric_guard": "top_1_usage_share",
        "wing_depth_switchable": "lineup_versatility_proxy",
        "balanced_two_way": "playoff_portability_proxy",
        "defense_first": "defensive_rating",
        "shooting_pressure": "estimated_shooting_pressure",
        "depth_heavy": "depth_balance_proxy",
        "dual_big": "offensive_rebounding_percentage",
        "creator_committee": "bench_creation_proxy",
    }
    column = proxy_columns.get(cohort)
    if column is None or column not in frame.columns:
        return frame.head(0)
    higher_is_better = column != "defensive_rating"
    return (
        frame.sort_values(["season", column], ascending=[True, not higher_is_better])
        .groupby("season", group_keys=False)
        .head(6)
    )


def _top_n_by_season(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return (
        frame.sort_values(["season", "net_rating"], ascending=[True, False])
        .groupby("season", group_keys=False)
        .head(n)
    )


def _metric_means(frame: pd.DataFrame) -> dict[str, float]:
    mapping = {
        "off_rating": "offensive_rating",
        "def_rating": "defensive_rating",
        "net_rating": "net_rating",
        "pace": "pace",
        "three_pa_rate": "three_point_attempt_rate",
        "three_p_pct": "three_point_percentage",
        "efg_pct": "efg_percentage",
        "tov_pct": "turnover_percentage",
        "oreb_pct": "offensive_rebounding_percentage",
        "dreb_pct": "defensive_rebounding_percentage",
        "fta_rate": "free_throw_rate",
        "top_1_usage_share": "top_1_usage_share",
        "top_2_usage_share": "top_2_usage_share",
        "top_3_usage_share": "top_3_usage_share",
        "number_of_rotation_shooters": "number_of_rotation_shooters",
        "number_of_playable_wings": "number_of_playable_wings",
        "number_of_big_minutes_players": "number_of_big_minutes_players",
        "backup_center_quality_proxy": "backup_center_quality_proxy",
        "bench_creation_proxy": "bench_creation_proxy",
        "defensive_rebounding_proxy": "defensive_rebounding_proxy",
        "turnover_control_proxy": "turnover_control_proxy",
        "role_player_spacing_proxy": "role_player_spacing_proxy",
        "star_dependency_proxy": "star_dependency_proxy",
        "depth_balance_proxy": "depth_balance_proxy",
        "lineup_versatility_proxy": "lineup_versatility_proxy",
        "playoff_portability_proxy": "playoff_portability_proxy",
    }
    return {
        out: round(float(pd.to_numeric(frame[col], errors="coerce").mean()), 3)
        for out, col in mapping.items()
        if col in frame.columns
    }


def _classify_team(row) -> str:
    if row.get("number_of_big_minutes_players", 0) >= 2.5:
        return "dual_big"
    if row.get("top_1_usage_share", 0) >= 0.34:
        return "heliocentric_guard"
    if row.get("number_of_playable_wings", 0) >= 4:
        return "wing_depth_switchable"
    if row.get("defensive_rating", 120) <= 110:
        return "defense_first"
    if row.get("estimated_shooting_pressure", 0) >= 0.7:
        return "shooting_pressure"
    if row.get("depth_balance_proxy", 0) >= 9:
        return "depth_heavy"
    if row.get("bench_creation_proxy", 0) >= 0.18:
        return "creator_committee"
    if row.get("playoff_portability_proxy", 0) >= 0.7:
        return "balanced_two_way"
    return "star_center_anchor"


def _latest_phi(frame: pd.DataFrame) -> pd.Series:
    phi = frame[frame["team_abbr"] == "PHI"].copy()
    if phi.empty:
        return pd.Series(dtype="object")
    season = sorted(phi["season"].astype(str).unique())[-1]
    return phi[phi["season"].astype(str) == season].iloc[0]


def _phi_distance(phi: pd.Series, metrics: dict[str, float]) -> float:
    if phi.empty:
        return 0.0
    pairs = (
        ("net_rating", "net_rating"),
        ("three_pa_rate", "three_point_attempt_rate"),
        ("tov_pct", "turnover_percentage"),
        ("dreb_pct", "defensive_rebounding_percentage"),
        ("role_player_spacing_proxy", "role_player_spacing_proxy"),
        ("lineup_versatility_proxy", "lineup_versatility_proxy"),
    )
    diffs = []
    for metric, phi_col in pairs:
        if metric in metrics and phi_col in phi:
            diffs.append(abs(float(metrics[metric]) - float(phi[phi_col])))
    return sum(diffs) / (len(diffs) or 1)


def _required_roles(cohort: str) -> list[str]:
    base = ["playoff rotation wings", "low-mistake role players"]
    extra = {
        "star_center_anchor": ["non-Embiid center minutes", "shooting around center"],
        "heliocentric_guard": ["defensive cover", "low-usage spacers"],
        "wing_depth_switchable": ["multiple playable wings", "switchable forwards"],
        "balanced_two_way": ["two-way rotation depth", "turnover control"],
        "defense_first": ["rim protection", "point-of-attack defense"],
        "shooting_pressure": ["movement shooting", "role-player shooting volume"],
        "depth_heavy": ["bench creation", "regular-season depth"],
        "dual_big": ["spacing big or mobile big", "defensive rebounding"],
        "creator_committee": ["secondary creators", "connector passing"],
    }
    return base + extra.get(cohort, [])


def _redundant_roles(cohort: str) -> list[str]:
    if cohort in {"heliocentric_guard", "star_center_anchor"}:
        return ["extra high-usage players without defense or spacing"]
    if cohort == "dual_big":
        return ["non-shooting extra bigs next to a center anchor"]
    return ["single-skill depth without playoff pathway"]


def _failure_modes(cohort: str) -> list[str]:
    mapping = {
        "shooting_pressure": ["shooting cools off", "defense gets hunted"],
        "defense_first": ["half-court offense stalls", "spacing is cramped"],
        "dual_big": ["spacing collapses", "mobility gets attacked"],
        "heliocentric_guard": ["usage overload", "late-clock predictability"],
        "star_center_anchor": ["non-star minutes collapse", "backup center gap"],
    }
    return mapping.get(cohort, ["bench units collapse", "role players get targeted"])


def _moves_phi_closer(cohort: str) -> list[str]:
    roles = _required_roles(cohort)
    return [f"add {role}" for role in roles[:4]]


def _usually_has(cohort: str) -> str:
    roles = ", ".join(_required_roles(cohort)[:4])
    return f"{_pretty(cohort)} teams usually require {roles}."


def _render_report(blueprints: pd.DataFrame) -> str:
    lines = [
        "# Contender Blueprints",
        "",
        "Structural cohorts built from team fingerprints and player-season proxies.",
        "",
        "| Blueprint | PHI distance | Usually has | Moves PHI closer |",
        "| --- | ---: | --- | --- |",
    ]
    for row in blueprints.to_dict(orient="records"):
        lines.append(
            f"| {row['blueprint_name']} | {row['phi_distance']} | "
            f"{row['what_this_team_type_usually_has']} | "
            f"{row['what_moves_phi_closer']} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Cohorts use public team and player-season proxies.",
            "- Historical player-season positions are filled from current NBA.com bio "
            "positions when missing, so role counts are useful proxies rather than "
            "exact historical lineup classifications.",
            "- Lineup/on-off and possession-level context are not fully sourced.",
            "- Blueprint distance is descriptive, not a prediction of playoff success.",
        ]
    )
    return "\n".join(lines)


def _usage_share(values: pd.Series, idx: int) -> float:
    if len(values) <= idx:
        return 0.0
    return round(float(values.iloc[idx]), 3)


def _backup_center_proxy(bigs: pd.DataFrame) -> float:
    if bigs.empty or len(bigs) < 2:
        return 0.0
    ranked = bigs.sort_values("minutes", ascending=False).iloc[1:]
    weighted_rebound = (ranked["rebound_pct"] * ranked["minutes"]).sum()
    return float(weighted_rebound / ranked["minutes"].sum())


def _pretty(value: str) -> str:
    return value.replace("_", " ").title()
