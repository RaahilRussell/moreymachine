"""Tests for the candidate universe classification + acquisition feasibility."""

from __future__ import annotations

import pandas as pd

from moreymachine.features.candidate_universe import (
    PHI_ROSTER_2025_26,
    REALISTIC_TYPES,
    UNIVERSE_COLUMNS,
    acquisition_feasibility,
    board_membership,
    classify_candidate_type,
    classify_candidate_universe,
)


def _player_seasons() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["2025-26"] * 7,
            "player_id": [1, 2, 3, 4, 5, 6, 7],
            "player_name": [
                "Joel Embiid",  # current Sixer
                "Maxer Star",  # max_or_near_max -> star_unrealistic
                "Cheap Rookie",  # rookie_scale -> rookie_scale_trade_target
                "Mid Vet",  # signed_long_term -> realistic_trade_target
                "Expiring Min",  # minimum_contract -> minimum_candidate
                "No Contract Guy",  # no contract -> missing_contract_status
                "Real UFA",  # unrestricted_free_agent
            ],
            "team_abbr": ["PHI", "OKC", "SAS", "DEN", "LAL", "BKN", "MIA"],
            "age": [31, 27, 22, 28, 30, 24, 29],
            "minutes": [2000, 2400, 1500, 1800, 900, 600, 1700],
            "pts": [30, 28, 12, 16, 8, 6, 14],
            "usage_rate": [0.34, 0.33, 0.18, 0.21, 0.14, 0.16, 0.2],
            "true_shooting": [0.62, 0.60, 0.55, 0.57, 0.54, 0.52, 0.58],
        }
    )


def _contracts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5, 7],
            "cap_hit_millions": [55.0, 50.0, 5.0, 18.0, 2.0, 9.0],
            "base_salary_millions": [None] * 6,
            "contract_aav_millions": [None] * 6,
            "contract_status": [
                "max_or_near_max",
                "max_or_near_max",
                "rookie_scale",
                "signed_long_term",
                "minimum_contract",
                "unrestricted_free_agent",
            ],
            "free_agent_year": [2029, 2028, 2027, 2028, 2026, 2026],
            "years_remaining": [3, 4, 2, 2, 1, 0],
            "option_status": ["none"] * 6,
            "extension_status": ["unknown"] * 6,
            "salary_source": ["bbref"] * 6,
        }
    )


def _bio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5, 6, 7],
            "draft_year": [2014, 2018, 2024, 2017, 2015, 2023, 2016],
            "position": ["C", "G", "F", "F", "G", "G", "F"],
        }
    )


def _universe() -> pd.DataFrame:
    return classify_candidate_universe(
        player_seasons=_player_seasons(),
        contracts=_contracts(),
        player_bio=_bio(),
    )


def test_schema_and_one_type_per_player() -> None:
    universe = _universe()
    assert list(universe.columns) == list(UNIVERSE_COLUMNS)
    assert universe["player_id"].is_unique
    assert universe["candidate_type"].notna().all()
    assert universe["feasibility_tier"].notna().all()


def test_types_follow_contract_status() -> None:
    types = _universe().set_index("player_name")["candidate_type"].to_dict()
    assert types["Joel Embiid"] == "current_sixers_player"
    assert types["Maxer Star"] == "star_unrealistic"
    assert types["Cheap Rookie"] == "rookie_scale_trade_target"
    assert types["Mid Vet"] == "realistic_trade_target"
    assert types["Expiring Min"] == "minimum_candidate"
    assert types["No Contract Guy"] == "missing_contract_status"
    assert types["Real UFA"] == "unrestricted_free_agent"


def test_unknown_contract_is_not_called_a_free_agent() -> None:
    candidate_type, _ = classify_candidate_type(
        {"player_name": "Mystery", "contract_status": "unknown"}
    )
    assert candidate_type == "missing_contract_status"
    assert "free_agent" not in candidate_type


def test_current_sixer_excluded_from_acquisition_board() -> None:
    embiid = _universe().query("player_name == 'Joel Embiid'").iloc[0]
    assert not embiid["on_acquisition_board"]


def test_feasibility_score_tier_and_reason() -> None:
    score, tier, reason = acquisition_feasibility(
        {"quality_percentile": 0.5, "cap_hit_millions": 5.0},
        "unrestricted_free_agent",
    )
    assert 0 <= score <= 100
    assert tier in ("Easy", "Possible", "Difficult", "Very Difficult", "Unrealistic")
    assert reason


def test_important_trade_target_is_harder_to_acquire() -> None:
    easy, _, _ = acquisition_feasibility(
        {"quality_percentile": 0.50, "cap_hit_millions": 8.0},
        "realistic_trade_target",
    )
    hard, _, _ = acquisition_feasibility(
        {"quality_percentile": 0.95, "cap_hit_millions": 8.0},
        "realistic_trade_target",
    )
    assert hard < easy


def test_missing_contract_feasibility_is_unknown() -> None:
    _, tier, _ = acquisition_feasibility({}, "missing_contract_status")
    assert tier == "Unknown"


def test_board_membership_and_realistic_types() -> None:
    for candidate_type in REALISTIC_TYPES:
        assert board_membership(candidate_type)["realistic_board"]
    assert not board_membership("star_unrealistic")["realistic_board"]


def test_current_sixer_name_beats_override() -> None:
    sixer = next(iter(PHI_ROSTER_2025_26))
    candidate_type, _ = classify_candidate_type(
        {"player_name": sixer}, manual_override="manual_watchlist"
    )
    assert candidate_type == "current_sixers_player"
