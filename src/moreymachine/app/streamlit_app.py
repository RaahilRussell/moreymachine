"""Streamlit dashboard for MoreyMachine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from moreymachine.features.player_archetypes import PLAYER_ARCHETYPES_PATH
from moreymachine.features.roster_archetypes import TEAM_ROSTER_ARCHETYPES_PATH
from moreymachine.features.roster_gaps import ROSTER_GAPS_PATH
from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.models.backtest import (
    BACKTEST_RANKINGS_PATH,
    BACKTEST_RESULTS_PATH,
    BACKTEST_SUMMARY_PATH,
)
from moreymachine.models.fit_model import CANDIDATE_FIT_RANKINGS_PATH
from moreymachine.utils.paths import DATA_DIR, PROCESSED_DATA_DIR

DEMO_DATA_DIR = DATA_DIR / "demo"
PLAYER_STATS_PATH = PROCESSED_DATA_DIR / "player_seasons_basic.parquet"

PAGE_OPTIONS = (
    "Project overview",
    "Sixers roster diagnosis",
    "Contender blueprint",
    "Free agent board",
    "Player detail report",
    "Backtest results",
)

DATASET_PATHS = {
    "candidate_rankings": {
        "full": CANDIDATE_FIT_RANKINGS_PATH,
        "demo": DEMO_DATA_DIR / "candidate_fit_rankings.parquet",
    },
    "roster_gaps": {
        "full": ROSTER_GAPS_PATH,
        "demo": DEMO_DATA_DIR / "phi_roster_gaps.parquet",
    },
    "team_fingerprints": {
        "full": TEAM_FINGERPRINTS_PATH,
        "demo": DEMO_DATA_DIR / "team_fingerprints.parquet",
    },
    "team_archetypes": {
        "full": TEAM_ROSTER_ARCHETYPES_PATH,
        "demo": DEMO_DATA_DIR / "team_roster_archetypes.parquet",
    },
    "player_archetypes": {
        "full": PLAYER_ARCHETYPES_PATH,
        "demo": DEMO_DATA_DIR / "player_archetypes.parquet",
    },
    "player_stats": {
        "full": PLAYER_STATS_PATH,
        "demo": DEMO_DATA_DIR / "player_seasons_basic.parquet",
    },
    "backtest_rankings": {
        "full": BACKTEST_RANKINGS_PATH,
        "demo": DEMO_DATA_DIR / "backtest_rankings.parquet",
    },
}

JSON_PATHS = {
    "backtest_results": {
        "full": BACKTEST_RESULTS_PATH,
        "demo": DEMO_DATA_DIR / "backtest_results.json",
    }
}

TEXT_PATHS = {
    "backtest_summary": {
        "full": BACKTEST_SUMMARY_PATH,
        "demo": DEMO_DATA_DIR / "backtest_summary.md",
    }
}


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="MoreyMachine",
        page_icon="MM",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("MoreyMachine")

    mode = _data_mode_selector()
    data = load_dashboard_data(mode)
    target_team, season = _target_controls(data)
    page = st.sidebar.radio("Page", PAGE_OPTIONS)

    _data_status(data)

    if page == "Project overview":
        render_project_overview(data, target_team, season)
    elif page == "Sixers roster diagnosis":
        render_roster_diagnosis(data, target_team, season)
    elif page == "Contender blueprint":
        render_contender_blueprint(data, season)
    elif page == "Free agent board":
        render_free_agent_board(data, target_team, season)
    elif page == "Player detail report":
        render_player_detail(data, target_team, season)
    elif page == "Backtest results":
        render_backtest_results(data)


def load_dashboard_data(mode: str) -> dict[str, Any]:
    """Load all dashboard datasets for the selected data mode."""
    return {
        "mode": mode,
        "candidate_rankings": load_parquet_dataset("candidate_rankings", mode),
        "roster_gaps": load_parquet_dataset("roster_gaps", mode),
        "team_fingerprints": load_parquet_dataset("team_fingerprints", mode),
        "team_archetypes": load_parquet_dataset("team_archetypes", mode),
        "player_archetypes": load_parquet_dataset("player_archetypes", mode),
        "player_stats": load_parquet_dataset("player_stats", mode),
        "backtest_rankings": load_parquet_dataset("backtest_rankings", mode),
        "backtest_results": load_json_dataset("backtest_results", mode),
        "backtest_summary": load_text_dataset("backtest_summary", mode),
    }


@st.cache_data(show_spinner=False)
def load_parquet_dataset(dataset_name: str, mode: str) -> pd.DataFrame:
    """Load a dashboard Parquet dataset or return an empty frame."""
    path = resolve_dataset_path(dataset_name, mode, DATASET_PATHS)
    if path is None:
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_json_dataset(dataset_name: str, mode: str) -> dict[str, Any]:
    """Load a dashboard JSON dataset or return an empty mapping."""
    path = resolve_dataset_path(dataset_name, mode, JSON_PATHS)
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_text_dataset(dataset_name: str, mode: str) -> str:
    """Load a dashboard text dataset or return an empty string."""
    path = resolve_dataset_path(dataset_name, mode, TEXT_PATHS)
    if path is None:
        return ""
    return path.read_text(encoding="utf-8")


def resolve_dataset_path(
    dataset_name: str,
    mode: str,
    path_map: dict[str, dict[str, Path]],
) -> Path | None:
    """Return the best available data path for a dataset and mode."""
    options = path_map[dataset_name]
    if mode == "Full data":
        return options["full"] if options["full"].exists() else None
    if mode == "Demo data":
        return options["demo"] if options["demo"].exists() else None
    if options["full"].exists():
        return options["full"]
    if options["demo"].exists():
        return options["demo"]
    return None


def render_project_overview(
    data: dict[str, Any],
    target_team: str,
    season: str | None,
) -> None:
    """Render the project overview page."""
    candidates = data["candidate_rankings"]
    gaps = _filtered_gaps(data["roster_gaps"], target_team, season)
    teams = data["team_fingerprints"]
    backtest = data["backtest_results"]

    st.subheader("Project overview")
    columns = st.columns(4)
    columns[0].metric("Candidate rows", _count_text(candidates))
    columns[1].metric("Gap categories", _count_text(gaps))
    columns[2].metric("Team seasons", _count_text(teams))
    columns[3].metric("Backtest rows", backtest.get("row_count", 0) or 0)

    top_candidate = _top_candidate(candidates)
    if top_candidate is not None:
        st.markdown("### Current top target")
        render_candidate_summary(top_candidate, gaps)

    st.markdown("### Workflow")
    st.write(
        "MoreyMachine builds team fingerprints, labels contender outcomes, diagnoses "
        "roster gaps, scores player portability, ranks candidate fits, and backtests "
        "the ranking logic against next-season outcomes."
    )


def render_roster_diagnosis(
    data: dict[str, Any],
    target_team: str,
    season: str | None,
) -> None:
    """Render target roster gap diagnosis."""
    gaps = _filtered_gaps(data["roster_gaps"], target_team, season)
    st.subheader(f"{target_team} roster diagnosis")
    if gaps.empty:
        st.info("No roster gap report is available for the selected team and season.")
        return

    render_gap_chart(gaps)
    display_columns = [
        "comparison_group_label",
        "category",
        "target_value",
        "elite_average",
        "percentile",
        "gap_size",
        "severity_score",
        "explanation",
    ]
    st.dataframe(
        gaps.loc[:, [column for column in display_columns if column in gaps.columns]],
        use_container_width=True,
        hide_index=True,
    )


def render_contender_blueprint(data: dict[str, Any], season: str | None) -> None:
    """Render contender team profile summaries."""
    teams = data["team_fingerprints"]
    archetypes = data["team_archetypes"]
    st.subheader("Contender blueprint")
    if teams.empty:
        st.info("No team fingerprint data is available.")
        return

    frame = teams.copy()
    if season and "season" in frame:
        frame = frame[frame["season"].astype(str).eq(str(season))]
    if not archetypes.empty:
        frame = frame.merge(
            archetypes.loc[
                :,
                [
                    column
                    for column in ("season", "team_abbr", "cluster_name")
                    if column in archetypes.columns
                ],
            ].drop_duplicates(),
            on=[column for column in ("season", "team_abbr") if column in frame],
            how="left",
        )

    contender_mask = _contender_mask(frame)
    contenders = frame.loc[contender_mask].copy()
    if contenders.empty:
        st.info("No conference-finals-or-better teams are available in this slice.")
        return

    st.metric("Contender team-seasons", len(contenders))
    blueprint_columns = [
        "offensive_rating",
        "defensive_rating",
        "net_rating",
        "pace",
        "estimated_shooting_pressure",
        "estimated_possession_control",
        "estimated_two_way_balance",
    ]
    summary = (
        contenders.loc[
            :,
            [column for column in blueprint_columns if column in contenders.columns],
        ]
        .mean(numeric_only=True)
        .rename("contender_average")
        .reset_index()
        .rename(columns={"index": "feature"})
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)
    if "cluster_name" in contenders.columns:
        st.markdown("### Common roster archetypes")
        st.bar_chart(contenders["cluster_name"].value_counts())


def render_free_agent_board(
    data: dict[str, Any],
    target_team: str,
    season: str | None,
) -> None:
    """Render candidate ranking board."""
    candidates = _filtered_candidates(data["candidate_rankings"], season)
    gaps = _filtered_gaps(data["roster_gaps"], target_team, season)
    st.subheader("Free agent board")
    if candidates.empty:
        st.info("No candidate fit rankings are available.")
        return

    filtered = candidate_filters(candidates)
    sort_options = [
        column
        for column in ("fit_score", "need_match", "portability")
        if column in filtered
    ]
    if sort_options:
        sort_column = st.selectbox("Sort by", sort_options)
        filtered = filtered.sort_values(sort_column, ascending=False)
    st.dataframe(
        filtered.loc[
            :,
            [
                column
                for column in (
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
                )
                if column in filtered.columns
            ],
        ],
        use_container_width=True,
        hide_index=True,
    )

    selected = select_candidate(filtered)
    if selected is not None:
        st.markdown("### Score breakdown")
        render_candidate_summary(selected, gaps)


def render_player_detail(
    data: dict[str, Any],
    target_team: str,
    season: str | None,
) -> None:
    """Render an individual player detail report."""
    candidates = _filtered_candidates(data["candidate_rankings"], season)
    gaps = _filtered_gaps(data["roster_gaps"], target_team, season)
    st.subheader("Player detail report")
    if candidates.empty:
        st.info("No candidate rankings are available.")
        return

    selected = select_candidate(candidates)
    if selected is None:
        return
    render_candidate_summary(selected, gaps)
    st.markdown("### Why fit")
    render_bullets(str(selected.get("why_fit", "")))
    st.markdown("### Concerns")
    render_bullets(str(selected.get("concerns", "")))


def render_backtest_results(data: dict[str, Any]) -> None:
    """Render backtest proof page."""
    results = data["backtest_results"]
    rankings = data["backtest_rankings"]
    summary = data["backtest_summary"]
    st.subheader("Backtest results")
    if not results:
        st.info("No backtest results are available.")
        return

    overall = pd.DataFrame(results.get("overall", {})).T.reset_index()
    if not overall.empty:
        overall = overall.rename(columns={"index": "method"})
        st.dataframe(overall, use_container_width=True, hide_index=True)
    comparison = pd.DataFrame(
        results.get("average_value_of_top_targets_vs_baselines", {})
    ).T.reset_index()
    if not comparison.empty:
        comparison = comparison.rename(columns={"index": "baseline"})
        st.markdown("### Average value vs baselines")
        st.dataframe(comparison, use_container_width=True, hide_index=True)
    if not rankings.empty and {"fit_score", "next_season_value"}.issubset(rankings):
        st.markdown("### Fit score vs next-season value")
        st.scatter_chart(rankings, x="fit_score", y="next_season_value")
    if summary:
        with st.expander("Backtest summary markdown"):
            st.markdown(summary)


def candidate_filters(candidates: pd.DataFrame) -> pd.DataFrame:
    """Apply sidebar candidate filters."""
    filtered = candidates.copy()
    if "position" in filtered:
        positions = sorted(value for value in filtered["position"].dropna().unique())
        selected = st.multiselect("Position", positions, default=positions)
        if selected:
            filtered = filtered[filtered["position"].isin(selected)]
    if "archetype" in filtered:
        archetypes = sorted(value for value in filtered["archetype"].dropna().unique())
        selected = st.multiselect("Archetype", archetypes, default=archetypes)
        if selected:
            filtered = filtered[filtered["archetype"].isin(selected)]
    filtered["salary_tier"] = filtered.apply(_salary_tier, axis=1)
    tiers = sorted(filtered["salary_tier"].dropna().unique())
    selected_tiers = st.multiselect("Salary tier", tiers, default=tiers)
    if selected_tiers:
        filtered = filtered[filtered["salary_tier"].isin(selected_tiers)]
    if "risk_score" in filtered:
        max_risk = st.slider("Maximum risk", 0, 100, 100)
        risk = pd.to_numeric(filtered["risk_score"], errors="coerce")
        filtered = filtered[risk <= max_risk]
    return filtered


def select_candidate(candidates: pd.DataFrame) -> pd.Series | None:
    """Select a candidate row from a candidate frame."""
    if candidates.empty or "player_name" not in candidates:
        return None
    names = candidates["player_name"].astype(str).tolist()
    selected_name = st.selectbox("Candidate", names)
    return candidates[candidates["player_name"].astype(str).eq(selected_name)].iloc[0]


def render_candidate_summary(candidate: pd.Series, gaps: pd.DataFrame) -> None:
    """Render candidate score summary and similarity proxy."""
    columns = st.columns(5)
    columns[0].metric("Fit score", _metric_value(candidate.get("fit_score")))
    columns[1].metric("Need match", _metric_value(candidate.get("need_match")))
    columns[2].metric("Contender gain", _metric_value(candidate.get("contender_gain")))
    columns[3].metric("Portability", _metric_value(candidate.get("portability")))
    columns[4].metric("Risk", _metric_value(candidate.get("risk_score")))

    score_columns = [
        "need_match",
        "contender_gain",
        "portability",
        "contract_value",
        "risk_score",
    ]
    scores = pd.DataFrame(
        {
            "component": score_columns,
            "score": [
                _numeric_value(candidate.get(column)) for column in score_columns
            ],
        }
    ).dropna()
    if not scores.empty:
        st.bar_chart(scores, x="component", y="score")

    before, after = contender_similarity_before_after(candidate, gaps)
    st.markdown("### Contender similarity")
    st.progress(int(before), text=f"Before: {before:.1f}")
    st.progress(int(after), text=f"After adding candidate: {after:.1f}")

    st.markdown("### Explanation")
    render_bullets(str(candidate.get("why_fit", "")))
    st.markdown("### Concerns")
    render_bullets(str(candidate.get("concerns", "")))


def render_gap_chart(gaps: pd.DataFrame) -> None:
    """Render roster gap severity chart."""
    if gaps.empty or "severity_score" not in gaps:
        return
    chart = (
        gaps.sort_values("severity_score", ascending=False)
        .drop_duplicates("category")
        .loc[:, ["category", "severity_score"]]
    )
    st.bar_chart(chart, x="category", y="severity_score")


def render_bullets(text: str) -> None:
    """Render semicolon or newline separated explanation bullets."""
    bullets = [
        item.strip(" -")
        for part in text.split("\n")
        for item in part.split(";")
        if item.strip(" -")
    ]
    if not bullets:
        st.write("No explanation available.")
        return
    for bullet in bullets:
        st.markdown(f"- {bullet}")


def contender_similarity_before_after(
    candidate: pd.Series,
    gaps: pd.DataFrame,
) -> tuple[float, float]:
    """Estimate before/after contender similarity for a candidate."""
    before = candidate.get("contender_similarity_before")
    after = candidate.get("contender_similarity_after")
    if pd.notna(before) and pd.notna(after):
        return float(before), float(after)

    if gaps.empty or "severity_score" not in gaps:
        before_value = 50.0
    else:
        severity = pd.to_numeric(gaps["severity_score"], errors="coerce").fillna(0)
        before_value = max(0.0, min(100.0, 100.0 - float(severity.mean())))
    gain = pd.to_numeric(
        pd.Series([candidate.get("contender_gain")]),
        errors="coerce",
    ).iloc[0]
    if pd.isna(gain):
        gain = 0.0
    after_value = max(before_value, min(100.0, before_value + (gain * 0.30)))
    return before_value, after_value


def _data_mode_selector() -> str:
    full_available = any(path["full"].exists() for path in DATASET_PATHS.values())
    demo_available = any(path["demo"].exists() for path in DATASET_PATHS.values())
    default = "Auto"
    if demo_available and not full_available:
        default = "Demo data"
    options = ["Auto", "Full data", "Demo data"]
    return st.sidebar.radio("Data source", options, index=options.index(default))


def _target_controls(data: dict[str, Any]) -> tuple[str, str | None]:
    teams = _available_teams(data)
    target_team = st.sidebar.selectbox(
        "Target team",
        teams,
        index=teams.index("PHI") if "PHI" in teams else 0,
    )
    seasons = _available_seasons(data, target_team)
    season = None
    if seasons:
        season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)
    return target_team, season


def _available_teams(data: dict[str, Any]) -> list[str]:
    values: set[str] = set()
    gaps = data["roster_gaps"]
    if "target_team" in gaps:
        values.update(gaps["target_team"].dropna().astype(str))
    teams = data["team_fingerprints"]
    if "team_abbr" in teams:
        values.update(teams["team_abbr"].dropna().astype(str))
    return sorted(values) or ["PHI"]


def _available_seasons(data: dict[str, Any], target_team: str) -> list[str]:
    values: set[str] = set()
    gaps = data["roster_gaps"]
    if {"target_team", "target_season"}.issubset(gaps.columns):
        values.update(
            gaps.loc[
                gaps["target_team"].astype(str).str.upper().eq(target_team.upper()),
                "target_season",
            ]
            .dropna()
            .astype(str)
        )
    teams = data["team_fingerprints"]
    if {"team_abbr", "season"}.issubset(teams.columns):
        values.update(
            teams.loc[
                teams["team_abbr"].astype(str).str.upper().eq(target_team.upper()),
                "season",
            ]
            .dropna()
            .astype(str)
        )
    return sorted(values, key=_season_sort_key)


def _filtered_gaps(
    gaps: pd.DataFrame,
    target_team: str,
    season: str | None,
) -> pd.DataFrame:
    if gaps.empty:
        return gaps
    result = gaps.copy()
    if "target_team" in result:
        result = result[
            result["target_team"].astype(str).str.upper().eq(target_team.upper())
        ]
    if season and "target_season" in result:
        result = result[result["target_season"].astype(str).eq(str(season))]
    return result


def _filtered_candidates(candidates: pd.DataFrame, season: str | None) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    if season is None:
        return candidates
    season_columns = [
        column
        for column in ("season", "previous_season", "target_season")
        if column in candidates.columns
    ]
    if not season_columns:
        return candidates
    column = season_columns[0]
    return candidates[candidates[column].astype(str).eq(str(season))].copy()


def _contender_mask(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if "deep_playoff" in frame:
        mask |= frame["deep_playoff"].fillna(False).astype(bool)
    if "playoff_tier" in frame:
        mask |= pd.to_numeric(frame["playoff_tier"], errors="coerce").ge(3)
    return mask


def _top_candidate(candidates: pd.DataFrame) -> pd.Series | None:
    if candidates.empty or "fit_score" not in candidates:
        return None
    return candidates.sort_values("fit_score", ascending=False).iloc[0]


def _salary_tier(row: pd.Series) -> str:
    salary = None
    for column in (
        "salary_millions",
        "estimated_salary_millions",
        "annual_salary_millions",
    ):
        if column in row and pd.notna(row[column]):
            salary = float(row[column])
            break
    if salary is None:
        return "Unknown"
    if salary < 8:
        return "Value"
    if salary < 18:
        return "Mid-tier"
    if salary < 30:
        return "Expensive"
    return "Max-level"


def _metric_value(value: Any) -> str:
    numeric = _numeric_value(value)
    if pd.isna(numeric):
        return "N/A"
    return f"{float(numeric):.1f}"


def _numeric_value(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return float("nan")
    return float(numeric)


def _count_text(frame: pd.DataFrame) -> str:
    return f"{len(frame):,}"


def _data_status(data: dict[str, Any]) -> None:
    missing = [
        name
        for name, value in data.items()
        if name != "mode"
        and (
            (isinstance(value, pd.DataFrame) and value.empty)
            or (isinstance(value, dict) and not value)
            or (isinstance(value, str) and not value)
        )
    ]
    if missing:
        st.sidebar.caption(f"Missing or empty: {', '.join(missing[:4])}")


def _season_sort_key(value: Any) -> int:
    text = str(value)
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) >= 4:
        return int(digits[:4])
    return -1


if __name__ == "__main__":
    main()
