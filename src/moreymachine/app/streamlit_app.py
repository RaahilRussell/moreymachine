"""MoreyMachine - explanation-first NBA front-office dashboard.

REAL_DATA_MODE is enforced here: the app loads only real, precomputed Parquet/
CSV files, shows provenance for every table, and renders loud "missing data"
guidance instead of ever falling back to demo data. It never live-fetches on a
page load - all data is built offline by the pipeline scripts and refreshed via
``scripts/refresh_current_data.py``. It is an unofficial project and is not
affiliated with Daryl Morey, the 76ers, or the NBA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from moreymachine.app.data_sources import (
    REGISTRY_BY_KEY,
    REQUIRED_KEYS,
    data_source_table,
)
from moreymachine.data.freshness import REFRESH_COMMAND, summarize_freshness
from moreymachine.features.explanations import all_explanations
from moreymachine.utils.config import load_settings
from moreymachine.utils.real_data import fix_hint, is_demo_path

PAGES = (
    "Overview",
    "Data Sources",
    "Sixers Roster Diagnosis",
    "Contender Blueprint",
    "Realistic Target Board",
    "Free Agent Board",
    "Trade Target Board",
    "Unrealistic Watchlist",
    "Player Detail",
    "Transaction Review",
    "Model Diagnostics",
    "Backtest Proof",
)

PHI_CORE = ("Joel Embiid", "Tyrese Maxey", "Paul George")
PRIORITY_LABEL = "Priority Target"

# Numeric score columns rendered as the at-a-glance board table.
BOARD_TABLE_COLUMNS = (
    "player_name",
    "current_team",
    "position",
    "role_archetype",
    "candidate_type",
    "candidate_status_freshness",
    "recommendation",
    "final_fit",
    "need_match",
    "contender_gain",
    "portability",
    "contract_value",
    "risk_score",
    "risk_tier",
    "expected_role",
    "salary_bucket",
    "cap_hit_millions",
    "salary_source",
    "acquisition_feasibility",
    "feasibility_tier",
    "why_fit",
    "concerns",
    "gaps_addressed",
    "role_on_sixers",
    "salary_context",
    "acquisition_summary",
    "risk_summary",
    "transaction_review_reason",
    "latest_transaction_date",
    "data_sources",
    "missing_data_flags",
)


def main() -> None:
    """Run the MoreyMachine Streamlit dashboard."""
    st.set_page_config(page_title="MoreyMachine", page_icon="MM", layout="wide")
    settings = load_settings()

    st.sidebar.title("MoreyMachine")
    st.sidebar.caption(
        "Unofficial NBA roster-construction engine. Not affiliated with the "
        "76ers, Daryl Morey, or the NBA."
    )
    _real_mode_banner(settings.real_data_mode)
    page = st.sidebar.radio("Page", PAGES)
    _freshness_sidebar()
    _missing_data_sidebar()

    renderers = {
        "Overview": render_overview,
        "Data Sources": render_data_sources,
        "Sixers Roster Diagnosis": render_sixers_diagnosis,
        "Contender Blueprint": render_contender_blueprint,
        "Realistic Target Board": render_realistic_board,
        "Free Agent Board": render_free_agent_board,
        "Trade Target Board": render_trade_board,
        "Unrealistic Watchlist": render_watchlist,
        "Player Detail": render_player_detail,
        "Transaction Review": render_transaction_review,
        "Model Diagnostics": render_model_diagnostics,
        "Backtest Proof": render_backtest_proof,
    }
    renderers[page]()


# ----------------------------------------------------------------------------
# Data loading (real-mode only, cached - never live-fetches)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _read(path_str: str, mtime: float) -> pd.DataFrame:
    path = Path(path_str)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def load(key: str) -> pd.DataFrame:
    """Load a registered real dataset, or an empty frame if it is missing."""
    dataset = REGISTRY_BY_KEY[key]
    if is_demo_path(dataset.path) or not dataset.path.exists():
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
        "Philadelphia 76ers' roster gaps, classifies every real NBA player into one "
        "acquisition lane, and ranks realistic free agents and trade targets by how "
        "well they close those gaps - with an explanation behind every number."
    )

    table = data_source_table()
    present = table[table["present"]]
    columns = st.columns(3)
    real_n = int((present["status"] == "real").sum())
    manual_n = int((present["status"] == "manual").sum())
    columns[0].metric("Real datasets loaded", real_n)
    columns[1].metric("Manual (real) datasets", manual_n)
    columns[2].metric("Demo datasets in use", 0)

    realistic = load("candidate_fit_rankings_realistic")
    if not realistic.empty:
        priority = int((realistic["recommendation"] == PRIORITY_LABEL).sum())
        cols = st.columns(3)
        cols[0].metric("Realistic candidates", len(realistic))
        cols[1].metric("Priority targets", f"{priority} / 10")
        roster_n = len(load("current_roster_reference"))
        cols[2].metric("Current Sixers (off board)", roster_n)

    st.subheader("How to read the boards")
    st.markdown(
        "- **Realistic Target Board** is the recommendation surface: free agents and "
        "tradeable players, capped at 10 Priority targets.\n"
        "- **Free Agent / Trade boards** are the same data split by how you'd acquire "
        "the player.\n"
        "- **Unrealistic Watchlist** is *theoretical fit only* - stars, untouchable "
        "core, and missing-contract players. **Not recommendations.**\n"
        "- **final_fit** = 0.30 need + 0.25 contender gain + 0.20 portability + 0.15 "
        "contract value + 0.10 feasibility - 0.20 x risk."
    )
    st.markdown(
        "**Real-time means cached and refreshable.** The app reads existing "
        "Parquet, CSV, JSON, and Markdown artifacts only. To refresh data, run "
        f"`{REFRESH_COMMAND}` and rebuild the pipeline; page loads do not call "
        "live APIs."
    )

    missing = _missing_required()
    st.subheader("Pipeline status")
    if missing:
        st.error("Required datasets missing: " + ", ".join(missing))
    else:
        st.success("All required real datasets are present.")


def render_data_sources() -> None:
    """Render the Data Sources provenance + freshness panel."""
    st.title("Data Sources")
    st.caption(
        "Every table MoreyMachine uses, with source, rows, seasons, last update, and "
        "whether it is real, manual (real), or demo. Nothing is fetched live."
    )

    st.subheader("Freshness")
    summaries = summarize_freshness()
    fresh = pd.DataFrame(
        {
            "table": s.name,
            "present": s.exists,
            "rows": s.rows,
            "seasons": s.seasons,
            "pulled_at": s.pulled_at or s.note,
            "mode": s.data_mode,
        }
        for s in summaries
    )
    st.dataframe(fresh, use_container_width=True, hide_index=True)
    st.info(f"To refresh real data, run: `{REFRESH_COMMAND}` then rebuild the boards.")

    st.subheader("Full registry")
    table = data_source_table()
    st.dataframe(
        table.loc[
            :,
            [
                "table",
                "status",
                "rows",
                "seasons",
                "source",
                "pulled_at",
                "freshness_age",
                "missing_fields",
                "refresh_command",
                "path",
            ],
        ],
        use_container_width=True,
        hide_index=True,
    )
    if (table["status"] == "demo").any():
        st.error("Demo data detected in the registry - this should never happen.")
    else:
        st.success("No demo data is used anywhere in the app.")

    missing = table[~table["present"]]
    if not missing.empty:
        st.subheader("Missing tables")
        for row in missing.itertuples():
            st.markdown(f"- **{row.table}** - {row.seasons}")


def render_sixers_diagnosis() -> None:
    """Render the Sixers roster diagnosis page."""
    st.title("Sixers Roster Diagnosis")
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
        "Compare against", sorted(gaps["comparison_group_label"].dropna().unique())
    )
    view = gaps[gaps["comparison_group_label"].eq(group)].sort_values(
        "severity_score", ascending=False
    )
    chart = view.dropna(subset=["severity_score"]).set_index("category")
    chart = chart["severity_score"]
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

    _render_roster_reference()


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

        phi = fingerprints[fingerprints["team_abbr"].astype(str).eq("PHI")]
        if not phi.empty:
            latest_phi = phi.sort_values("season").iloc[-1]
            benchmark = summary.copy()
            benchmark["PHI_latest"] = benchmark["feature"].map(
                lambda col: latest_phi.get(col)
            )
            benchmark["gap_vs_contender_average"] = pd.to_numeric(
                benchmark["PHI_latest"], errors="coerce"
            ) - pd.to_numeric(benchmark["contender_average"], errors="coerce")
            st.subheader("PHI vs contender benchmarks")
            st.dataframe(benchmark, use_container_width=True, hide_index=True)

    st.subheader("Tier definitions")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "tier": 0,
                    "playoff_tier": "missed playoffs",
                    "quality_tier": "bottom 10 team",
                },
                {
                    "tier": 1,
                    "playoff_tier": "lost first round",
                    "quality_tier": "below average",
                },
                {
                    "tier": 2,
                    "playoff_tier": "lost second round",
                    "quality_tier": "average / play-in",
                },
                {
                    "tier": 3,
                    "playoff_tier": "lost conference finals",
                    "quality_tier": "playoff-level",
                },
                {
                    "tier": 4,
                    "playoff_tier": "lost finals",
                    "quality_tier": "top-10 net rating",
                },
                {
                    "tier": 5,
                    "playoff_tier": "champion",
                    "quality_tier": "top-5 / elite",
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

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
        definitions = (
            archetypes[["cluster_name"]]
            .dropna()
            .drop_duplicates()
            .rename(columns={"cluster_name": "roster_archetype"})
        )
        definitions["definition"] = "Clustered from team fingerprint features."
        st.dataframe(definitions, use_container_width=True, hide_index=True)

    st.subheader("Score glossary")
    for explanation in all_explanations():
        with st.expander(explanation.label):
            st.markdown(explanation.to_markdown())


def render_realistic_board() -> None:
    """Render the realistic target board with the full filter set."""
    st.title("Realistic Target Board")
    st.caption(
        "Free agents and tradeable players only. No current Sixers, no stars, no "
        "missing-contract players. At most 10 Priority targets."
    )
    _render_board("candidate_fit_rankings_realistic", with_filters=True)


def render_free_agent_board() -> None:
    """Render the free-agent-only board."""
    st.title("Free Agent Board")
    st.caption("Free agents, minimum, MLE, and likely-FA candidates only.")
    _render_board("candidate_fit_rankings_free_agents", with_filters=True)


def render_trade_board() -> None:
    """Render the trade-target-only board."""
    st.title("Trade Target Board")
    st.caption("Realistic, expensive, and rookie-scale trade targets only.")
    _render_board("candidate_fit_rankings_trade_targets", with_filters=True)


def render_watchlist() -> None:
    """Render the unrealistic watchlist (theoretical fit, not recommendations)."""
    st.title("Unrealistic Watchlist")
    st.error(
        "**Theoretical fit only - NOT recommendations.** These are stars on max "
        "deals, untouchable young core pieces, and players with no matched contract. "
        "They are shown for context, not as acquisition targets."
    )
    _render_board("candidate_fit_rankings_watchlist", with_filters=False)


def render_player_detail() -> None:
    """Render a single-candidate deep dive with role + core comparison."""
    st.title("Player Detail")
    if missing_warning("candidate_fit_rankings_all"):
        return
    candidates = load("candidate_fit_rankings_all")
    names = candidates["player_name"].astype(str).sort_values().tolist()
    selected = st.selectbox("Candidate", names)
    row = candidates[candidates["player_name"].astype(str).eq(selected)].iloc[0]

    st.markdown(
        f"**{selected}** - {row.get('current_team', '')} | "
        f"{row.get('role_archetype', '')} | `{row.get('candidate_type', '')}`"
    )
    st.markdown(f"**Recommendation:** {row.get('recommendation', 'n/a')}")

    cols = st.columns(5)
    cols[0].metric("Final fit", _fmt(row.get("final_fit")))
    cols[1].metric("Need match", _fmt(row.get("need_match")))
    cols[2].metric("Contender gain", _fmt(row.get("contender_gain")))
    cols[3].metric("Portability", _fmt(row.get("portability")))
    risk_label = f"{_fmt(row.get('risk_score'))} ({row.get('risk_tier', '')})"
    cols[4].metric("Risk", risk_label)

    breakdown = pd.DataFrame(
        {
            "component": [
                "need_match",
                "contender_gain",
                "portability",
                "contract_value",
                "acquisition_feasibility",
                "risk_score",
            ],
            "score": [
                _num(row.get(c))
                for c in (
                    "need_match",
                    "contender_gain",
                    "portability",
                    "contract_value",
                    "acquisition_feasibility",
                    "risk_score",
                )
            ],
        }
    ).dropna()
    if not breakdown.empty:
        st.bar_chart(breakdown.set_index("component")["score"])

    st.subheader("Why he fits")
    _bullets(str(row.get("why_fit", "")))
    st.markdown(f"**Role on the Sixers:** {row.get('role_on_sixers', 'n/a')}")
    st.markdown(f"**Gaps addressed:** {row.get('gaps_addressed', 'none')}")
    _render_gap_scores(row.get("gap_specific_scores"))

    st.subheader("Why he may not fit")
    _bullets(str(row.get("concerns", "")))

    st.subheader("Acquisition & contract")
    st.markdown(f"- **Feasibility:** {row.get('acquisition_feasibility', 'n/a')}")
    st.markdown(f"- **Salary:** {row.get('salary_context', 'n/a')}")
    st.markdown(f"- **Portability:** {row.get('portability_summary', 'n/a')}")
    st.markdown(f"- **Risk:** {row.get('risk_summary', 'n/a')}")

    _render_core_comparison(selected)

    st.subheader("Data sources & confidence")
    st.markdown(f"- **Sources:** {row.get('data_sources', 'n/a')}")
    confidence = row.get("explanation_confidence", "n/a")
    st.markdown(f"- **Explanation confidence:** {confidence}")
    flags = str(row.get("missing_data_flags", "none"))
    if flags and flags != "none":
        st.warning(f"Missing data: {flags}")
    else:
        st.success("No missing-data flags for this candidate.")


def render_transaction_review() -> None:
    """Render candidates whose acquisition status may be stale."""
    st.title("Transaction Review")
    st.caption(
        "Candidates matched to recent status-changing transactions, source conflicts, "
        "or manual-review freshness flags. These rows should be checked before being "
        "treated as current acquisition targets."
    )
    if missing_warning("candidate_fit_rankings_all"):
        return
    board = load("candidate_fit_rankings_all")
    status_col = "candidate_status_freshness"
    if status_col not in board.columns:
        st.error(
            "Candidate rankings do not include transaction freshness. Run "
            "`python scripts/refresh_transactions.py`, then rebuild the candidate "
            "universe and rankings."
        )
        return
    review = board[
        board[status_col].isin(
            [
                "stale_needs_review",
                "conflict_between_sources",
                "manual_verification_required",
            ]
        )
    ].copy()
    cols = [
        c
        for c in (
            "player_name",
            "current_team",
            "candidate_type",
            "recommendation",
            "final_fit",
            "candidate_status_freshness",
            "transaction_review_reason",
            "latest_transaction_date",
            "latest_transaction_type",
            "latest_transaction_description",
            "salary_pulled_at",
            "transaction_source",
        )
        if c in review.columns
    ]
    if review.empty:
        st.success("No candidate currently requires transaction review.")
    else:
        st.dataframe(
            review.sort_values("final_fit", ascending=False).loc[:, cols],
            use_container_width=True,
            hide_index=True,
        )

    if not missing_warning("transactions"):
        transactions = load("transactions")
        st.subheader("Recent transaction feed")
        tx_cols = [
            c
            for c in (
                "transaction_date",
                "player_name",
                "team_abbr",
                "from_team_abbr",
                "transaction_type",
                "description",
                "source_url",
                "pulled_at",
            )
            if c in transactions.columns
        ]
        st.dataframe(
            transactions.sort_values("transaction_date", ascending=False).loc[
                :, tx_cols
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_model_diagnostics() -> None:
    """Render saturation/risk/portability/contract distributions + suspect picks."""
    st.title("Model Diagnostics")
    st.caption(
        "Health checks on the scoring model: a good model spreads its scores instead "
        "of saturating, and flags its own least-trustworthy suggestions."
    )
    if missing_warning("candidate_fit_rankings_all"):
        return
    board = load("candidate_fit_rankings_all")
    realistic = load("candidate_fit_rankings_realistic")

    cols = st.columns(4)
    cols[0].metric(
        "contract_value >= 95",
        _share(board, "contract_value", 95),
        help="Target < 10%",
    )
    cols[1].metric(
        "portability >= 95",
        _share(board, "portability", 95),
        help="Target < 5%",
    )
    cols[2].metric(
        "Most common risk", _mode_share(board, "risk_score"), help="Target < 50%"
    )
    priority_n = int((realistic["recommendation"] == PRIORITY_LABEL).sum())
    cols[3].metric("Priority targets", f"{priority_n}/10")

    edges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    labels = [f"{lo}-{hi}" for lo, hi in zip(edges[:-1], edges[1:], strict=True)]
    for column in ("final_fit", "contract_value", "portability", "risk_score"):
        if column in board.columns:
            st.subheader(f"{column} distribution")
            binned = pd.cut(
                pd.to_numeric(board[column], errors="coerce"),
                bins=edges,
                labels=labels,
                include_lowest=True,
            )
            counts = binned.value_counts().reindex(labels).fillna(0)
            st.bar_chart(counts)

    st.subheader("Risk tiers")
    if "risk_tier" in board.columns:
        st.bar_chart(board["risk_tier"].value_counts())

    st.subheader("Self-flagged suspect suggestions")
    st.caption(
        "Realistic candidates with a high fit but a reason to doubt it - thin "
        "minutes, low explanation confidence, or missing data."
    )
    suspect = realistic.copy()
    suspect["minutes_proxy"] = pd.to_numeric(
        suspect.get("contender_gain"), errors="coerce"
    )
    flagged = suspect[
        (pd.to_numeric(suspect["final_fit"], errors="coerce") >= 60)
        & (
            (suspect.get("explanation_confidence") == "low")
            | (suspect.get("missing_data_flags", "none").fillna("none") != "none")
            | (suspect.get("risk_tier") == "Unknown")
        )
    ]
    if flagged.empty:
        st.success("No high-fit realistic candidate is currently self-flagged.")
    else:
        st.dataframe(
            flagged.sort_values("final_fit", ascending=False).loc[
                :,
                [
                    "player_name",
                    "final_fit",
                    "explanation_confidence",
                    "risk_tier",
                    "missing_data_flags",
                ],
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Validation warnings")
    validation_path = REGISTRY_BY_KEY["candidate_fit_rankings_all"].path.parent / (
        "target_board_validation.md"
    )
    if validation_path.exists():
        text = validation_path.read_text(encoding="utf-8")
        if "**FAIL**" in text:
            st.error("Target-board validation has failures.")
        else:
            st.success("Target-board validation report is passing.")
        st.markdown(text)
    else:
        st.warning(
            "No cached target-board validation report found. Run "
            "`python scripts/validate_target_board.py`."
        )


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
    summary_path = (
        REGISTRY_BY_KEY["backtest_rankings"].path.parent / "backtest_summary.md"
    )
    if summary_path.exists():
        st.markdown(summary_path.read_text(encoding="utf-8"))
    results_path = summary_path.with_name("backtest_results.json")
    if results_path.exists():
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        overall = payload.get("overall", {})
        if overall:
            rows = [
                {"method": method, **values}
                for method, values in overall.items()
                if isinstance(values, dict)
            ]
            st.subheader("Fit model vs baselines")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        contract = payload.get("metrics", {}).get("contract_value", {})
        if contract.get("status") == "evaluated_separately":
            st.subheader("Contract-value backtest")
            st.json(contract)
        else:
            st.warning(
                "Historical salary coverage is missing for this run, so contract "
                "surplus and free-agent-specific backtests are not shown."
            )

    if "candidate_type" in rankings.columns:
        counts = rankings["candidate_type"].value_counts()
        st.subheader("Historical candidate scope")
        st.bar_chart(counts)
        if set(counts.index) == {"historical_offseason_candidate"}:
            st.info(
                "Historical realistic-board and free-agent splits require sourced "
                "offseason candidate status. This run uses the non-PHI historical "
                "candidate universe and does not infer free-agent or trade status."
            )
    if {"fit_score", "next_season_value"}.issubset(rankings.columns):
        st.subheader("Fit score vs next-season value")
        st.scatter_chart(rankings, x="fit_score", y="next_season_value")


# ----------------------------------------------------------------------------
# Board rendering
# ----------------------------------------------------------------------------
def _render_board(key: str, *, with_filters: bool) -> None:
    if missing_warning(key):
        return
    board = load(key)
    if board.empty:
        st.info("No candidates in this board.")
        return
    _candidate_source_note(board)

    filtered = _board_filters(board) if with_filters else board
    display = [c for c in BOARD_TABLE_COLUMNS if c in filtered.columns]
    st.dataframe(
        filtered.sort_values("final_fit", ascending=False).loc[:, display],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(filtered)} of {len(board)} candidates shown.")

    st.subheader("Top candidates, explained")
    for row in filtered.sort_values("final_fit", ascending=False).head(8).itertuples():
        header = (
            f"{row.player_name} ({getattr(row, 'current_team', '')}) - "
            f"fit {getattr(row, 'final_fit', 0):.1f} - "
            f"{getattr(row, 'recommendation', '')}"
        )
        with st.expander(header):
            st.markdown(f"**Why he fits:** {getattr(row, 'why_fit', '')}")
            st.markdown(f"**Role on the Sixers:** {getattr(row, 'role_on_sixers', '')}")
            st.markdown(f"**Concerns:** {getattr(row, 'concerns', '')}")
            st.markdown(f"**Gaps addressed:** {getattr(row, 'gaps_addressed', '')}")
            st.markdown(f"**Salary context:** {getattr(row, 'salary_context', '')}")
            st.markdown(f"**Acquisition:** {getattr(row, 'acquisition_summary', '')}")
            st.markdown(f"**Risk:** {getattr(row, 'risk_summary', '')}")
            st.markdown(f"**Sources:** {getattr(row, 'data_sources', '')}")
            flags = getattr(row, "missing_data_flags", "none")
            st.markdown(f"**Missing data:** {flags}")
            st.caption(
                f"{getattr(row, 'acquisition_feasibility', '')} "
                f"{getattr(row, 'salary_context', '')}"
            )


def _board_filters(board: pd.DataFrame) -> pd.DataFrame:
    filtered = board.copy()
    columns = st.columns(3)
    with columns[0]:
        filtered = _multiselect_filter(filtered, "candidate_type", "Acquisition lane")
        filtered = _multiselect_filter(filtered, "position", "Position")
    with columns[1]:
        filtered = _multiselect_filter(filtered, "role_archetype", "Archetype")
        filtered = _multiselect_filter(filtered, "risk_tier", "Risk tier")
    with columns[2]:
        filtered = _multiselect_filter(filtered, "recommendation", "Recommendation")
        filtered = _multiselect_filter(filtered, "salary_bucket", "Salary bucket")
        salary_column = (
            "cap_hit_millions"
            if "cap_hit_millions" in filtered.columns
            else "salary_millions"
            if "salary_millions" in filtered.columns
            else None
        )
        if salary_column is not None:
            bucket = st.select_slider(
                "Max salary ($M)",
                options=[2, 5, 10, 15, 20, 25, 35, 65],
                value=65,
            )
            salary = pd.to_numeric(filtered[salary_column], errors="coerce")
            filtered = filtered[salary.isna() | (salary <= bucket)]
    return filtered


def _multiselect_filter(frame: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    if column not in frame.columns:
        return frame
    options = sorted(frame[column].dropna().astype(str).unique())
    if not options:
        return frame
    chosen = st.multiselect(label, options, default=options)
    if chosen:
        return frame[frame[column].astype(str).isin(chosen)]
    return frame


def _render_roster_reference() -> None:
    reference = load("current_roster_reference")
    if reference.empty:
        return
    st.subheader("Current Sixers roster (reference, off the acquisition board)")
    cols = [
        c
        for c in (
            "player_name",
            "position",
            "role_archetype",
            "salary_millions",
            "cap_hit_millions",
            "contract_status",
            "quality_percentile",
        )
        if c in reference.columns
    ]
    sort_col = next(
        (
            column
            for column in ("salary_millions", "cap_hit_millions")
            if column in cols
        ),
        None,
    )
    view = reference.loc[:, cols]
    if sort_col is not None:
        view = view.sort_values(sort_col, ascending=False)
    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
    )


def _render_core_comparison(selected: str) -> None:
    roles = load("player_roles")
    if roles.empty or "role_archetype" not in roles.columns:
        return
    dims = [
        "spacing_score",
        "movement_shooting_score",
        "creation_score",
        "wing_defense_proxy",
        "rim_protection_proxy",
        "rebounding_score",
    ]
    dims = [d for d in dims if d in roles.columns]
    names = [selected, *PHI_CORE]
    view = roles[roles["player_name"].astype(str).isin(names)]
    if view.empty or not dims:
        return
    st.subheader("Role next to the Sixers core")
    pivot = view.set_index("player_name")[dims]
    st.dataframe(pivot, use_container_width=True)


def _render_gap_scores(value: Any) -> None:
    try:
        parsed = json.loads(value) if isinstance(value, str) and value else {}
    except json.JSONDecodeError:
        parsed = {}
    if parsed:
        st.bar_chart(pd.Series(parsed, name="gap fit"))


# ----------------------------------------------------------------------------
# Sidebar + helpers
# ----------------------------------------------------------------------------
def _real_mode_banner(real_data_mode: bool) -> None:
    if real_data_mode:
        st.sidebar.success("REAL_DATA_MODE: on (no demo data)")
    else:
        st.sidebar.error(
            "REAL_DATA_MODE: OFF - demo data may appear. Set REAL_DATA_MODE=true."
        )


def _freshness_sidebar() -> None:
    summaries = [s for s in summarize_freshness() if s.exists and s.pulled_at]
    if summaries:
        latest = max(s.pulled_at for s in summaries)
        st.sidebar.caption(f"Data last refreshed: {latest}")
    st.sidebar.caption(f"Refresh with: `{REFRESH_COMMAND}`")


def _missing_data_sidebar() -> None:
    missing = _missing_required()
    if missing:
        st.sidebar.warning("Missing: " + ", ".join(missing))


def _missing_required() -> list[str]:
    return [
        REGISTRY_BY_KEY[key].label
        for key in REQUIRED_KEYS
        if not REGISTRY_BY_KEY[key].path.exists()
    ]


def _candidate_source_note(board: pd.DataFrame) -> None:
    st.info(
        "Candidates are real nba_api players. Salaries: real Basketball-Reference "
        "contracts where matched. Roles: real bio + tracking. Nothing is fetched live."
    )


def _bullets(text: str) -> None:
    parts = [
        item.strip(" -.")
        for chunk in str(text).split("\n")
        for item in chunk.split(";")
        if item.strip(" -.")
    ]
    if not parts:
        st.write("No explanation available.")
        return
    for part in parts:
        st.markdown(f"- {part}")


def _share(frame: pd.DataFrame, column: str, threshold: float) -> str:
    if column not in frame.columns or frame.empty:
        return "n/a"
    values = pd.to_numeric(frame[column], errors="coerce")
    return f"{(values >= threshold).mean() * 100:.1f}%"


def _mode_share(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns or frame.empty:
        return "n/a"
    counts = (
        pd.to_numeric(frame[column], errors="coerce")
        .round(0)
        .value_counts(normalize=True)
    )
    return "n/a" if counts.empty else f"{counts.iloc[0] * 100:.1f}%"


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
