"""Contract and transaction state schemas."""

from __future__ import annotations

from moreymachine.schemas.common import ArtifactSchema
from moreymachine.utils.paths import (
    CONTRACTS_PATH,
    MANUAL_CONTRACTS_PATH,
    TRANSACTIONS_PATH,
)

CONTRACT_STATUS_VALUES = (
    "signed_long_term",
    "signed_short_term",
    "max_or_near_max",
    "rookie_scale",
    "minimum_contract",
    "unrestricted_free_agent",
    "restricted_free_agent",
    "likely_free_agent",
    "unknown",
    "missing",
)

TRANSACTION_TYPES = (
    "signing",
    "extension",
    "trade",
    "option_exercised",
    "option_declined",
    "free_agent_status_change",
    "waived",
    "released",
    "draft",
    "other",
)

CONTRACT_STATE_SCHEMA = ArtifactSchema(
    name="contracts",
    path=CONTRACTS_PATH,
    required_artifact=True,
    required_columns=(
        "player_name",
        "player_id",
        "contract_status",
        "base_salary_millions",
        "cap_hit_millions",
        "contract_aav_millions",
        "salary_source",
        "source_url",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=(
        "years_remaining",
        "option_status",
        "free_agent_year",
        "extension_status",
    ),
    enum_columns={"contract_status": CONTRACT_STATUS_VALUES},
    provenance_columns=("salary_source", "source_url", "pulled_at", "data_mode"),
    non_null_columns=("player_name", "contract_status"),
    source_columns=("salary_source", "source_url", "source_note"),
)

MANUAL_CONTRACT_STATE_SCHEMA = ArtifactSchema(
    name="manual_contracts",
    path=MANUAL_CONTRACTS_PATH,
    required_artifact=True,
    artifact_type="csv",
    required_columns=(
        "player_name",
        "contract_status",
        "salary_source",
        "source_url",
        "pulled_at",
        "data_mode",
        "missing_data_flags",
    ),
    optional_columns=(
        "player_id",
        "current_team",
        "base_salary_millions",
        "cap_hit_millions",
        "contract_aav_millions",
    ),
    enum_columns={"contract_status": CONTRACT_STATUS_VALUES},
    provenance_columns=("salary_source", "source_url", "pulled_at", "data_mode"),
    non_null_columns=("player_name", "contract_status"),
    source_columns=("salary_source", "source_url", "source_note"),
)

TRANSACTION_STATE_SCHEMA = ArtifactSchema(
    name="transactions",
    path=TRANSACTIONS_PATH,
    required_artifact=True,
    required_columns=(
        "transaction_date",
        "player_name",
        "transaction_type",
        "description",
        "source",
        "source_url",
        "pulled_at",
        "data_mode",
    ),
    optional_columns=("player_id", "team_abbr", "from_team_abbr"),
    enum_columns={"transaction_type": TRANSACTION_TYPES},
    provenance_columns=("source", "source_url", "pulled_at", "data_mode"),
    non_null_columns=("transaction_date", "player_name", "transaction_type"),
)

SCHEMAS = (
    CONTRACT_STATE_SCHEMA,
    MANUAL_CONTRACT_STATE_SCHEMA,
    TRANSACTION_STATE_SCHEMA,
)
