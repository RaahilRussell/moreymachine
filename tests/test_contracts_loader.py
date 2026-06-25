"""Tests for rich contract normalization and salary semantics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moreymachine.data.contracts_loader import (
    CONTRACT_STATUS_CATEGORIES,
    RICH_CONTRACT_COLUMNS,
    _derive_status,
    _normalize,
)


def _raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_name": ["Maxer", "Minner", "Rookie", "Vet"],
            "player_id": [1, 2, 3, 4],
            "team": ["PHI", "BOS", "OKC", "DEN"],
            "salary": [50_000_000, 2_000_000, 5_000_000, 18_000_000],
            "years_remaining": [3, 1, 2, 2],
            "contract_status": [
                "under_contract",
                "expiring",
                "under_contract",
                "under_contract",
            ],
            "option_status": ["", "", "", ""],
            "source": ["bbref"] * 4,
            "pulled_at": ["2026-06-25"] * 4,
            "data_mode": ["real_scraped"] * 4,
        }
    )


def _bio() -> pd.DataFrame:
    return pd.DataFrame(
        {"player_id": [1, 2, 3, 4], "draft_year": [2014, 2016, 2024, 2017]}
    )


def test_normalize_produces_rich_schema_and_keeps_base_aav_missing() -> None:
    rich = _normalize(_raw(), bio=_bio(), season="2025-26")
    for column in ("cap_hit_millions", "base_salary_millions", "contract_aav_millions"):
        assert column in rich.columns
    # The scrape is a cap hit; base and AAV are never invented.
    assert rich["base_salary_millions"].isna().all()
    assert rich["contract_aav_millions"].isna().all()
    assert (rich["cap_hit_millions"] > 0).all()


def test_status_categories_are_from_the_allowed_set() -> None:
    rich = _normalize(_raw(), bio=_bio(), season="2025-26")
    assert set(rich["contract_status"]).issubset(set(CONTRACT_STATUS_CATEGORIES))


def test_derive_status_rules() -> None:
    assert _derive_status(cap_hit_m=50, old_status="", years_remaining=3,
                          draft_year=2014, season_start=2025) == "max_or_near_max"
    assert _derive_status(cap_hit_m=5, old_status="", years_remaining=2,
                          draft_year=2024, season_start=2025) == "rookie_scale"
    assert _derive_status(cap_hit_m=2.0, old_status="", years_remaining=1,
                          draft_year=2014, season_start=2025) == "minimum_contract"
    assert _derive_status(cap_hit_m=18, old_status="", years_remaining=3,
                          draft_year=2014, season_start=2025) == "signed_long_term"
    assert _derive_status(cap_hit_m=np.nan, old_status="", years_remaining=1,
                          draft_year=2014, season_start=2025) == "unknown"


def test_free_agent_year_is_derived_not_guessed_fa_type() -> None:
    rich = _normalize(_raw(), bio=_bio(), season="2025-26")
    minner = rich[rich["player_name"] == "Minner"].iloc[0]
    assert int(minner["free_agent_year"]) == 2026
    # Status is never silently turned into UFA/RFA from the scrape alone.
    assert "free_agent" not in minner["contract_status"]


def test_rich_columns_are_exactly_the_contract_schema() -> None:
    rich = _normalize(_raw(), bio=_bio(), season="2025-26")
    for column in RICH_CONTRACT_COLUMNS:
        assert column in rich.columns
