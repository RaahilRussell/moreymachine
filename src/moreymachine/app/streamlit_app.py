"""MoreyMachine - explanation-first NBA front-office dashboard.

REAL_DATA_MODE is enforced here: the app loads only real, precomputed Parquet/
CSV files, shows provenance for every table, and renders loud "missing data"
guidance instead of ever falling back to demo data. It is an unofficial project
and is not affiliated with Daryl Morey, the 76ers, or the NBA.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from moreymachine.app.data_sources import (
    REGISTRY_BY_KEY,
    REQUIRED_KEYS,
    data_source_table,
)
from moreymachine.features.explanations import (
    all_explanations,
)
from moreymachine.utils.config import load_settings
from moreymachine.utils.real_data import fix_hint, is_demo_path

PAGES = (
    "Overview",
    "Data Sources",
    "Sixers Diagnosis",
    "Contender Blueprint",
    "Target Board",
    "Player Detail",
    "Backtest Proof",
)


def main() -> None:
    """Run the MoreyMachine Streamlit dashboard."""
    st.set_page_config(page_title="MoreyMachine", page_icon="🏀", layout="wide")
    settings = load_settings()

    st.sidebar.title("MoreyMachine")
    st.sidebar.caption(
        "Unofficial NBA roster-construction engine. Not affiliated with the "
        "76ers, Daryl Morey, or the NBA."
    )
    _real_mode_banner(settings.real_data_mode)
    page = st.sidebar.radio("Page", PAGES)
    _missing_data_sidebar()

    if page == "Overview":
        render_overview()
    elif page == "Data Sources":
        render_data_sources()
    elif page == "Sixers Diagnosis":
        render_sixers_diagnosis()
    elif page == "Contender Blueprint":
        render_contender_blueprint()
    elif page == "Target Board":
        render_target_board()
    elif page == "Player Detail":
        render_player_detail()
    elif page == "Backtest Proof":
        render_backtest_proof()


# ----------------------------------------------------------------------------
# Data loading (real-mode only)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _read(path_str: str, mtime: float) -> pd.DataFrame:
    path = Path(path_str)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def load(key: str) -> pd.DataFrame:
    """Load a registered real dataset, or an empty frame if it is missing.

    Never reads demo data. Missing files return an empty frame so the calling
    page can render explicit missing-data guidance.
    """
    dataset = REGISTRY_BY_KEY[key]
    if is_demo_path(dataset.path):
        return pd.DataFrame()
    if not dataset.path.exists():
        return pd.DataFrame()
    return _read(str(dataset.path), dataset.path.stat().st_mtime)


def missing_warning(key: str) -> bool:
    """Show a missing-data warning for a dataset; return True if missing."""
    dataset = REGISTRY_BY_KEY[key]
    if dataset.path.exists():
        return False
    st.warning(
        f"**Missing real data: {dataset.label}.** "
        f"Expected at `{dataset.path}`. To fix: {fix_hint(dataset.fix_table)}."
    )
    return True


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
def render_overview() -> None:
    """Render the project overview and how-to-interpret guide."""
    st.title("MoreyMachine")
    st.write(
        "MoreyMachine learns what real contender rosters look like, diagnoses the "
        "Philadelphia 76ers' roster gaps, and ranks real free agents and trade "
        "targets by how well they close those gaps."
    )

    table = data_source_table()
    present = table[table["present"]]
    real = present[present["status"] == "real"]
    manual = present[present["status"] == "manual"]
    columns = st.columns(3)
    columns[0].metric("Real datasets loaded", len(real))
    columns[1].metric("Manual (real) datasets", len(manual))
    columns[2].metric("Demo datasets in use", 0)

    st.subheader("What data is real")
    st.markdown(
        "- **Team & player stats:** live NBA.com advanced metrics via `nba_api`.\n"
        "- **Playoff tiers:** hand-verified real results (2015-16 to 2024-25).\n"
        "- **Salaries:** real Basketball-Reference contracts (where matched).\n"
        "- Every table below shows its source, rows, seasons, and last update."
    )

    missing = [
        REGISTRY_BY_KEY[key].label
        for key in REQUIRED_KEYS
        if not REGISTRY_BY_KEY[key].path.exists()
    ]
    st.subheader("What is missing")
    if missing:
        st.error(
            "Required datasets missing: "
            + ", ".join(missing)
            + ". See the Data Sources page for exact fix commands."
        )
    else:
        st.success("All required real datasets are present.")

    st.subheader("How to interpret the scores")
    st.markdown(
        "- **GM Fit Score (0-100):** 0.35 contender-similarity gain + 0.25 roster-"
        "need match + 0.20 playoff portability + 0.20 contract value - risk.\n"
        "- **Playoff portability (0-100):** how well a player's game survives a "
        "playoff series (real 3pt volume, low turnovers, low-usage fit, defense).\n"
        "- **Severity (gaps):** how far PHI trails contenders, scaled by historical "
        "team-season spread.\n"
        "- Every number on every page links back to a real source and an "
        "explanation - see the Contender Blueprint glossary."
    )


def render_data_sources() -> None:
    """Render the Data Sources provenance panel."""
    st.title("Data Sources")
    st.caption(
        "Every table MoreyMachine uses, with source, rows, seasons covered, last "
        "update, and whether it is real, manual (real), or demo."
    )
    table = data_source_table()
    st.dataframe(
        table.loc[
            :,
            ["table", "status", "rows", "seasons", "last_updated", "source", "path"],
        ],
        use_container_width=True,
        hide_index=True,
    )
    demo_rows = table[table["status"] == "demo"]
    if demo_rows.empty:
        st.success("No demo data is used anywhere in the app.")
    else:
        st.error("Demo data detected in the registry - this should never happen.")

    missing = table[~table["present"]]
    if not missing.empty:
        st.subheader("Missing tables and how to build them")
        for row in missing.itertuples():
            st.markdown(f"- **{row.table}** - {row.seasons}")


def render_sixers_diagnosis() -> None:
    """Render the Sixers roster diagnosis page."""
    st.title("Sixers Diagnosis")
    if missing_warning("phi_roster_gaps") or missing_warning("team_fingerprints"):
        return

    gaps = load("phi_roster_gaps")
    fingerprints = load("team_fingerprints")
    season = str(gaps["target_season"].iloc[0])
    st.caption(f"Target season: {season} (real PHI fingerprint vs contenders).")

    profile = fingerprints[
        fingerprints["team_abbr"].astype(str).eq("PHI")
        & fingerprints["season"].astype(str).eq(season)
    ]
    if not profile.empty:
        row = profile.iloc[0]
        cols = st.columns(4)
        cols[0].metric("Net rating", f"{row['net_rating']:.1f}")
        cols[1].metric("Off rating", f"{row['offensive_rating']:.1f}")
        cols[2].metric("Def rating", f"{row['defensive_rating']:.1f}")
        cols[3].metric("Shooting pressure", f"{row['estimated_shooting_pressure']:.2f}")

    group = st.selectbox(
        "Compare against",
        sorted(gaps["comparison_group_label"].dropna().unique()),
    )
    view = gaps[gaps["comparison_group_label"].eq(group)].sort_values(
        "severity_score", ascending=False
    )
    chart = view.dropna(subset=["severity_score"]).set_index("category")[
        "severity_score"
    ]
    if not chart.empty:
        st.bar_chart(chart)

    st.subheader("Top roster gaps (explained)")
    for row in view.head(6).itertuples():
        if pd.isna(row.severity_score):
            continue
        with st.expander(
            f"{row.category} - severity {row.severity_score:.1f} "
            f"({_pct(row.percentile)} percentile)"
        ):
            st.write(row.explanation)
            importance = getattr(row, "playoff_importance", "")
            fix = getattr(row, "fix_type", "")
            if importance:
                st.markdown(f"**Why it matters in the playoffs:** {importance}")
            if fix:
                st.markdown(f"**What fixes it:** {fix}.")
            st.caption(
                f"PHI {row.target_value:.3g} vs contender avg "
                f"{row.elite_average:.3g}. Source columns: {row.source_columns}."
            )


def render_contender_blueprint() -> None:
    """Render contender blueprint and the score glossary."""
    st.title("Contender Blueprint")
    if missing_warning("team_fingerprints"):
        return
    fingerprints = load("team_fingerprints")

    deep = fingerprints[fingerprints.get("deep_playoff").fillna(False).astype(bool)]
    st.subheader("What deep-playoff teams tend to have")
    st.caption(
        f"Averaged over {len(deep)} real conference-finals-or-better team-seasons "
        "(playoff_tier >= 3)."
    )
    blueprint_columns = [
        "net_rating",
        "offensive_rating",
        "defensive_rating",
        "estimated_shooting_pressure",
        "estimated_possession_control",
        "estimated_two_way_balance",
    ]
    available = [c for c in blueprint_columns if c in deep.columns]
    if available and not deep.empty:
        summary = deep[available].mean().rename("contender_average").reset_index()
        summary.columns = ["feature", "contender_average"]
        st.dataframe(summary, use_container_width=True, hide_index=True)

    archetypes = load("team_roster_archetypes")
    if not archetypes.empty and "cluster_name" in archetypes.columns:
        st.subheader("Roster archetypes among contenders")
        merged = deep.merge(
            archetypes[["season", "team_abbr", "cluster_name"]].drop_duplicates(),
            on=["season", "team_abbr"],
            how="left",
        )
        counts = merged["cluster_name"].value_counts()
        if not counts.empty:
            st.bar_chart(counts)

    st.subheader("Tier definitions")
    st.markdown(
        "- **Playoff tier:** 0 missed, 1 first round, 2 second round, 3 conference "
        "finals, 4 finals, 5 champion.\n"
        "- **Quality tier (regular season):** within-season net-rating band, "
        "0 bottom to 5 elite."
    )

    st.subheader("Score glossary")
    for explanation in all_explanations():
        with st.expander(explanation.label):
            st.markdown(explanation.to_markdown())


def render_target_board() -> None:
    """Render the ranked candidate target board with filters."""
    st.title("Target Board")
    if missing_warning("candidate_fit_rankings"):
        return
    candidates = load("candidate_fit_rankings")
    _candidate_source_note(candidates)

    filtered = candidates.copy()
    if "archetype" in filtered.columns:
        options = sorted(filtered["archetype"].dropna().unique())
        chosen = st.multiselect("Archetype", options, default=options)
        if chosen:
            filtered = filtered[filtered["archetype"].isin(chosen)]
    if "recommendation" in filtered.columns:
        recs = sorted(filtered["recommendation"].dropna().unique())
        chosen = st.multiselect("Recommendation", recs, default=recs)
        if chosen:
            filtered = filtered[filtered["recommendation"].isin(chosen)]
    if "salary_millions" in filtered.columns:
        max_salary = st.slider("Max salary ($M)", 0, 65, 65)
        salary = pd.to_numeric(filtered["salary_millions"], errors="coerce")
        filtered = filtered[salary.isna() | (salary <= max_salary)]
    if "risk_score" in filtered.columns:
        max_risk = st.slider("Max risk", 0, 100, 100)
        risk = pd.to_numeric(filtered["risk_score"], errors="coerce")
        filtered = filtered[risk <= max_risk]

    display_columns = [
        c
        for c in (
            "player_name",
            "current_team",
            "archetype",
            "fit_score",
            "need_match",
            "contender_gain",
            "portability",
            "contract_value",
            "risk_score",
            "salary_millions",
            "recommendation",
        )
        if c in filtered.columns
    ]
    st.dataframe(
        filtered.sort_values("fit_score", ascending=False).loc[:, display_columns],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(filtered)} of {len(candidates)} real candidates shown.")


def render_player_detail() -> None:
    """Render a single-candidate deep dive."""
    st.title("Player Detail")
    if missing_warning("candidate_fit_rankings"):
        return
    candidates = load("candidate_fit_rankings")
    names = candidates["player_name"].astype(str).tolist()
    selected = st.selectbox("Candidate", names)
    row = candidates[candidates["player_name"].astype(str).eq(selected)].iloc[0]

    cols = st.columns(5)
    cols[0].metric("GM Fit", _fmt(row.get("fit_score")))
    cols[1].metric("Need match", _fmt(row.get("need_match")))
    cols[2].metric("Contender gain", _fmt(row.get("contender_gain")))
    cols[3].metric("Portability", _fmt(row.get("portability")))
    cols[4].metric("Contract value", _fmt(row.get("contract_value")))

    st.markdown(f"**Recommendation:** {row.get('recommendation', 'n/a')}")
    if pd.notna(row.get("salary_millions")):
        st.caption(f"Salary: ${float(row['salary_millions']):.1f}M")

    breakdown = pd.DataFrame(
        {
            "component": [
                "need_match",
                "contender_gain",
                "portability",
                "contract_value",
                "risk_score",
            ],
            "score": [
                _num(row.get(c))
                for c in (
                    "need_match",
                    "contender_gain",
                    "portability",
                    "contract_value",
                    "risk_score",
                )
            ],
        }
    ).dropna()
    if not breakdown.empty:
        st.bar_chart(breakdown.set_index("component")["score"])

    st.subheader("Why he fits")
    _bullets(str(row.get("why_fit", "")))
    st.subheader("Why he may not fit")
    _bullets(str(row.get("concerns", "")))

    st.subheader("Data sources & missing data")
    st.markdown(f"- **Sources:** {row.get('data_sources', 'n/a')}")
    flags = str(row.get("missing_data_flags", "none"))
    if flags and flags != "none":
        st.warning(f"Missing data: {flags}")
    else:
        st.success("No missing-data flags for this candidate.")


def render_backtest_proof() -> None:
    """Render the backtest proof page."""
    st.title("Backtest Proof")
    st.caption(
        "Do fit-based rankings beat simple baselines at predicting next-season "
        "value, using only prior-season data?"
    )
    if missing_warning("backtest_rankings"):
        return
    rankings = load("backtest_rankings")
    summary_path = REGISTRY_BY_KEY["backtest_rankings"].path.parent / (
        "backtest_summary.md"
    )
    if summary_path.exists():
        st.markdown(summary_path.read_text(encoding="utf-8"))
    if {"fit_score", "next_season_value"}.issubset(rankings.columns):
        st.subheader("Fit score vs next-season value")
        st.scatter_chart(rankings, x="fit_score", y="next_season_value")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _real_mode_banner(real_data_mode: bool) -> None:
    if real_data_mode:
        st.sidebar.success("REAL_DATA_MODE: on (no demo data)")
    else:
        st.sidebar.error(
            "REAL_DATA_MODE: OFF - demo data may appear. Set REAL_DATA_MODE=true."
        )


def _missing_data_sidebar() -> None:
    missing = [
        REGISTRY_BY_KEY[key].label
        for key in REQUIRED_KEYS
        if not REGISTRY_BY_KEY[key].path.exists()
    ]
    if missing:
        st.sidebar.warning("Missing: " + ", ".join(missing))


def _candidate_source_note(candidates: pd.DataFrame) -> None:
    types = (
        candidates["candidate_type"].dropna().unique().tolist()
        if "candidate_type" in candidates.columns
        else []
    )
    note = "Candidates are real nba_api players."
    if "manual_watchlist" in types:
        note += " Some are a manual/auto watchlist (verify free-agent status)."
    st.info(note + " Salaries: real Basketball-Reference contracts where matched.")


def _bullets(text: str) -> None:
    parts = [
        item.strip(" -")
        for chunk in text.split("\n")
        for item in chunk.split(";")
        if item.strip(" -")
    ]
    if not parts:
        st.write("No explanation available.")
        return
    for part in parts:
        st.markdown(f"- {part}")


def _fmt(value: Any) -> str:
    number = _num(value)
    return "N/A" if pd.isna(number) else f"{number:.1f}"


def _num(value: Any) -> float:
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def _pct(value: Any) -> str:
    number = _num(value)
    return "n/a" if pd.isna(number) else f"{number:.0f}th"


if __name__ == "__main__":
    main()
