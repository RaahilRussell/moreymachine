"""Tests for offseason backtesting."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from moreymachine.models.backtest import (
    BASELINE_SCORE_COLUMNS,
    build_backtest,
    offseason_pairs,
    render_backtest_summary,
    run_backtest,
)


def test_offseason_pairs_use_consecutive_seasons() -> None:
    pairs = offseason_pairs(_toy_player_stats())

    assert pairs == [("2020-21", "2021-22"), ("2021-22", "2022-23")]


def test_run_backtest_outputs_rankings_and_metrics() -> None:
    rankings, metrics = run_backtest(
        player_stats=_toy_player_stats(),
        team_fingerprints=_toy_team_fingerprints(),
        player_archetypes=_toy_player_archetypes(),
        contracts=_toy_contracts(),
        target_team="PHI",
        top_k=1,
        random_state=7,
    )

    assert set(rankings["previous_season"]) == {"2020-21", "2021-22"}
    assert set(BASELINE_SCORE_COLUMNS).issubset(metrics["overall"])
    assert rankings.groupby("previous_season").head(1)["player_name"].tolist() == [
        "Portable Spacer",
        "Portable Spacer",
    ]
    assert (
        metrics["overall"]["moreymachine_fit"]["average_value_top_targets"]
        > metrics["overall"]["previous_points"]["average_value_top_targets"]
    )
    assert (
        metrics["overall"]["moreymachine_fit"]["hit_rate_top_targets"]
        >= metrics["overall"]["previous_points"]["hit_rate_top_targets"]
    )
    assert "previous_points" in metrics["average_value_of_top_targets_vs_baselines"]


def test_render_backtest_summary_includes_baselines() -> None:
    _, metrics = run_backtest(
        player_stats=_toy_player_stats(),
        team_fingerprints=_toy_team_fingerprints(),
        player_archetypes=_toy_player_archetypes(),
        contracts=_toy_contracts(),
        target_team="PHI",
        top_k=1,
    )

    summary = render_backtest_summary(metrics)

    assert "# Offseason Backtest Summary" in summary
    assert "moreymachine_fit" in summary
    assert "previous_points" in summary


def test_build_backtest_writes_outputs(tmp_path: Path) -> None:
    players_path = tmp_path / "players.parquet"
    teams_path = tmp_path / "team_fingerprints.parquet"
    archetypes_path = tmp_path / "player_archetypes.parquet"
    contracts_path = tmp_path / "contracts.csv"
    results_path = tmp_path / "backtest_results.json"
    rankings_path = tmp_path / "backtest_rankings.parquet"
    summary_path = tmp_path / "backtest_summary.md"
    _toy_player_stats().to_parquet(players_path, index=False)
    _toy_team_fingerprints().to_parquet(teams_path, index=False)
    _toy_player_archetypes().to_parquet(archetypes_path, index=False)
    _toy_contracts().to_csv(contracts_path, index=False)

    result = build_backtest(
        player_stats_path=players_path,
        team_fingerprints_path=teams_path,
        player_archetypes_path=archetypes_path,
        team_roster_archetypes_path=None,
        contracts_path=contracts_path,
        results_path=results_path,
        rankings_path=rankings_path,
        summary_path=summary_path,
        target_team="PHI",
        top_k=1,
    )

    assert result.rows > 0
    assert result.offseasons == ("after_2020-21", "after_2021-22")
    assert len(pd.read_parquet(rankings_path)) == result.rows
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert (
        payload["overall"]["moreymachine_fit"]["average_value_top_targets"] is not None
    )
    assert "Offseason Backtest Summary" in summary_path.read_text(encoding="utf-8")


def _toy_player_stats() -> pd.DataFrame:
    rows = []
    rows.extend(
        [
            _player_row(
                "2020-21",
                1,
                "Portable Spacer",
                "BKN",
                8,
                1600,
                0.14,
                0.60,
                0.52,
                0.39,
                0.08,
                0.4,
                5.0,
                1.8,
            ),
            _player_row(
                "2020-21",
                2,
                "Volume Scorer",
                "WAS",
                24,
                1800,
                0.33,
                0.50,
                0.25,
                0.31,
                0.18,
                -1.4,
                2.0,
                -0.5,
            ),
            _player_row(
                "2020-21",
                3,
                "Neutral Wing",
                "CHA",
                11,
                1200,
                0.18,
                0.55,
                0.34,
                0.35,
                0.12,
                0.0,
                3.0,
                0.2,
            ),
            _player_row(
                "2021-22",
                1,
                "Portable Spacer",
                "BKN",
                10,
                2100,
                0.15,
                0.62,
                0.54,
                0.40,
                0.08,
                1.0,
                7.0,
                3.0,
            ),
            _player_row(
                "2021-22",
                2,
                "Volume Scorer",
                "WAS",
                25,
                1300,
                0.32,
                0.49,
                0.24,
                0.30,
                0.19,
                -2.0,
                1.0,
                -1.0,
            ),
            _player_row(
                "2021-22",
                3,
                "Neutral Wing",
                "CHA",
                10,
                1400,
                0.18,
                0.56,
                0.36,
                0.36,
                0.11,
                0.1,
                3.5,
                0.4,
            ),
            _player_row(
                "2022-23",
                1,
                "Portable Spacer",
                "BKN",
                11,
                2200,
                0.16,
                0.63,
                0.55,
                0.41,
                0.07,
                1.2,
                8.0,
                3.4,
            ),
            _player_row(
                "2022-23",
                2,
                "Volume Scorer",
                "WAS",
                23,
                1000,
                0.34,
                0.48,
                0.23,
                0.29,
                0.20,
                -2.4,
                0.5,
                -1.4,
            ),
            _player_row(
                "2022-23",
                3,
                "Neutral Wing",
                "CHA",
                12,
                1500,
                0.18,
                0.56,
                0.36,
                0.36,
                0.11,
                0.2,
                4.0,
                0.6,
            ),
        ]
    )
    return pd.DataFrame(rows)


def _player_row(
    season: str,
    player_id: int,
    player_name: str,
    team: str,
    ppg: float,
    minutes: float,
    usage: float,
    ts: float,
    three_rate: float,
    three_pct: float,
    turnover: float,
    dbpm: float,
    win_shares: float,
    bpm: float,
) -> dict[str, object]:
    return {
        "season": season,
        "player_id": player_id,
        "player_name": player_name,
        "team_abbreviation": team,
        "position": "SG" if player_id == 1 else "PG" if player_id == 2 else "SF",
        "age": 28,
        "points_per_game": ppg,
        "minutes": minutes,
        "usage_rate": usage,
        "true_shooting_percentage": ts,
        "three_point_attempt_rate": three_rate,
        "three_point_percentage": three_pct,
        "turnover_rate": turnover,
        "assist_rate": 0.13 if player_id == 1 else 0.08,
        "rebound_rate": 0.08,
        "steal_rate": 0.017 if player_id == 1 else 0.006,
        "block_rate": 0.004,
        "defensive_box_plus_minus": dbpm,
        "win_shares": win_shares,
        "bpm": bpm,
        "vorp": max(0.0, bpm + 1),
    }


def _toy_team_fingerprints() -> pd.DataFrame:
    rows = []
    for season_index, season in enumerate(("2020-21", "2021-22", "2022-23")):
        rows.extend(
            [
                _team_row(season, "PHI", 2.0 + season_index, 114.0, 0.55, 2, False),
                _team_row(season, "BOS", 7.5, 108.0, 0.72, 3, True),
                _team_row(season, "DEN", 7.0, 109.0, 0.70, 5, True),
                _team_row(season, "MIA", 5.0, 110.0, 0.64, 3, True),
                _team_row(season, "MIL", 4.8, 111.0, 0.62, 2, False),
                _team_row(season, "ORL", -2.0, 118.0, 0.48, 0, False),
            ]
        )
    return pd.DataFrame(rows)


def _team_row(
    season: str,
    team: str,
    net_rating: float,
    defensive_rating: float,
    shooting_pressure: float,
    playoff_tier: int,
    deep_playoff: bool,
) -> dict[str, object]:
    return {
        "season": season,
        "team_abbr": team,
        "team_id": f"{season}-{team}",
        "team_name": f"{team} Team",
        "offensive_rating": defensive_rating + net_rating,
        "defensive_rating": defensive_rating,
        "net_rating": net_rating,
        "pace": 98.0,
        "efg_percentage": shooting_pressure - 0.15,
        "turnover_percentage": 0.13,
        "offensive_rebounding_percentage": 0.25,
        "defensive_rebounding_percentage": 0.72,
        "free_throw_rate": 0.22,
        "three_point_attempt_rate": shooting_pressure - 0.20,
        "three_point_percentage": 0.35 + (shooting_pressure / 10),
        "estimated_shooting_pressure": shooting_pressure,
        "estimated_possession_control": 0.55,
        "estimated_two_way_balance": 0.55 + (net_rating / 20),
        "playoff_tier": playoff_tier,
        "quality_tier": 4 if net_rating >= 4 else 3,
        "deep_playoff": deep_playoff,
        "finals_team": playoff_tier >= 4,
        "champion": playoff_tier == 5,
    }


def _toy_player_archetypes() -> pd.DataFrame:
    rows = []
    for season in ("2020-21", "2021-22"):
        rows.extend(
            [
                {
                    "season": season,
                    "player_id": 1,
                    "archetype_name": "Low-Usage Spacer",
                },
                {"season": season, "player_id": 2, "archetype_name": "Scoring Guard"},
                {
                    "season": season,
                    "player_id": 3,
                    "archetype_name": "Balanced Role Player",
                },
            ]
        )
    return pd.DataFrame(rows)


def _toy_contracts() -> pd.DataFrame:
    rows = []
    for season in ("2020-21", "2021-22"):
        rows.extend(
            [
                {"season": season, "player_id": 1, "estimated_salary_millions": 12},
                {"season": season, "player_id": 2, "estimated_salary_millions": 28},
                {"season": season, "player_id": 3, "estimated_salary_millions": 8},
            ]
        )
    return pd.DataFrame(rows)
