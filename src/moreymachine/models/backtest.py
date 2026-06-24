"""Chronological offseason backtesting for MoreyMachine candidate rankings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from moreymachine.features.player_archetypes import (
    PLAYER_ARCHETYPES_PATH,
    PLAYER_SEASONS_BASIC_PATH,
)
from moreymachine.features.roster_archetypes import TEAM_ROSTER_ARCHETYPES_PATH
from moreymachine.features.roster_gaps import create_roster_gap_report
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.models.fit_model import rank_candidates
from moreymachine.utils.paths import REPORTS_DATA_DIR

BACKTEST_RESULTS_PATH = REPORTS_DATA_DIR / "backtest_results.json"
BACKTEST_RANKINGS_PATH = REPORTS_DATA_DIR / "backtest_rankings.parquet"
BACKTEST_SUMMARY_PATH = REPORTS_DATA_DIR / "backtest_summary.md"

BASELINE_SCORE_COLUMNS = {
    "moreymachine_fit": "fit_score",
    "previous_points": "baseline_points_score",
    "previous_impact": "baseline_impact_score",
    "salary": "baseline_salary_score",
    "random": "baseline_random_score",
}


@dataclass(frozen=True)
class BacktestBuildResult:
    """Summary of a completed backtest run."""

    rows: int
    offseasons: tuple[str, ...]
    results_path: Path
    rankings_path: Path
    summary_path: Path


def build_backtest(
    *,
    player_stats_path: str | Path = PLAYER_SEASONS_BASIC_PATH,
    team_fingerprints_path: str | Path = TEAM_FINGERPRINTS_PATH,
    player_archetypes_path: str | Path | None = PLAYER_ARCHETYPES_PATH,
    team_roster_archetypes_path: str | Path | None = TEAM_ROSTER_ARCHETYPES_PATH,
    contracts_path: str | Path | None = None,
    results_path: str | Path = BACKTEST_RESULTS_PATH,
    rankings_path: str | Path = BACKTEST_RANKINGS_PATH,
    summary_path: str | Path = BACKTEST_SUMMARY_PATH,
    target_team: str = "PHI",
    start_season: str | None = None,
    end_season: str | None = None,
    top_k: int = 10,
    random_state: int = 42,
) -> BacktestBuildResult:
    """Run an offseason backtest from files and write reports."""
    player_stats = _read_table(player_stats_path)
    team_fingerprints = _read_table(team_fingerprints_path)
    player_archetypes = _read_optional_table(player_archetypes_path)
    team_archetypes = _read_optional_table(team_roster_archetypes_path)
    contracts = _read_optional_table(contracts_path)

    rankings, metrics = run_backtest(
        player_stats=player_stats,
        team_fingerprints=team_fingerprints,
        player_archetypes=player_archetypes,
        team_roster_archetypes=team_archetypes,
        contracts=contracts,
        target_team=target_team,
        start_season=start_season,
        end_season=end_season,
        top_k=top_k,
        random_state=random_state,
    )

    rankings_output = Path(rankings_path)
    rankings_output.parent.mkdir(parents=True, exist_ok=True)
    rankings.to_parquet(rankings_output, index=False)

    results_output = Path(results_path)
    results_output.parent.mkdir(parents=True, exist_ok=True)
    results_output.write_text(
        json.dumps(_json_safe(metrics), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    summary_output = Path(summary_path)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(render_backtest_summary(metrics), encoding="utf-8")

    offseasons = tuple(sorted(rankings["offseason"].dropna().unique()))
    return BacktestBuildResult(
        rows=len(rankings),
        offseasons=offseasons,
        results_path=results_output,
        rankings_path=rankings_output,
        summary_path=summary_output,
    )


def run_backtest(
    *,
    player_stats: pd.DataFrame,
    team_fingerprints: pd.DataFrame,
    player_archetypes: pd.DataFrame | None = None,
    team_roster_archetypes: pd.DataFrame | None = None,
    contracts: pd.DataFrame | None = None,
    target_team: str = "PHI",
    start_season: str | None = None,
    end_season: str | None = None,
    top_k: int = 10,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run chronological offseason backtests and return rankings plus metrics."""
    rows = []
    for previous_season, next_season in offseason_pairs(
        player_stats,
        start_season=start_season,
        end_season=end_season,
    ):
        offseason_rows = _backtest_offseason(
            previous_season=previous_season,
            next_season=next_season,
            player_stats=player_stats,
            team_fingerprints=team_fingerprints,
            player_archetypes=player_archetypes,
            team_roster_archetypes=team_roster_archetypes,
            contracts=contracts,
            target_team=target_team,
            random_state=random_state,
        )
        if not offseason_rows.empty:
            rows.append(offseason_rows)

    rankings = (
        pd.concat(rows, ignore_index=True)
        if rows
        else pd.DataFrame(columns=_ranking_columns())
    )
    metrics = evaluate_backtest_rankings(
        rankings,
        target_team=target_team,
        top_k=top_k,
    )
    return rankings, metrics


def offseason_pairs(
    player_stats: pd.DataFrame,
    *,
    start_season: str | None = None,
    end_season: str | None = None,
) -> list[tuple[str, str]]:
    """Return consecutive previous/next season pairs for offseason tests."""
    if "season" not in player_stats.columns:
        raise ValueError("player_stats must include a season column")

    seasons = sorted(
        (str(season) for season in player_stats["season"].dropna().unique()),
        key=_season_sort_key,
    )
    pairs = []
    for previous_season, next_season in zip(seasons, seasons[1:], strict=False):
        previous_year = _season_sort_key(previous_season)
        if _season_sort_key(next_season) != previous_year + 1:
            continue
        if start_season and previous_year < _season_sort_key(start_season):
            continue
        if end_season and previous_year > _season_sort_key(end_season):
            continue
        pairs.append((previous_season, next_season))
    return pairs


def evaluate_backtest_rankings(
    rankings: pd.DataFrame,
    *,
    target_team: str = "PHI",
    top_k: int = 10,
) -> dict[str, Any]:
    """Evaluate MoreyMachine rankings against raw-stat baselines."""
    methods = {
        method: column
        for method, column in BASELINE_SCORE_COLUMNS.items()
        if column in rankings.columns
    }
    overall = {
        method: _method_metrics(rankings, score_column=column, top_k=top_k)
        for method, column in methods.items()
    }
    by_offseason = {}
    for offseason, frame in rankings.groupby("offseason"):
        by_offseason[str(offseason)] = {
            method: _method_metrics(frame, score_column=column, top_k=top_k)
            for method, column in methods.items()
        }

    morey_average = overall.get("moreymachine_fit", {}).get("average_value_top_targets")
    baseline_comparison = {}
    for method, metrics in overall.items():
        if method == "moreymachine_fit":
            continue
        baseline_average = metrics.get("average_value_top_targets")
        baseline_comparison[method] = {
            "average_value_top_targets": baseline_average,
            "delta_vs_moreymachine": _nullable_difference(
                morey_average,
                baseline_average,
            ),
        }

    return {
        "target_team": target_team,
        "top_k": top_k,
        "offseasons": (
            sorted(str(value) for value in rankings["offseason"].unique())
            if "offseason" in rankings
            else []
        ),
        "row_count": int(len(rankings)),
        "overall": overall,
        "by_offseason": by_offseason,
        "average_value_of_top_targets_vs_baselines": baseline_comparison,
    }


def render_backtest_summary(metrics: dict[str, Any]) -> str:
    """Render a Markdown summary from backtest metrics."""
    lines = [
        "# Offseason Backtest Summary",
        "",
        f"Target team: {metrics.get('target_team', '')}",
        f"Offseasons tested: {', '.join(metrics.get('offseasons', [])) or 'none'}",
        f"Rows evaluated: {metrics.get('row_count', 0)}",
        "",
        "## Overall Metrics",
        "",
        (
            "| Method | Spearman | Top Quartile Gap | Hit Rate Top K | "
            "Avg Top Target Value |"
        ),
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for method, values in metrics.get("overall", {}).items():
        lines.append(
            "| "
            f"{method} | "
            f"{_format_metric(values.get('spearman_correlation'))} | "
            f"{_format_metric(values.get('top_quartile_bottom_quartile_gap'))} | "
            f"{_format_metric(values.get('hit_rate_top_targets'))} | "
            f"{_format_metric(values.get('average_value_top_targets'))} |"
        )

    lines.extend(["", "## Baseline Comparison", ""])
    comparison = metrics.get("average_value_of_top_targets_vs_baselines", {})
    if not comparison:
        lines.append("No baseline comparison was available.")
    else:
        lines.extend(
            [
                "| Baseline | Avg Top Value | Delta vs MoreyMachine |",
                "| --- | ---: | ---: |",
            ]
        )
        for method, values in comparison.items():
            lines.append(
                "| "
                f"{method} | "
                f"{_format_metric(values.get('average_value_top_targets'))} | "
                f"{_format_metric(values.get('delta_vs_moreymachine'))} |"
            )

    return "\n".join(lines).rstrip() + "\n"


def _backtest_offseason(
    *,
    previous_season: str,
    next_season: str,
    player_stats: pd.DataFrame,
    team_fingerprints: pd.DataFrame,
    player_archetypes: pd.DataFrame | None,
    team_roster_archetypes: pd.DataFrame | None,
    contracts: pd.DataFrame | None,
    target_team: str,
    random_state: int,
) -> pd.DataFrame:
    historical_teams = _through_season(team_fingerprints, previous_season)
    historical_team_archetypes = _through_season(
        team_roster_archetypes,
        previous_season,
    )
    try:
        roster_gaps = create_roster_gap_report(
            historical_teams,
            roster_archetypes=historical_team_archetypes,
            target_team=target_team,
            target_season=previous_season,
        )
    except ValueError:
        return pd.DataFrame(columns=_ranking_columns())

    candidate_pool = _season_frame(player_stats, previous_season)
    candidate_pool = _exclude_target_team(candidate_pool, target_team)
    if candidate_pool.empty:
        return pd.DataFrame(columns=_ranking_columns())

    previous_archetypes = _season_frame(player_archetypes, previous_season)
    previous_contracts = _season_frame(contracts, previous_season)
    rankings = rank_candidates(
        candidate_pool,
        roster_gaps=roster_gaps,
        player_archetypes=previous_archetypes,
        contracts=previous_contracts,
        season=previous_season,
    )
    if rankings.empty:
        return pd.DataFrame(columns=_ranking_columns())

    enriched = _attach_candidate_identity(rankings, candidate_pool)
    enriched = _attach_previous_season_signals(enriched, candidate_pool)
    enriched = _attach_contracts(enriched, previous_contracts)
    enriched = _attach_baseline_scores(
        enriched,
        previous_season=previous_season,
        random_state=random_state,
    )
    enriched = _attach_next_outcomes(
        enriched,
        next_players=_season_frame(player_stats, next_season),
        salary_frame=previous_contracts,
    )
    enriched["team_weakness_improvement"] = _team_weakness_improvement(
        roster_gaps,
        team_fingerprints,
        target_team=target_team,
        previous_season=previous_season,
        next_season=next_season,
    )
    enriched["next_season_value"] = _next_value_score(enriched)
    enriched["offseason"] = f"after_{previous_season}"
    enriched["previous_season"] = previous_season
    enriched["next_season"] = next_season
    return enriched.loc[:, _ranking_columns(enriched)]


def _attach_candidate_identity(
    rankings: pd.DataFrame,
    candidate_pool: pd.DataFrame,
) -> pd.DataFrame:
    identifiers = candidate_pool.copy()
    identifiers["player_name"] = identifiers.apply(_player_name_from_row, axis=1)
    identifiers["current_team"] = identifiers.apply(_current_team_from_row, axis=1)
    identifiers["position"] = identifiers.apply(_position_from_row, axis=1)

    key_columns = ["player_name", "current_team", "position"]
    identity_columns = [
        column
        for column in ("player_id", "season", "player_name", "current_team", "position")
        if column in identifiers.columns
    ]
    identifiers = identifiers.loc[:, identity_columns].drop_duplicates(
        subset=key_columns,
    )
    return rankings.merge(
        identifiers,
        on=key_columns,
        how="left",
        validate="many_to_one",
    )


def _attach_previous_season_signals(
    rankings: pd.DataFrame,
    candidate_pool: pd.DataFrame,
) -> pd.DataFrame:
    signals = _candidate_signal_frame(candidate_pool)
    return _merge_on_player(rankings, signals)


def _attach_contracts(
    rankings: pd.DataFrame,
    contracts: pd.DataFrame | None,
) -> pd.DataFrame:
    if contracts is None or contracts.empty:
        rankings["salary_millions"] = np.nan
        return rankings
    salary = contracts.copy()
    salary["salary_millions"] = salary.apply(_salary_from_row, axis=1)
    columns = [
        column
        for column in ("player_id", "player_name", "salary_millions")
        if column in salary.columns
    ]
    if len(columns) < 2:
        rankings["salary_millions"] = np.nan
        return rankings
    return _merge_on_player(rankings, salary.loc[:, columns])


def _attach_baseline_scores(
    rankings: pd.DataFrame,
    *,
    previous_season: str,
    random_state: int,
) -> pd.DataFrame:
    result = rankings.copy()
    result["baseline_points_score"] = _percentile_score(result["previous_ppg"])
    result["baseline_impact_score"] = _percentile_score(result["previous_impact"])
    result["baseline_salary_score"] = _percentile_score(result["salary_millions"])
    result["baseline_random_score"] = _random_scores(
        len(result),
        seed=random_state + _season_sort_key(previous_season),
    )
    return result


def _attach_next_outcomes(
    rankings: pd.DataFrame,
    *,
    next_players: pd.DataFrame,
    salary_frame: pd.DataFrame | None,
) -> pd.DataFrame:
    if next_players.empty:
        return _add_empty_next_outcomes(rankings)

    outcomes = _next_outcome_frame(next_players)
    result = _merge_on_player(rankings, outcomes)
    result["next_contract_surplus"] = _contract_surplus(result, salary_frame)
    result["playoff_rotation_usefulness"] = _playoff_rotation_usefulness(result)
    return result


def _candidate_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    if "player_id" in frame:
        result["player_id"] = frame["player_id"]
    result["player_name"] = frame.apply(_player_name_from_row, axis=1)
    result["previous_ppg"] = frame.apply(_points_per_game, axis=1)
    result["previous_impact"] = frame.apply(_impact_proxy, axis=1)
    result["previous_efficiency"] = frame.apply(_efficiency, axis=1)
    result["previous_minutes"] = frame.apply(_minutes, axis=1)
    return result


def _next_outcome_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    if "player_id" in frame:
        result["player_id"] = frame["player_id"]
    result["player_name"] = frame.apply(_player_name_from_row, axis=1)
    result["next_season_minutes"] = frame.apply(_minutes, axis=1)
    result["next_season_ppg"] = frame.apply(_points_per_game, axis=1)
    result["next_season_efficiency"] = frame.apply(_efficiency, axis=1)
    result["next_season_bpm"] = frame.apply(_impact_proxy, axis=1)
    result["next_season_vorp"] = frame.apply(_number_from_row(("vorp",)), axis=1)
    result["next_season_win_shares"] = frame.apply(
        _number_from_row(("win_shares", "ws")),
        axis=1,
    )
    result["next_playoff_minutes"] = frame.apply(
        _number_from_row(("playoff_minutes", "playoff_min", "playoff_mp")),
        axis=1,
    )
    return result


def _next_value_score(frame: pd.DataFrame) -> pd.Series:
    components = pd.DataFrame(index=frame.index)
    components["minutes_value"] = _scale_series(
        frame.get("next_season_minutes"),
        low=400,
        high=2200,
    )
    components["impact_value"] = _scale_series(
        frame.get("next_season_bpm"),
        low=-3,
        high=4,
    )
    components["efficiency_value"] = _scale_series(
        frame.get("next_season_efficiency"),
        low=0.50,
        high=0.64,
    )
    components["win_share_value"] = _scale_series(
        frame.get("next_season_win_shares"),
        low=0,
        high=8,
    )
    components["contract_surplus_value"] = _scale_series(
        frame.get("next_contract_surplus"),
        low=-25,
        high=25,
    )
    components["playoff_rotation_value"] = _scale_series(
        frame.get("playoff_rotation_usefulness"),
        low=0,
        high=100,
    )
    return components.mean(axis=1, skipna=True).round(2)


def _method_metrics(
    rankings: pd.DataFrame,
    *,
    score_column: str,
    top_k: int,
) -> dict[str, Any]:
    usable = rankings.dropna(subset=[score_column, "next_season_value"]).copy()
    if usable.empty:
        return {
            "spearman_correlation": None,
            "top_quartile_bottom_quartile_gap": None,
            "hit_rate_top_targets": None,
            "average_value_top_targets": None,
        }

    spearman = None
    if len(usable) >= 2 and usable[score_column].nunique() > 1:
        spearman_value = usable[score_column].corr(
            usable["next_season_value"],
            method="spearman",
        )
        spearman = None if pd.isna(spearman_value) else float(spearman_value)

    top_gap = _top_bottom_quartile_gap(usable, score_column=score_column)
    top_targets = _top_targets_by_offseason(
        usable,
        score_column=score_column,
        top_k=top_k,
    )
    average_top_value = None
    hit_rate = None
    if not top_targets.empty:
        average_top_value = float(top_targets["next_season_value"].mean())
        hit_rate = float(top_targets["outcome_hit"].mean())

    return {
        "spearman_correlation": spearman,
        "top_quartile_bottom_quartile_gap": top_gap,
        "hit_rate_top_targets": hit_rate,
        "average_value_top_targets": average_top_value,
    }


def _top_bottom_quartile_gap(
    frame: pd.DataFrame,
    *,
    score_column: str,
) -> float | None:
    if len(frame) < 4:
        return None
    top_threshold = frame[score_column].quantile(0.75)
    bottom_threshold = frame[score_column].quantile(0.25)
    top = frame.loc[frame[score_column] >= top_threshold, "next_season_value"]
    bottom = frame.loc[frame[score_column] <= bottom_threshold, "next_season_value"]
    if top.empty or bottom.empty:
        return None
    return float(top.mean() - bottom.mean())


def _top_targets_by_offseason(
    frame: pd.DataFrame,
    *,
    score_column: str,
    top_k: int,
) -> pd.DataFrame:
    rows = []
    for _, offseason_frame in frame.groupby("offseason"):
        threshold = offseason_frame["next_season_value"].quantile(0.75)
        top = offseason_frame.nlargest(min(top_k, len(offseason_frame)), score_column)
        top = top.copy()
        top["outcome_hit"] = top["next_season_value"] >= threshold
        rows.append(top)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _team_weakness_improvement(
    roster_gaps: pd.DataFrame,
    team_fingerprints: pd.DataFrame,
    *,
    target_team: str,
    previous_season: str,
    next_season: str,
) -> float:
    if roster_gaps.empty:
        return np.nan
    positive_gaps = roster_gaps[
        pd.to_numeric(roster_gaps["gap_size"], errors="coerce").fillna(0) > 0
    ]
    if positive_gaps.empty:
        return np.nan
    gap = positive_gaps.sort_values("severity_score", ascending=False).iloc[0]
    source_columns = [
        column.strip()
        for column in str(gap.get("source_columns", "")).split(",")
        if column.strip()
    ]
    if not source_columns:
        return np.nan

    previous = _team_row(team_fingerprints, target_team, previous_season)
    next_row = _team_row(team_fingerprints, target_team, next_season)
    if previous is None or next_row is None:
        return np.nan

    previous_value = _mean_row_value(previous, source_columns)
    next_value = _mean_row_value(next_row, source_columns)
    if pd.isna(previous_value) or pd.isna(next_value):
        return np.nan

    higher_is_better = bool(gap.get("higher_is_better", True))
    if higher_is_better:
        return float(next_value - previous_value)
    return float(previous_value - next_value)


def _through_season(
    frame: pd.DataFrame | None,
    season: str,
) -> pd.DataFrame | None:
    if frame is None:
        return None
    if frame.empty or "season" not in frame.columns:
        return frame.copy()
    season_key = _season_sort_key(season)
    return frame.loc[frame["season"].map(_season_sort_key) <= season_key].copy()


def _season_frame(frame: pd.DataFrame | None, season: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    if "season" not in frame.columns:
        return frame.copy()
    return frame.loc[frame["season"].astype(str).eq(str(season))].copy()


def _exclude_target_team(frame: pd.DataFrame, target_team: str) -> pd.DataFrame:
    team_column = _first_column(
        frame,
        ("team_abbreviation", "team_abbr", "current_team", "team"),
    )
    if team_column is None:
        return frame
    return frame.loc[
        ~frame[team_column].astype(str).str.upper().eq(target_team.upper())
    ].copy()


def _merge_on_player(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    if right.empty:
        return left
    keys = []
    if "player_id" in left.columns and "player_id" in right.columns:
        keys.append("player_id")
    elif "player_name" in left.columns and "player_name" in right.columns:
        keys.append("player_name")
    if not keys:
        return left
    right_columns = [
        column
        for column in right.columns
        if column in keys or column not in left.columns
    ]
    right = right.loc[:, right_columns]
    right = right.drop_duplicates(subset=keys)
    return left.merge(right, on=keys, how="left")


def _add_empty_next_outcomes(rankings: pd.DataFrame) -> pd.DataFrame:
    result = rankings.copy()
    for column in (
        "next_season_minutes",
        "next_season_ppg",
        "next_season_efficiency",
        "next_season_bpm",
        "next_season_vorp",
        "next_season_win_shares",
        "next_playoff_minutes",
        "next_contract_surplus",
        "playoff_rotation_usefulness",
    ):
        result[column] = np.nan
    return result


def _contract_surplus(
    frame: pd.DataFrame,
    salary_frame: pd.DataFrame | None,
) -> pd.Series:
    if salary_frame is None or salary_frame.empty or "salary_millions" not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    value = _next_value_without_contract(frame)
    salary = pd.to_numeric(frame["salary_millions"], errors="coerce")
    salary_penalty = _scale_series(salary, low=0, high=40)
    return value - salary_penalty


def _next_value_without_contract(frame: pd.DataFrame) -> pd.Series:
    components = pd.DataFrame(index=frame.index)
    components["minutes_value"] = _scale_series(
        frame.get("next_season_minutes"),
        low=400,
        high=2200,
    )
    components["impact_value"] = _scale_series(
        frame.get("next_season_bpm"),
        low=-3,
        high=4,
    )
    components["efficiency_value"] = _scale_series(
        frame.get("next_season_efficiency"),
        low=0.50,
        high=0.64,
    )
    components["win_share_value"] = _scale_series(
        frame.get("next_season_win_shares"),
        low=0,
        high=8,
    )
    return components.mean(axis=1, skipna=True)


def _playoff_rotation_usefulness(frame: pd.DataFrame) -> pd.Series:
    playoff_minutes = _scale_series(frame.get("next_playoff_minutes"), low=0, high=600)
    regular_minutes = _scale_series(
        frame.get("next_season_minutes"),
        low=400,
        high=2200,
    )
    impact = _scale_series(frame.get("next_season_bpm"), low=-3, high=4)
    return pd.concat(
        [playoff_minutes, regular_minutes * 0.65, impact * 0.35],
        axis=1,
    ).mean(axis=1, skipna=True)


def _team_row(
    frame: pd.DataFrame,
    target_team: str,
    season: str,
) -> pd.Series | None:
    if not {"season", "team_abbr"}.issubset(frame.columns):
        return None
    rows = frame.loc[
        frame["season"].astype(str).eq(str(season))
        & frame["team_abbr"].astype(str).str.upper().eq(target_team.upper())
    ]
    if rows.empty:
        return None
    return rows.iloc[0]


def _mean_row_value(row: pd.Series, columns: list[str]) -> float:
    values = []
    normalized = {str(column).lower(): column for column in row.index}
    for column in columns:
        actual = normalized.get(column.lower())
        if actual is None:
            continue
        value = pd.to_numeric(pd.Series([row[actual]]), errors="coerce").iloc[0]
        if pd.notna(value):
            values.append(float(value))
    if not values:
        return np.nan
    return float(sum(values) / len(values))


def _points_per_game(row: pd.Series) -> float:
    direct = _number(row, ("points_per_game", "ppg"))
    if pd.notna(direct):
        return direct
    points = _number(row, ("pts", "points"))
    games = _number(row, ("games_played", "gp", "games"))
    if pd.notna(points) and pd.notna(games) and games > 0:
        return points / games
    return np.nan


def _impact_proxy(row: pd.Series) -> float:
    direct = _number(
        row,
        (
            "bpm",
            "box_plus_minus",
            "estimated_plus_minus",
            "epm",
            "vorp",
            "win_shares",
            "ws",
            "plus_minus",
        ),
    )
    return direct


def _efficiency(row: pd.Series) -> float:
    direct = _ratio(
        row,
        (
            "true_shooting_percentage",
            "true_shooting",
            "ts_pct",
            "ts",
            "efg_percentage",
            "efg_pct",
            "fg_pct",
        ),
    )
    if pd.notna(direct):
        return direct
    points = _number(row, ("pts", "points"))
    fga = _number(row, ("fga", "field_goals_attempted"))
    fta = _number(row, ("fta", "free_throws_attempted"))
    if pd.notna(points) and pd.notna(fga) and pd.notna(fta):
        denominator = 2 * (fga + (0.44 * fta))
        if denominator > 0:
            return points / denominator
    return np.nan


def _minutes(row: pd.Series) -> float:
    return _number(row, ("minutes", "min", "mp"))


def _salary_from_row(row: pd.Series) -> float:
    salary = _number(
        row,
        (
            "salary_millions",
            "estimated_salary_millions",
            "annual_salary_millions",
            "salary",
            "estimated_salary",
            "contract_estimate",
            "annual_salary",
            "aav",
        ),
    )
    if pd.isna(salary):
        return np.nan
    if salary > 1000:
        salary = salary / 1_000_000
    return salary


def _player_name_from_row(row: pd.Series) -> str:
    value = _text(row, ("player_name", "name", "player"), default="Unknown Player")
    return value


def _current_team_from_row(row: pd.Series) -> str:
    return _text(
        row,
        ("current_team", "team_abbreviation", "team_abbr", "team"),
        default="",
    )


def _position_from_row(row: pd.Series) -> str:
    return _text(row, ("position", "player_position", "pos"), default="")


def _number_from_row(aliases: tuple[str, ...]):
    def getter(row: pd.Series) -> float:
        return _number(row, aliases)

    return getter


def _percentile_score(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    if values.notna().sum() == 0:
        return pd.Series(np.nan, index=values.index, dtype="float64")
    return values.rank(method="average", pct=True) * 100


def _random_scores(length: int, *, seed: int) -> pd.Series:
    generator = np.random.default_rng(seed)
    return pd.Series(generator.random(length) * 100)


def _scale_series(
    values: pd.Series | None,
    *,
    low: float,
    high: float,
    higher_is_better: bool = True,
) -> pd.Series:
    if values is None:
        return pd.Series(dtype="float64")
    numeric = pd.to_numeric(values, errors="coerce")
    if high == low:
        result = pd.Series(50.0, index=numeric.index)
    else:
        result = (numeric - low) / (high - low) * 100
    if not higher_is_better:
        result = 100 - result
    return result.clip(lower=0, upper=100)


def _read_table(path: str | Path) -> pd.DataFrame:
    table_path = Path(path)
    if table_path.suffix.lower() == ".csv":
        return pd.read_csv(table_path)
    return pd.read_parquet(table_path)


def _read_optional_table(path: str | Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    table_path = Path(path)
    if not table_path.exists():
        return None
    return _read_table(table_path)


def _first_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {column.lower(): column for column in frame.columns}
    for alias in aliases:
        column = normalized.get(alias.lower())
        if column is not None:
            return column
    return None


def _number(row: pd.Series, aliases: tuple[str, ...]) -> float:
    value = _raw_value(row, aliases)
    if value is None:
        return np.nan
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return np.nan
    return float(numeric)


def _ratio(row: pd.Series, aliases: tuple[str, ...]) -> float:
    value = _number(row, aliases)
    if pd.isna(value):
        return np.nan
    if abs(value) > 1.5:
        return value / 100
    return value


def _text(row: pd.Series, aliases: tuple[str, ...], *, default: str) -> str:
    value = _raw_value(row, aliases)
    if value is None or pd.isna(value):
        return default
    return str(value)


def _raw_value(row: pd.Series, aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).lower(): key for key in row.index}
    for alias in aliases:
        key = normalized.get(alias.lower())
        if key is not None:
            return row[key]
    return None


def _nullable_difference(left: Any, right: Any) -> float | None:
    if left is None or right is None or pd.isna(left) or pd.isna(right):
        return None
    return float(left - right)


def _ranking_columns(frame: pd.DataFrame | None = None) -> list[str]:
    columns = [
        "offseason",
        "previous_season",
        "next_season",
        "player_id",
        "player_name",
        "current_team",
        "position",
        "archetype",
        "fit_score",
        "need_match",
        "contender_gain",
        "portability",
        "contract_value",
        "risk_score",
        "recommendation",
        "previous_ppg",
        "previous_impact",
        "previous_efficiency",
        "previous_minutes",
        "salary_millions",
        "baseline_points_score",
        "baseline_impact_score",
        "baseline_salary_score",
        "baseline_random_score",
        "next_season_minutes",
        "next_season_ppg",
        "next_season_efficiency",
        "next_season_bpm",
        "next_season_vorp",
        "next_season_win_shares",
        "next_contract_surplus",
        "team_weakness_improvement",
        "playoff_rotation_usefulness",
        "next_season_value",
        "why_fit",
        "concerns",
    ]
    if frame is None:
        return columns
    return [column for column in columns if column in frame.columns]


def _season_sort_key(value: Any) -> int:
    match = re.search(r"\d{4}", str(value))
    if match is None:
        return -1
    return int(match.group(0))


def _format_metric(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.3f}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return value
