"""Tests for player playoff portability scoring."""

from __future__ import annotations

import pandas as pd

from moreymachine.features.playoff_portability import (
    add_playoff_portability_scores,
    score_player_playoff_portability,
)


def test_fake_shooter_is_penalized() -> None:
    score = score_player_playoff_portability(
        {
            "player_name": "Fake Shooter",
            "position": "SF",
            "age": 27,
            "minutes": 950,
            "usage_rate": 0.14,
            "true_shooting_percentage": 0.55,
            "three_point_attempt_rate": 0.12,
            "three_point_percentage": 0.40,
            "turnover_rate": 0.11,
            "rebound_rate": 0.05,
            "steal_rate": 0.006,
            "block_rate": 0.002,
        }
    )

    assert score.score < 55
    assert any("fake shooting" in bullet for bullet in score.bullets)


def test_low_usage_high_volume_shooter_scores_well() -> None:
    score = score_player_playoff_portability(
        {
            "player_name": "Portable Spacer",
            "position": "SG",
            "age": 28,
            "minutes": 1900,
            "usage_rate": 0.15,
            "true_shooting_percentage": 0.61,
            "three_point_attempt_rate": 0.52,
            "three_point_percentage": 0.39,
            "turnover_rate": 0.08,
            "assist_rate": 0.13,
            "rebound_rate": 0.08,
            "steal_rate": 0.017,
            "block_rate": 0.004,
            "defensive_box_plus_minus": 0.3,
        }
    )

    assert score.score >= 85
    assert any("three-point volume" in bullet for bullet in score.bullets)
    assert any("Low-usage role" in bullet for bullet in score.bullets)


def test_inefficient_high_usage_scorer_is_penalized() -> None:
    score = score_player_playoff_portability(
        {
            "player_name": "Tough Shot Scorer",
            "position": "PG",
            "age": 29,
            "minutes": 1700,
            "usage_rate": 0.33,
            "true_shooting_percentage": 0.50,
            "three_point_attempt_rate": 0.27,
            "three_point_percentage": 0.31,
            "turnover_rate": 0.18,
            "assist_rate": 0.09,
            "rebound_rate": 0.04,
            "steal_rate": 0.006,
            "block_rate": 0.001,
            "defensive_box_plus_minus": -1.4,
        }
    )

    assert score.score <= 25
    assert any(
        "High-usage scoring is inefficient" in bullet for bullet in score.bullets
    )
    assert any("Turnover rate is vulnerable" in bullet for bullet in score.bullets)


def test_add_playoff_portability_scores_appends_explanations() -> None:
    players = pd.DataFrame(
        [
            {
                "player_name": "Portable Spacer",
                "position": "SG",
                "age": 28,
                "minutes": 1900,
                "usage_rate": 0.15,
                "true_shooting_percentage": 0.61,
                "three_point_attempt_rate": 0.52,
                "three_point_percentage": 0.39,
                "turnover_rate": 0.08,
                "assist_rate": 0.13,
                "steal_rate": 0.017,
            },
            {
                "player_name": "Tough Shot Scorer",
                "position": "PG",
                "age": 29,
                "minutes": 1700,
                "usage_rate": 0.33,
                "true_shooting_percentage": 0.50,
                "three_point_attempt_rate": 0.27,
                "three_point_percentage": 0.31,
                "turnover_rate": 0.18,
                "defensive_box_plus_minus": -1.4,
            },
        ]
    )

    result = add_playoff_portability_scores(players)

    assert {
        "playoff_portability_score",
        "playoff_portability_bullets",
        "playoff_portability_explanation",
    }.issubset(result.columns)
    assert (
        result.loc[0, "playoff_portability_score"]
        > result.loc[1, "playoff_portability_score"]
    )
    assert result.loc[0, "playoff_portability_explanation"].startswith("- ")
