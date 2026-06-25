"""Tests for the candidate universe classification."""

from __future__ import annotations

import pandas as pd

from moreymachine.features.candidate_universe import (
    PHI_ROSTER_2025_26,
    REALISTIC_TYPES,
    UNIVERSE_COLUMNS,
    board_membership,
    classify_candidate_type,
    classify_candidate_universe,
)


def _player_seasons() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": ["2025-26"] * 6,
            "player_id": [1, 2, 3, 4, 5, 6],
            "player_name": [
                "Joel Embiid",  # current Sixer
                "Star Maxsalary",  # >= 35M -> star_unrealistic
                "Cheap Rookie",  # rookie scale trade target
                "Mid Vet",  # realistic trade target
                "Expiring Min",  # minimum candidate (expiring, <2.6M)
                "No Contract Guy",  # missing_contract_status
            ],
            "team_abbr": ["PHI", "OKC", "SAS", "DEN", "LAL", "BKN"],
            "age": [31, 27, 22, 28, 30, 24],
            "minutes": [2000, 2400, 1500, 1800, 900, 600],
            "pts": [30, 28, 12, 16, 8, 6],
            "usage_rate": [0.34, 0.33, 0.18, 0.21, 0.14, 0.16],
            "true_shooting": [0.62, 0.60, 0.55, 0.57, 0.54, 0.52],
        }
    )


def _contracts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5],
            "salary": [
                50_000_000,
                40_000_000,
                3_000_000,
                18_000_000,
                2_000_000,
            ],
            "contract_status": [
                "under_contract",
                "under_contract",
                "under_contract",
                "under_contract",
                "expiring",
            ],
            "years_remaining": [3, 4, 2, 2, 1],
            "source": ["Basketball-Reference"] * 5,
        }
    )


def _bio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5, 6],
            "draft_year": [2014, 2018, 2024, 2017, 2015, 2023],
            "position": ["C", "G", "F", "F", "G", "G"],
        }
    )


def test_classify_universe_assigns_exactly_one_type_per_player() -> None:
    universe = classify_candidate_universe(
        player_seasons=_player_seasons(),
        contracts=_contracts(),
        player_bio=_bio(),
    )

    assert list(universe.columns) == list(UNIVERSE_COLUMNS)
    assert len(universe) == 6
    # One row per player, one candidate_type each.
    assert universe["player_id"].is_unique
    assert universe["candidate_type"].notna().all()


def test_current_sixers_are_classified_and_off_acquisition_board() -> None:
    universe = classify_candidate_universe(
        player_seasons=_player_seasons(),
        contracts=_contracts(),
        player_bio=_bio(),
    )
    embiid = universe[universe["player_name"] == "Joel Embiid"].iloc[0]
    assert embiid["candidate_type"] == "current_sixers_player"
    assert not embiid["on_acquisition_board"]


def test_expected_types_for_each_salary_lane() -> None:
    frame = classify_candidate_universe(
        player_seasons=_player_seasons(),
        contracts=_contracts(),
        player_bio=_bio(),
    )
    universe = frame.set_index("player_name")["candidate_type"].to_dict()

    assert universe["Star Maxsalary"] == "star_unrealistic"
    assert universe["Cheap Rookie"] == "rookie_scale_trade_target"
    assert universe["Mid Vet"] == "realistic_trade_target"
    assert universe["Expiring Min"] == "minimum_candidate"
    assert universe["No Contract Guy"] == "missing_contract_status"


def test_classify_candidate_type_respects_manual_override() -> None:
    row = {
        "player_name": "Anyone",
        "salary_millions": 8.0,
        "contract_status": "expiring",
    }
    candidate_type, _ = classify_candidate_type(row, manual_override="manual_watchlist")
    assert candidate_type == "manual_watchlist"


def test_current_sixer_name_beats_manual_override() -> None:
    sixer = next(iter(PHI_ROSTER_2025_26))
    candidate_type, _ = classify_candidate_type(
        {"player_name": sixer}, manual_override="manual_watchlist"
    )
    assert candidate_type == "current_sixers_player"


def test_board_membership_flags_match_realistic_types() -> None:
    for candidate_type in REALISTIC_TYPES:
        flags = board_membership(candidate_type)
        assert flags["realistic_board"]
        assert flags["on_acquisition_board"]
    star = board_membership("star_unrealistic")
    assert not star["realistic_board"]
    assert not star["trade_board"]
