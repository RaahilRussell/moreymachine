"""Tests for transaction parsing and candidate-status freshness."""

from __future__ import annotations

import pandas as pd

from moreymachine.data.transactions import (
    classify_transaction_type,
    parse_transactions_html,
)
from moreymachine.features.candidate_universe import classify_candidate_universe


def test_parse_spotrac_transaction_rows() -> None:
    html = """
    <div id="table-wrapper">
      <ul class="list-group">
        <li class="list-group-item">
          <span>
            <a href="https://www.spotrac.com/nba/player/_/id/1/player-one">
              Player One (G)
            </a>
            <small>
              <strong>Jun 24, 2026</strong>
              - Agreed to a 4 year contract with Denver (DEN)
            </small>
          </span>
        </li>
        <li class="list-group-item">
          <span>
            <a href="https://www.spotrac.com/nba/player/_/id/2/player-two">
              Player Two (F)
            </a>
            <small>
              <strong>Jun 23, 2026</strong>
              - Traded to Miami (MIA) from Boston (BOS) for cash
            </small>
          </span>
        </li>
      </ul>
    </div>
    """

    frame = parse_transactions_html(html, source_url="https://example.test")

    assert frame["player_name"].tolist() == ["Player One", "Player Two"]
    assert frame["transaction_type"].tolist() == ["signing", "trade"]
    assert frame.loc[1, "team_abbr"] == "MIA"
    assert frame.loc[1, "from_team_abbr"] == "BOS"


def test_transaction_type_classification_covers_status_changes() -> None:
    assert classify_transaction_type("Team exercised $2M option") == "option_exercised"
    assert classify_transaction_type("Declined player option") == "option_declined"
    assert classify_transaction_type("Signed a 2 year contract") == "signing"
    assert classify_transaction_type("Signed a contract extension") == "extension"


def test_recent_signing_moves_free_agent_to_contract_blocked() -> None:
    players = pd.DataFrame(
        {
            "season": ["2025-26"],
            "player_id": [10],
            "player_name": ["Status Player"],
            "team_abbr": ["DEN"],
            "age": [28],
            "minutes": [1000],
            "pts": [300],
            "usage_rate": [0.18],
            "true_shooting": [0.58],
        }
    )
    contracts = pd.DataFrame(
        {
            "player_id": [10],
            "cap_hit_millions": [2.0],
            "base_salary_millions": [pd.NA],
            "contract_aav_millions": [pd.NA],
            "contract_status": ["unrestricted_free_agent"],
            "free_agent_year": [2026],
            "years_remaining": [0],
            "option_status": ["none"],
            "extension_status": ["unknown"],
            "salary_source": ["test"],
            "pulled_at": ["2026-06-20"],
        }
    )
    transactions = pd.DataFrame(
        {
            "transaction_date": ["2026-06-19"],
            "player_id": [10],
            "player_name": ["Status Player"],
            "team_abbr": ["DEN"],
            "transaction_type": ["signing"],
            "description": ["Signed a contract with Denver (DEN)"],
            "source": ["Spotrac NBA Transactions"],
        }
    )

    universe = classify_candidate_universe(
        player_seasons=players,
        contracts=contracts,
        transactions=transactions,
    )

    row = universe.iloc[0]
    assert row["candidate_type"] == "contract_blocked"
    assert row["candidate_status_freshness"] == "conflict_between_sources"
