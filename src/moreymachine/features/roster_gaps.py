"""Roster gap analysis against successful team-season baselines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from moreymachine.features.roster_archetypes import TEAM_ROSTER_ARCHETYPES_PATH
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

DEFAULT_TARGET_TEAM = "PHI"
ROSTER_GAPS_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.parquet"
ROSTER_GAPS_MARKDOWN_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.md"

COMPARISON_GROUP_LABELS = {
    "conference_finals_or_better": "Conference Finals or Better",
    "same_roster_archetype_successful": "Same Archetype Successful Teams",
    "top_5_net_rating": "Top-5 Net Rating Teams",
}


@dataclass(frozen=True)
class GapCategory:
    """Definition for one roster gap signal."""

    key: str
    label: str
    primary_aliases: tuple[str, ...]
    fallback_aliases: tuple[tuple[str, ...], ...]
    higher_is_better: bool
    context: str


@dataclass(frozen=True)
class RosterGapBuildResult:
    """Summary of a completed roster gap report build."""

    rows: int
    target_team: str
    target_season: str
    output_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class CategoryValues:
    """Resolved metric values for a gap category."""

    values: pd.Series
    source_columns: tuple[str, ...]


GAP_CATEGORIES = (
    GapCategory(
        key="shooting_pressure",
        label="Shooting Pressure",
        primary_aliases=("estimated_shooting_pressure",),
        fallback_aliases=(
            ("efg_percentage", "effective_fg_pct", "efg_pct"),
            ("three_point_attempt_rate", "three_point_rate", "fg3a_rate"),
            ("three_point_percentage", "three_point_pct", "fg3_pct"),
            ("free_throw_rate", "ft_rate", "ftr"),
        ),
        higher_is_better=True,
        context="spacing, efficiency, three-point volume, and rim-pressure signals",
    ),
    GapCategory(
        key="role_player_shooting",
        label="Role-Player Shooting",
        primary_aliases=(
            "role_player_shooting",
            "role_player_three_point_percentage",
            "bench_three_point_percentage",
            "low_usage_three_point_percentage",
        ),
        fallback_aliases=(
            ("three_point_percentage", "three_point_pct", "fg3_pct"),
            ("three_point_attempt_rate", "three_point_rate", "fg3a_rate"),
        ),
        higher_is_better=True,
        context="role-player shooting when available, with team shooting as fallback",
    ),
    GapCategory(
        key="defense",
        label="Defense",
        primary_aliases=("defensive_rating", "def_rating", "def_rtg", "drtg"),
        fallback_aliases=(),
        higher_is_better=False,
        context="points allowed per 100 possessions",
    ),
    GapCategory(
        key="rebounding",
        label="Rebounding",
        primary_aliases=(),
        fallback_aliases=(
            (
                "offensive_rebounding_percentage",
                "offensive_rebound_pct",
                "oreb_pct",
            ),
            (
                "defensive_rebounding_percentage",
                "defensive_rebound_pct",
                "dreb_pct",
            ),
        ),
        higher_is_better=True,
        context="combined offensive and defensive rebounding strength",
    ),
    GapCategory(
        key="turnover_control",
        label="Turnover Control",
        primary_aliases=(
            "turnover_percentage",
            "turnover_rate",
            "tov_pct",
        ),
        fallback_aliases=(),
        higher_is_better=False,
        context="turnover avoidance",
    ),
    GapCategory(
        key="pace_transition",
        label="Pace/Transition",
        primary_aliases=("pace", "pace_per_48", "transition_rate"),
        fallback_aliases=(),
        higher_is_better=True,
        context="pace as a transition pressure proxy",
    ),
    GapCategory(
        key="bench_rotation_depth",
        label="Bench/Rotation Depth",
        primary_aliases=(
            "bench_rotation_depth",
            "rotation_depth",
            "rotation_player_count",
            "bench_minutes_share",
            "bench_net_rating",
        ),
        fallback_aliases=(),
        higher_is_better=True,
        context="bench or rotation depth proxies when present",
    ),
    GapCategory(
        key="usage_concentration",
        label="Usage Concentration",
        primary_aliases=(
            "top_usage_concentration",
            "usage_concentration",
            "top_usage_pct",
            "top_usage_concentration_zscore",
        ),
        fallback_aliases=(),
        higher_is_better=False,
        context="how concentrated the offense is among top creators",
    ),
    GapCategory(
        key="playoff_portability_proxy",
        label="Playoff Portability Proxy",
        primary_aliases=("estimated_two_way_balance",),
        fallback_aliases=(
            ("net_rating", "net_rtg"),
            ("estimated_shooting_pressure",),
            ("estimated_possession_control",),
        ),
        higher_is_better=True,
        context="two-way balance and possession resilience",
    ),
)


# Why each gap matters in a playoff series.
PLAYOFF_IMPORTANCE: dict[str, str] = {
    "shooting_pressure": (
        "Playoff defenses load up on stars; without floor-spacing pressure the "
        "paint clogs and star efficiency collapses."
    ),
    "role_player_shooting": (
        "Role-player shooting is the first thing playoff scouting tests; "
        "non-shooters get ignored and turn the floor 4-on-5."
    ),
    "defense": (
        "Series are won on stops in the half court; a weak defense gets hunted "
        "in late-game possessions."
    ),
    "rebounding": (
        "Second-chance points swing tight playoff games and compound over a "
        "seven-game series."
    ),
    "turnover_control": (
        "Half-court playoff offense magnifies turnovers into transition points "
        "against."
    ),
    "pace_transition": (
        "Easy transition points are scarce in the playoffs; teams that cannot "
        "generate them must grind in the half court."
    ),
    "bench_rotation_depth": (
        "Playoff rotations shorten, but injuries and foul trouble still demand "
        "a trustworthy 8th-9th man."
    ),
    "usage_concentration": (
        "Over-concentrated offense is easy to scheme against; defenses blitz the "
        "lone creator when no one else can punish it."
    ),
    "playoff_portability_proxy": (
        "Two-way, low-variance contributors hold up when series tighten and "
        "matchups get targeted."
    ),
}

# What kind of player most directly closes each gap.
FIX_TYPE: dict[str, str] = {
    "shooting_pressure": "a high-volume movement/catch-and-shoot shooter",
    "role_player_shooting": "a low-usage 3-and-D wing who spaces the floor",
    "defense": "a switchable wing stopper or rim-protecting anchor",
    "rebounding": "a rebounding big or crash-the-glass forward",
    "turnover_control": "a secure connector guard with a low turnover profile",
    "pace_transition": "an athletic transition finisher and outlet runner",
    "bench_rotation_depth": "a reliable two-way rotation veteran",
    "usage_concentration": "a secondary shot-creator who can run offense off the bench",
    "playoff_portability_proxy": "a low-usage, two-way role player who fits any lineup",
}


def build_roster_gaps(
    *,
    input_path: str | Path = TEAM_FINGERPRINTS_PATH,
    roster_archetypes_path: str | Path | None = TEAM_ROSTER_ARCHETYPES_PATH,
    output_path: str | Path = ROSTER_GAPS_PATH,
    markdown_path: str | Path = ROSTER_GAPS_MARKDOWN_PATH,
    target_team: str = DEFAULT_TARGET_TEAM,
    target_season: str | None = None,
) -> RosterGapBuildResult:
    """Build and save the roster gap report for a target team."""
    fingerprints = pd.read_parquet(input_path)
    roster_archetypes = _read_optional_roster_archetypes(roster_archetypes_path)
    gaps = create_roster_gap_report(
        fingerprints,
        roster_archetypes=roster_archetypes,
        target_team=target_team,
        target_season=target_season,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    gaps.to_parquet(output, index=False)

    markdown_output = Path(markdown_path)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_roster_gap_markdown(gaps), encoding="utf-8")

    return RosterGapBuildResult(
        rows=len(gaps),
        target_team=str(gaps["target_team"].iloc[0]),
        target_season=str(gaps["target_season"].iloc[0]),
        output_path=output,
        markdown_path=markdown_output,
    )


def create_roster_gap_report(
    team_fingerprints: pd.DataFrame,
    *,
    roster_archetypes: pd.DataFrame | None = None,
    target_team: str = DEFAULT_TARGET_TEAM,
    target_season: str | None = None,
) -> pd.DataFrame:
    """Compare one target team-season against contender baseline groups."""
    frame = _merge_roster_archetypes(team_fingerprints, roster_archetypes)
    _validate_input_frame(frame)
    frame = frame.reset_index(drop=True)

    target = _target_row(frame, target_team=target_team, target_season=target_season)
    category_values = {
        category.key: _category_values(frame, category) for category in GAP_CATEGORIES
    }
    comparison_groups = _comparison_groups(frame, target)

    rows = []
    for group_key, group_frame in comparison_groups.items():
        for category in GAP_CATEGORIES:
            values = category_values[category.key]
            rows.append(
                _gap_row(
                    frame=frame,
                    target=target,
                    group_key=group_key,
                    group_frame=group_frame,
                    category=category,
                    values=values,
                )
            )

    return pd.DataFrame(rows).sort_values(
        ["comparison_group", "severity_score", "category"],
        ascending=[True, False, True],
        na_position="last",
    )


def render_roster_gap_markdown(gaps: pd.DataFrame) -> str:
    """Render a readable Markdown roster gap report."""
    if gaps.empty:
        return "# Roster Gap Report\n\nNo roster gaps were generated.\n"

    target_team = str(gaps["target_team"].iloc[0])
    target_season = str(gaps["target_season"].iloc[0])
    lines = [
        f"# {target_team} Roster Gap Report",
        "",
        f"Target season: {target_season}",
        "",
        (
            "Positive gap sizes indicate the target trails the comparison group. "
            "Severity is scaled from the size of the gap relative to historical "
            "team-season variation."
        ),
        "",
    ]

    for group_key, group_gaps in gaps.groupby("comparison_group", sort=False):
        lines.extend(
            [
                f"## {COMPARISON_GROUP_LABELS.get(group_key, group_key)}",
                "",
                (
                    "| Category | Target | Elite Avg | Percentile | Gap | "
                    "Severity | Explanation |"
                ),
                "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        ordered = group_gaps.sort_values(
            ["severity_score", "category"],
            ascending=[False, True],
            na_position="last",
        )
        for row in ordered.itertuples(index=False):
            lines.append(
                "| "
                f"{row.category} | "
                f"{_format_value(row.target_value)} | "
                f"{_format_value(row.elite_average)} | "
                f"{_format_percentile(row.percentile)} | "
                f"{_format_value(row.gap_size)} | "
                f"{_format_value(row.severity_score)} | "
                f"{row.explanation} |"
            )
        lines.append("")
        lines.append("**Top gaps in detail**")
        lines.append("")
        for row in ordered.head(4).itertuples(index=False):
            importance = getattr(row, "playoff_importance", "")
            fix_type = getattr(row, "fix_type", "")
            lines.append(
                f"- **{row.category}** (severity "
                f"{_format_value(row.severity_score)}, "
                f"{_format_percentile(row.percentile)} pct): {row.explanation}"
            )
            if importance:
                lines.append(f"  - *Why it matters in the playoffs:* {importance}")
            if fix_type:
                lines.append(f"  - *What fixes it:* {fix_type}.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _read_optional_roster_archetypes(path: str | Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    archetype_path = Path(path)
    if not archetype_path.exists():
        return None
    return pd.read_parquet(archetype_path)


def _validate_input_frame(frame: pd.DataFrame) -> None:
    missing = [column for column in ("season", "team_abbr") if column not in frame]
    if missing:
        raise ValueError(f"Team fingerprints are missing required columns: {missing}")


def _merge_roster_archetypes(
    team_fingerprints: pd.DataFrame,
    roster_archetypes: pd.DataFrame | None,
) -> pd.DataFrame:
    frame = team_fingerprints.copy()
    if roster_archetypes is None or roster_archetypes.empty:
        return frame
    if not {"season", "team_abbr"}.issubset(roster_archetypes.columns):
        return frame

    merge_columns = ["season", "team_abbr"]
    archetype_columns = [
        column
        for column in roster_archetypes.columns
        if column in {"cluster_id", "cluster_name"} or column.endswith("_zscore")
    ]
    merge_columns.extend(column for column in archetype_columns if column not in frame)
    if len(merge_columns) == 2:
        return frame

    archetypes = roster_archetypes.loc[:, merge_columns].drop_duplicates(
        subset=["season", "team_abbr"]
    )
    return frame.merge(archetypes, on=["season", "team_abbr"], how="left")


def _target_row(
    frame: pd.DataFrame,
    *,
    target_team: str,
    target_season: str | None,
) -> pd.Series:
    team_mask = frame["team_abbr"].astype(str).str.upper().eq(target_team.upper())
    if target_season is not None:
        team_mask &= frame["season"].astype(str).eq(str(target_season))
    candidates = frame.loc[team_mask].copy()
    if candidates.empty:
        season_text = f" in season {target_season}" if target_season else ""
        raise ValueError(
            f"No team fingerprint row found for {target_team}{season_text}"
        )

    if target_season is None:
        candidates = candidates.assign(
            _season_sort=candidates["season"].map(_season_sort_key)
        ).sort_values(["_season_sort", "season"])
    return candidates.iloc[-1].drop(labels=["_season_sort"], errors="ignore")


def _comparison_groups(
    frame: pd.DataFrame,
    target: pd.Series,
) -> dict[str, pd.DataFrame]:
    not_target = frame.index != int(target.name)
    successful = _successful_mask(frame) & not_target
    groups = {
        "conference_finals_or_better": frame.loc[successful],
        "same_roster_archetype_successful": _same_archetype_successful_group(
            frame,
            target,
            successful,
        ),
        "top_5_net_rating": frame.loc[_top_net_rating_mask(frame) & not_target],
    }
    return groups


def _same_archetype_successful_group(
    frame: pd.DataFrame,
    target: pd.Series,
    successful: pd.Series,
) -> pd.DataFrame:
    if "cluster_id" not in frame.columns or pd.isna(target.get("cluster_id")):
        return frame.iloc[0:0]
    return frame.loc[successful & frame["cluster_id"].eq(target["cluster_id"])]


def _successful_mask(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if "deep_playoff" in frame.columns:
        mask |= frame["deep_playoff"].fillna(False).astype(bool)
    if "playoff_tier" in frame.columns:
        playoff_tier = pd.to_numeric(frame["playoff_tier"], errors="coerce")
        mask |= playoff_tier.ge(3)
    return mask


def _top_net_rating_mask(frame: pd.DataFrame, top_n: int = 5) -> pd.Series:
    net_rating_column = _first_available_column(frame, ("net_rating", "net_rtg"))
    if net_rating_column is None:
        return pd.Series(False, index=frame.index)

    net_rating = pd.to_numeric(frame[net_rating_column], errors="coerce")
    ranks = net_rating.groupby(frame["season"]).rank(
        method="first",
        ascending=False,
    )
    return ranks.le(top_n).fillna(False)


def _category_values(frame: pd.DataFrame, category: GapCategory) -> CategoryValues:
    primary_column = _first_available_column(frame, category.primary_aliases)
    if primary_column is not None:
        values = pd.to_numeric(frame[primary_column], errors="coerce")
        if values.notna().any():
            return CategoryValues(values=values, source_columns=(primary_column,))

    component_columns = []
    for aliases in category.fallback_aliases:
        column = _first_available_column(frame, aliases)
        if column is None:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().any():
            component_columns.append(column)

    if not component_columns:
        empty = pd.Series(np.nan, index=frame.index, dtype="float64")
        return CategoryValues(values=empty, source_columns=())

    components = frame.loc[:, component_columns].apply(pd.to_numeric, errors="coerce")
    values = components.mean(axis=1, skipna=True)
    return CategoryValues(values=values, source_columns=tuple(component_columns))


def _gap_row(
    *,
    frame: pd.DataFrame,
    target: pd.Series,
    group_key: str,
    group_frame: pd.DataFrame,
    category: GapCategory,
    values: CategoryValues,
) -> dict[str, object]:
    target_value = _value_at(values.values, int(target.name))
    comparison_values = values.values.loc[group_frame.index].dropna()
    elite_average = (
        float(comparison_values.mean()) if not comparison_values.empty else np.nan
    )
    gap_size = _gap_size(
        target_value=target_value,
        elite_average=elite_average,
        higher_is_better=category.higher_is_better,
    )
    percentile = _target_percentile(
        frame=frame,
        target=target,
        values=values.values,
        higher_is_better=category.higher_is_better,
    )
    severity_score = _severity_score(values.values, gap_size)

    return {
        "target_team": str(target["team_abbr"]),
        "target_season": str(target["season"]),
        "comparison_group": group_key,
        "comparison_group_label": COMPARISON_GROUP_LABELS.get(group_key, group_key),
        "comparison_count": int(len(group_frame)),
        "category_key": category.key,
        "category": category.label,
        "source_columns": ", ".join(values.source_columns),
        "higher_is_better": category.higher_is_better,
        "target_value": target_value,
        "elite_average": elite_average,
        "percentile": percentile,
        "gap_size": gap_size,
        "severity_score": severity_score,
        "explanation": _explanation(
            category=category,
            group_key=group_key,
            target_value=target_value,
            elite_average=elite_average,
            percentile=percentile,
            gap_size=gap_size,
            comparison_count=len(group_frame),
            source_columns=values.source_columns,
        ),
        "playoff_importance": PLAYOFF_IMPORTANCE.get(category.key, ""),
        "fix_type": FIX_TYPE.get(category.key, ""),
    }


def _value_at(values: pd.Series, index: int) -> float:
    value = values.loc[index]
    return float(value) if pd.notna(value) else np.nan


def _gap_size(
    *,
    target_value: float,
    elite_average: float,
    higher_is_better: bool,
) -> float:
    if pd.isna(target_value) or pd.isna(elite_average):
        return np.nan
    if higher_is_better:
        return float(elite_average - target_value)
    return float(target_value - elite_average)


def _target_percentile(
    *,
    frame: pd.DataFrame,
    target: pd.Series,
    values: pd.Series,
    higher_is_better: bool,
) -> float:
    season_values = values.loc[frame["season"].astype(str).eq(str(target["season"]))]
    season_values = season_values.dropna()
    if season_values.empty or int(target.name) not in season_values.index:
        return np.nan

    ranks = season_values.rank(
        method="average",
        pct=True,
        ascending=higher_is_better,
    )
    return float(ranks.loc[int(target.name)] * 100)


def _severity_score(values: pd.Series, gap_size: float) -> float:
    if pd.isna(gap_size):
        return np.nan
    if gap_size <= 0:
        return 0.0

    spread = float(values.dropna().std(ddof=0))
    if not np.isfinite(spread) or spread <= 0:
        return 100.0
    return float(min(100.0, round((gap_size / spread) * 25, 2)))


def _explanation(
    *,
    category: GapCategory,
    group_key: str,
    target_value: float,
    elite_average: float,
    percentile: float,
    gap_size: float,
    comparison_count: int,
    source_columns: tuple[str, ...],
) -> str:
    group_label = COMPARISON_GROUP_LABELS.get(group_key, group_key)
    if not source_columns:
        return f"No source column was available for {category.label.lower()}."
    if comparison_count == 0 or pd.isna(elite_average):
        return f"No comparison teams were available for {group_label.lower()}."
    if pd.isna(target_value):
        return f"The target team is missing {category.label.lower()} data."

    percentile_text = (
        "unknown percentile"
        if pd.isna(percentile)
        else f"{percentile:.0f}th percentile"
    )
    if pd.isna(gap_size):
        direction = "cannot be compared with"
    elif gap_size > 0:
        direction = "trails"
    elif gap_size < 0:
        direction = "exceeds"
    else:
        direction = "matches"

    return (
        f"{category.label} {direction} {group_label.lower()} by "
        f"{abs(gap_size):.3f}; target is in the {percentile_text} "
        f"using {', '.join(source_columns)} for {category.context}."
    )


def _first_available_column(
    frame: pd.DataFrame,
    aliases: tuple[str, ...],
) -> str | None:
    normalized = {column.lower(): column for column in frame.columns}
    for alias in aliases:
        column = normalized.get(alias.lower())
        if column is not None:
            return column
    return None


def _season_sort_key(value: object) -> int:
    match = re.search(r"\d{4}", str(value))
    if match is None:
        return -1
    return int(match.group(0))


def _format_value(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    numeric_value = float(value)
    if abs(numeric_value) < 1:
        return f"{numeric_value:.3f}"
    return f"{numeric_value:.2f}"


def _format_percentile(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.0f}%"
