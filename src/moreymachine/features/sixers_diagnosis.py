"""Expanded Sixers roster diagnosis: statistical + roster-composition gaps.

The team-level statistical gaps (from ``roster_gaps``) say *how* PHI trails
contenders on aggregate metrics. This module adds *roster-composition* gaps -
computed from PHI's real player-role data - that say *who is missing*: non-Embiid
rim protection, backup-center stability, wing and point-of-attack defense,
shooting depth, connector passing, rebounding, bench creation, playoff-playable
size, and lineup versatility.

Composition values are real (from the role engine). The contender targets are
documented roster-construction heuristics, not invented data, and every row
carries an explicit ``data_sources`` note saying so. Each gap explains what it
means, why it matters in the playoffs, and what kind of player fixes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.features.candidate_universe import PHI_ROSTER_2025_26
from moreymachine.features.roster_archetypes import TEAM_ROSTER_ARCHETYPES_PATH
from moreymachine.features.roster_gaps import ROSTER_GAPS_PATH, build_roster_gaps
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import (
    PLAYER_ROLES_PATH,
    REPORTS_DATA_DIR,
)

ROSTER_GAPS_MARKDOWN_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.md"

DIAGNOSIS_COLUMNS = (
    "target_team",
    "target_season",
    "category_key",
    "gap_name",
    "gap_kind",
    "sixers_value",
    "contender_average",
    "percentile",
    "gap_size",
    "severity_score",
    "gap_tier",
    "what_it_means",
    "why_it_matters_in_playoffs",
    "what_kind_of_player_fixes_it",
    "relevant_stats",
    "data_sources",
)


@dataclass(frozen=True)
class CompositionGap:
    """A roster-composition gap spec evaluated against a contender target."""

    key: str
    name: str
    target: float
    importance: float  # 0-1 playoff importance weight
    what_it_means: str
    why_playoffs: str
    fixer: str
    relevant_stats: str
    value_fn: Callable[[pd.DataFrame], float]


@dataclass(frozen=True)
class DiagnosisResult:
    """Summary of a diagnosis build."""

    rows: int
    target_team: str
    target_season: str
    output_path: Path
    markdown_path: Path


def build_sixers_diagnosis(
    *,
    team: str = "PHI",
    fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    roster_archetypes_path: str | Path = TEAM_ROSTER_ARCHETYPES_PATH,
    player_roles_path: str | Path = PLAYER_ROLES_PATH,
    output_path: str | Path = ROSTER_GAPS_PATH,
    markdown_path: str | Path = ROSTER_GAPS_MARKDOWN_PATH,
) -> DiagnosisResult:
    """Build the combined statistical + composition roster diagnosis."""
    statistical = _statistical_gaps(
        team=team,
        fingerprints_path=fingerprints_path,
        roster_archetypes_path=roster_archetypes_path,
        output_path=output_path,
    )
    season = str(statistical["target_season"].iloc[0]) if not statistical.empty else ""
    roster = _phi_roster_roles(player_roles_path)
    composition = _composition_gaps(roster, team=team, season=season)

    combined = pd.concat([statistical, composition], ignore_index=True)
    combined = (
        combined.loc[:, list(DIAGNOSIS_COLUMNS)]
        .sort_values("severity_score", ascending=False)
        .reset_index(drop=True)
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output, index=False)
    Path(markdown_path).write_text(
        _render_markdown(combined, team, season), encoding="utf-8"
    )
    return DiagnosisResult(
        rows=len(combined),
        target_team=team,
        target_season=season,
        output_path=output,
        markdown_path=Path(markdown_path),
    )


def _statistical_gaps(
    *,
    team: str,
    fingerprints_path: str | Path,
    roster_archetypes_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """Run the team-level gap engine and map it to the rich diagnosis schema."""
    build_roster_gaps(
        input_path=fingerprints_path,
        roster_archetypes_path=roster_archetypes_path,
        output_path=output_path,
        markdown_path=REPORTS_DATA_DIR / "_phi_roster_gaps_stat.md",
        target_team=team,
    )
    gaps = pd.read_parquet(output_path)
    if gaps.empty:
        return pd.DataFrame(columns=DIAGNOSIS_COLUMNS)

    gaps = gaps.assign(
        severity_score=pd.to_numeric(gaps["severity_score"], errors="coerce")
    ).dropna(subset=["severity_score"])
    # One row per category - keep the most severe comparison group.
    idx = gaps.groupby("category_key")["severity_score"].idxmax()
    top = gaps.loc[idx].copy()
    return pd.DataFrame(
        {
            "target_team": top["target_team"],
            "target_season": top["target_season"],
            "category_key": top["category_key"],
            "gap_name": top["category"],
            "gap_kind": "statistical",
            "sixers_value": pd.to_numeric(top["target_value"], errors="coerce").round(
                3
            ),
            "contender_average": pd.to_numeric(
                top["elite_average"], errors="coerce"
            ).round(3),
            "percentile": pd.to_numeric(top["percentile"], errors="coerce").round(1),
            "gap_size": pd.to_numeric(top["gap_size"], errors="coerce").round(3),
            "severity_score": top["severity_score"].round(2),
            "gap_tier": top["severity_score"].map(_gap_tier),
            "what_it_means": top["explanation"],
            "why_it_matters_in_playoffs": top["playoff_importance"],
            "what_kind_of_player_fixes_it": top["fix_type"],
            "relevant_stats": top["source_columns"],
            "data_sources": "team_fingerprints (real nba_api) vs contender baselines",
        }
    ).reset_index(drop=True)


def _phi_roster_roles(player_roles_path: str | Path) -> pd.DataFrame:
    path = Path(player_roles_path)
    if not path.exists():
        return pd.DataFrame()
    roles = pd.read_parquet(path)
    return roles[roles["player_name"].isin(PHI_ROSTER_2025_26)].copy()


def _composition_gaps(roster: pd.DataFrame, *, team: str, season: str) -> pd.DataFrame:
    if roster.empty:
        return pd.DataFrame(columns=DIAGNOSIS_COLUMNS)

    rows = []
    for spec in COMPOSITION_GAPS:
        value = float(spec.value_fn(roster))
        target = spec.target
        gap_ratio = max(0.0, (target - value) / target) if target else 0.0
        severity = round(spec.importance * gap_ratio * 50.0, 2)
        rows.append(
            {
                "target_team": team,
                "target_season": season,
                "category_key": spec.key,
                "gap_name": spec.name,
                "gap_kind": "composition",
                "sixers_value": round(value, 2),
                "contender_average": round(target, 2),
                "percentile": round(min(100.0, 100.0 * value / (2 * target)), 1)
                if target
                else 50.0,
                "gap_size": round(max(0.0, target - value), 2),
                "severity_score": severity,
                "gap_tier": _gap_tier(severity),
                "what_it_means": spec.what_it_means,
                "why_it_matters_in_playoffs": spec.why_playoffs,
                "what_kind_of_player_fixes_it": spec.fixer,
                "relevant_stats": spec.relevant_stats,
                "data_sources": (
                    "PHI roster role engine (real bio+tracking) vs documented "
                    "contender roster-construction targets"
                ),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Composition gap evaluators (operate on the PHI player-roles frame)
# --------------------------------------------------------------------------- #
def _best(roster: pd.DataFrame, column: str, *, exclude: tuple[str, ...] = ()) -> float:
    sub = _rotation(roster, 12)
    sub = sub[~sub["player_name"].isin(exclude)]
    values = pd.to_numeric(sub.get(column), errors="coerce").dropna()
    return float(values.max()) if not values.empty else 0.0


def _nth_best(roster: pd.DataFrame, column: str, n: int) -> float:
    values = (
        pd.to_numeric(_rotation(roster, 12).get(column), errors="coerce")
        .dropna()
        .sort_values(ascending=False)
    )
    return float(values.iloc[n - 1]) if len(values) >= n else 0.0


def _rotation(roster: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """The projected playoff rotation: the top-N by sample reliability (minutes)."""
    return roster.sort_values("sample_reliability", ascending=False).head(top_n)


def _count_at_least(roster: pd.DataFrame, column: str, threshold: float) -> float:
    values = pd.to_numeric(_rotation(roster).get(column), errors="coerce")
    return float((values >= threshold).sum())


def _rotation_mean(roster: pd.DataFrame, column: str, top_n: int = 8) -> float:
    rot = roster.sort_values("sample_reliability", ascending=False).head(top_n)
    values = pd.to_numeric(rot.get(column), errors="coerce").dropna()
    return float(values.mean()) if not values.empty else 0.0


def _archetype_variety(roster: pd.DataFrame) -> float:
    rot = roster.sort_values("sample_reliability", ascending=False).head(9)
    return float(rot["role_archetype"].nunique())


COMPOSITION_GAPS = (
    CompositionGap(
        "non_embiid_rim_protection",
        "Non-Embiid rim protection",
        60.0,
        0.95,
        "The best rim protector on the roster other than Embiid.",
        "Embiid misses playoff games and minutes; without a second rim deterrent "
        "the paint collapses when he sits or is in foul trouble.",
        "a switchable or drop-coverage backup center with real rim protection",
        "rim_protection_proxy (blocks/36, rim FG% defended, height)",
        lambda r: _best(r, "rim_protection_proxy", exclude=("Joel Embiid",)),
    ),
    CompositionGap(
        "backup_center_stability",
        "Backup center stability",
        52.0,
        0.85,
        "The second-best rim-protecting big on the roster.",
        "Playoff rotations need a trustworthy backup five to survive non-Embiid "
        "minutes without bleeding points in the paint.",
        "a reliable backup center who rebounds and protects the rim",
        "rim_protection_proxy (2nd best)",
        lambda r: _nth_best(r, "rim_protection_proxy", 2),
    ),
    CompositionGap(
        "wing_defensive_depth",
        "Wing defensive depth",
        3.0,
        0.9,
        "Count of rotation wings with a plus wing-defense proxy.",
        "Playoff offenses hunt weak perimeter defenders; you need multiple "
        "switchable wing stoppers to throw at opposing scorers.",
        "switchable wing defenders who can guard 2-4",
        "wing_defense_proxy >= 58",
        lambda r: _count_at_least(r, "wing_defense_proxy", 58),
    ),
    CompositionGap(
        "point_of_attack_defense",
        "Point-of-attack defense",
        65.0,
        0.85,
        "The best on-ball perimeter defender on the roster.",
        "Containing the primary ball-handler without help keeps the defense intact; "
        "without it, playoff guards get downhill at will.",
        "a point-of-attack guard who pressures the ball",
        "point_of_attack_defense_proxy",
        lambda r: _best(r, "point_of_attack_defense_proxy"),
    ),
    CompositionGap(
        "role_player_shooting_volume",
        "Role-player shooting volume",
        4.0,
        0.95,
        "Count of rotation players who are real catch-and-shoot threats.",
        "Stars get doubled in the playoffs; you need four floor-spacers around them "
        "or the paint clogs and efficiency collapses.",
        "high-volume catch-and-shoot wings and bigs",
        "catch_and_shoot_score >= 60",
        lambda r: _count_at_least(r, "catch_and_shoot_score", 60),
    ),
    CompositionGap(
        "real_spacing",
        "Real spacing (not fake spacing)",
        55.0,
        0.85,
        "Rotation spacing on real 3-point volume, discounting low-volume shooters.",
        "Defenses ignore non-shooters in the playoffs, turning the floor 4-on-5; real "
        "spacing keeps help defenders honest.",
        "shooters with real 3-point volume, not just a respectable percentage",
        "spacing_score (rotation mean)",
        lambda r: _rotation_mean(r, "spacing_score"),
    ),
    CompositionGap(
        "connector_passing",
        "Low-usage connector passing",
        60.0,
        0.7,
        "The best low-usage connector passer on the roster.",
        "When stars are blitzed, someone has to make the next read; connectors keep "
        "the offense flowing 4-on-3.",
        "a low-usage connector guard or forward who moves the ball",
        "connector_score",
        lambda r: _best(r, "connector_score"),
    ),
    CompositionGap(
        "defensive_rebounding_depth",
        "Defensive rebounding",
        55.0,
        0.75,
        "The best defensive rebounder on the roster.",
        "Closing possessions on the defensive glass denies second-chance points that "
        "swing tight playoff games.",
        "a forward or big who secures the defensive glass",
        "defensive_rebounding_score",
        lambda r: _best(r, "defensive_rebounding_score"),
    ),
    CompositionGap(
        "offensive_rebounding_depth",
        "Offensive rebounding",
        50.0,
        0.6,
        "The best offensive rebounder on the roster.",
        "Extra possessions are scarce against a set playoff defense; crashing the "
        "glass manufactures easy points.",
        "an energy big or forward who crashes the offensive glass",
        "offensive_rebounding_score",
        lambda r: _best(r, "offensive_rebounding_score"),
    ),
    CompositionGap(
        "bench_creation",
        "Bench shot creation",
        55.0,
        0.8,
        "The best secondary shot-creator outside the top two creators.",
        "When the starters rest or a star is contained, bench units need someone who "
        "can generate a good shot.",
        "a secondary creator who can run a bench unit",
        "secondary_creation_score (3rd best)",
        lambda r: _nth_best(r, "secondary_creation_score", 3),
    ),
    CompositionGap(
        "playoff_playable_size",
        "Playoff-playable size",
        79.0,
        0.6,
        "Average height (inches) of the projected playoff rotation.",
        "Playoff series punish small lineups on the glass and at the rim; baseline "
        "size keeps lineups viable.",
        "size on the wing or in the frontcourt without sacrificing skill",
        "height_inches (rotation mean)",
        lambda r: _rotation_mean(r, "height_inches"),
    ),
    CompositionGap(
        "lineup_versatility",
        "Lineup versatility",
        6.0,
        0.7,
        "Number of distinct role archetypes in the projected rotation.",
        "Versatile rosters can counter different playoff matchups; one-note rosters "
        "get schemed out of a series.",
        "multi-positional players who unlock different lineup looks",
        "distinct role_archetype count",
        _archetype_variety,
    ),
)


def _gap_tier(severity: float) -> str:
    if pd.isna(severity):
        return "Unknown"
    if severity >= 35:
        return "Critical"
    if severity >= 20:
        return "Significant"
    if severity >= 10:
        return "Moderate"
    if severity > 0:
        return "Minor"
    return "Strength"


def _render_markdown(frame: pd.DataFrame, team: str, season: str) -> str:
    built = datetime.now(UTC).date().isoformat()
    lines = [
        f"# {team} Roster Diagnosis ({season})",
        "",
        f"_Built {built}. Statistical gaps from real team fingerprints vs "
        "contenders; composition gaps from the real PHI role engine vs documented "
        "contender roster-construction targets._",
        "",
        f"{len(frame)} gaps, ranked by severity.",
        "",
    ]
    for row in frame.itertuples():
        lines.append(
            f"## {row.gap_name} - {row.gap_tier} (severity {row.severity_score:.1f})"
        )
        lines.append(
            f"- PHI: {row.sixers_value} | contender target/avg: "
            f"{row.contender_average} | kind: {row.gap_kind}"
        )
        lines.append(f"- **What it means:** {row.what_it_means}")
        lines.append(
            f"- **Why it matters in the playoffs:** {row.why_it_matters_in_playoffs}"
        )
        lines.append(f"- **What fixes it:** {row.what_kind_of_player_fixes_it}")
        lines.append(f"- Stats: {row.relevant_stats}. Sources: {row.data_sources}.")
        lines.append("")
    return "\n".join(lines)
