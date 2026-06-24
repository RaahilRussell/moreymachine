"""Tests for roster gap analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from moreymachine.features.roster_gaps import (
    COMPARISON_GROUP_LABELS,
    GAP_CATEGORIES,
    build_roster_gaps,
    create_roster_gap_report,
    render_roster_gap_markdown,
)


def test_create_roster_gap_report_returns_gap_rows() -> None:
    gaps = create_roster_gap_report(
        _toy_fingerprints(),
        roster_archetypes=_toy_archetypes(),
        target_team="PHI",
    )

    assert len(gaps) == len(COMPARISON_GROUP_LABELS) * len(GAP_CATEGORIES)
    assert set(gaps["comparison_group"]) == set(COMPARISON_GROUP_LABELS)
    assert set(gaps["category_key"]) == {category.key for category in GAP_CATEGORIES}
    assert gaps["target_season"].unique().tolist() == ["2022-23"]

    defense = gaps.loc[
        (gaps["comparison_group"] == "conference_finals_or_better")
        & (gaps["category_key"] == "defense")
    ].iloc[0]
    assert defense["target_value"] == 114.0
    assert defense["elite_average"] < defense["target_value"]
    assert defense["gap_size"] > 0
    assert defense["severity_score"] > 0
    assert defense["percentile"] < 50
    assert "defensive_rating" in defense["source_columns"]


def test_same_archetype_group_uses_successful_cluster_peers() -> None:
    gaps = create_roster_gap_report(
        _toy_fingerprints(),
        roster_archetypes=_toy_archetypes(),
        target_team="PHI",
        target_season="2022-23",
    )

    same_archetype = gaps.loc[
        gaps["comparison_group"] == "same_roster_archetype_successful"
    ]
    assert same_archetype["comparison_count"].unique().tolist() == [2]


def test_missing_optional_category_still_reports_explanation() -> None:
    fingerprints = _toy_fingerprints().drop(
        columns=["bench_depth", "top_usage_concentration"]
    )
    gaps = create_roster_gap_report(
        fingerprints,
        roster_archetypes=_toy_archetypes(),
        target_team="PHI",
    )

    bench = gaps.loc[
        (gaps["comparison_group"] == "conference_finals_or_better")
        & (gaps["category_key"] == "bench_rotation_depth")
    ].iloc[0]
    assert pd.isna(bench["target_value"])
    assert bench["source_columns"] == ""
    assert "No source column" in bench["explanation"]


def test_render_roster_gap_markdown_includes_sections() -> None:
    gaps = create_roster_gap_report(
        _toy_fingerprints(),
        roster_archetypes=_toy_archetypes(),
        target_team="PHI",
    )

    markdown = render_roster_gap_markdown(gaps)

    assert "# PHI Roster Gap Report" in markdown
    assert "## Conference Finals or Better" in markdown
    assert "| Category | Target | Elite Avg | Percentile | Gap | Severity |" in markdown
    assert "Shooting Pressure" in markdown


def test_build_roster_gaps_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "team_fingerprints.parquet"
    archetypes_path = tmp_path / "team_roster_archetypes.parquet"
    output_path = tmp_path / "phi_roster_gaps.parquet"
    markdown_path = tmp_path / "phi_roster_gaps.md"
    _toy_fingerprints().to_parquet(input_path, index=False)
    _toy_archetypes().to_parquet(archetypes_path, index=False)

    result = build_roster_gaps(
        input_path=input_path,
        roster_archetypes_path=archetypes_path,
        output_path=output_path,
        markdown_path=markdown_path,
        target_team="PHI",
    )

    assert result.rows == len(COMPARISON_GROUP_LABELS) * len(GAP_CATEGORIES)
    assert result.target_team == "PHI"
    assert result.target_season == "2022-23"
    assert result.output_path == output_path
    assert result.markdown_path == markdown_path
    assert len(pd.read_parquet(output_path)) == result.rows
    assert "# PHI Roster Gap Report" in markdown_path.read_text(encoding="utf-8")


def _toy_fingerprints() -> pd.DataFrame:
    rows = [
        _team_row("2021-22", "GSW", 7.5, 106.0, 0.72, 3, True, 0.40, 0.46, 8.5, 0.30),
        _team_row("2021-22", "PHX", 6.8, 108.0, 0.68, 2, False, 0.38, 0.40, 8.0, 0.34),
        _team_row("2021-22", "MIL", 5.8, 109.0, 0.66, 3, True, 0.37, 0.41, 7.5, 0.36),
        _team_row("2021-22", "DAL", 4.9, 110.0, 0.61, 3, True, 0.36, 0.39, 7.0, 0.42),
        _team_row("2021-22", "MEM", 4.1, 111.0, 0.58, 2, False, 0.35, 0.37, 8.0, 0.35),
        _team_row("2021-22", "ATL", 1.0, 114.0, 0.55, 1, False, 0.34, 0.38, 6.0, 0.39),
        _team_row("2021-22", "LAL", -2.0, 116.0, 0.50, 0, False, 0.33, 0.35, 5.5, 0.44),
        _team_row("2021-22", "SAS", -3.0, 117.0, 0.48, 0, False, 0.32, 0.34, 6.0, 0.32),
        _team_row("2022-23", "BOS", 8.0, 108.0, 0.73, 3, True, 0.39, 0.45, 8.5, 0.31),
        _team_row("2022-23", "DEN", 7.0, 110.0, 0.70, 5, True, 0.38, 0.40, 7.5, 0.37),
        _team_row("2022-23", "MIA", 5.0, 109.0, 0.62, 3, True, 0.35, 0.38, 7.0, 0.33),
        _team_row("2022-23", "CLE", 4.0, 107.0, 0.60, 2, False, 0.36, 0.37, 7.0, 0.35),
        _team_row("2022-23", "PHI", 3.0, 114.0, 0.55, 2, False, 0.36, 0.39, 6.0, 0.42),
        _team_row("2022-23", "NYK", 2.0, 113.0, 0.57, 1, False, 0.35, 0.41, 7.5, 0.34),
        _team_row("2022-23", "TOR", -1.0, 115.0, 0.52, 0, False, 0.34, 0.36, 6.5, 0.38),
        _team_row("2022-23", "CHI", -2.5, 116.0, 0.49, 0, False, 0.33, 0.34, 5.5, 0.40),
    ]
    return pd.DataFrame(rows)


def _team_row(
    season: str,
    team_abbr: str,
    net_rating: float,
    defensive_rating: float,
    shooting_pressure: float,
    playoff_tier: int,
    deep_playoff: bool,
    three_point_percentage: float,
    three_point_attempt_rate: float,
    bench_depth: float,
    top_usage_concentration: float,
) -> dict[str, object]:
    return {
        "season": season,
        "team_abbr": team_abbr,
        "team_id": f"{season}-{team_abbr}",
        "team_name": f"{team_abbr} Team",
        "offensive_rating": defensive_rating + net_rating,
        "defensive_rating": defensive_rating,
        "net_rating": net_rating,
        "pace": 96.0 + (net_rating / 2),
        "efg_percentage": shooting_pressure - 0.15,
        "turnover_percentage": 0.12 + max(0.0, 4.0 - net_rating) / 100,
        "offensive_rebounding_percentage": 0.23 + max(0.0, net_rating) / 200,
        "defensive_rebounding_percentage": 0.70 + max(0.0, net_rating) / 150,
        "free_throw_rate": 0.20 + max(0.0, net_rating) / 200,
        "three_point_attempt_rate": three_point_attempt_rate,
        "three_point_percentage": three_point_percentage,
        "estimated_shooting_pressure": shooting_pressure,
        "estimated_possession_control": 0.50 + max(0.0, net_rating) / 20,
        "estimated_two_way_balance": 0.52 + max(0.0, net_rating) / 16,
        "bench_depth": bench_depth,
        "top_usage_concentration": top_usage_concentration,
        "playoff_tier": playoff_tier,
        "quality_tier": 4 if net_rating >= 4 else 3 if net_rating >= 2 else 1,
        "deep_playoff": deep_playoff,
        "finals_team": playoff_tier >= 4,
        "champion": playoff_tier == 5,
    }


def _toy_archetypes() -> pd.DataFrame:
    clusters = {
        "PHI": 1,
        "BOS": 1,
        "GSW": 1,
        "DEN": 2,
        "MIA": 2,
        "MIL": 2,
        "PHX": 0,
        "DAL": 0,
        "MEM": 0,
        "ATL": 3,
        "LAL": 3,
        "SAS": 3,
        "CLE": 4,
        "NYK": 4,
        "TOR": 4,
        "CHI": 4,
    }
    rows = []
    for row in _toy_fingerprints().itertuples(index=False):
        cluster_id = clusters[row.team_abbr]
        rows.append(
            {
                "season": row.season,
                "team_abbr": row.team_abbr,
                "cluster_id": cluster_id,
                "cluster_name": f"Cluster {cluster_id}",
            }
        )
    return pd.DataFrame(rows)
