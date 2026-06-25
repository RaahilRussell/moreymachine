"""Strict schema contracts for every core MoreyMachine table.

A *data contract* pins down what each table must contain before anything is
allowed to depend on it: required data columns, provenance columns, non-null
keys, and the set of ``data_mode`` values that are legal in real mode. The
contracts are the single source of truth that ``scripts/validate_data_contracts``
checks, so a table can never silently lose its provenance or ship demo data.

Severity policy:
* **errors** (fail the build): a missing required column, a null in a non-null
  key, or a ``data_mode`` value outside the allowed set (e.g. ``demo``).
* **warnings** (surfaced, non-fatal): a recommended provenance column that a
  table does not yet emit. As the pipeline is rebuilt these are promoted to
  required, so warnings trend to zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH
from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_UNIVERSE_PATH,
    CANDIDATES_PATH,
    CONTRACTS_PATH,
    PLAYER_BIO_PATH,
    PLAYER_ROLE_EXPLANATIONS_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    REPORTS_DATA_DIR,
    TEAM_SEASONS_PATH,
)

# Legal data_mode values. "demo" is intentionally absent: real mode never
# tolerates demo data. "missing" marks an honestly-absent real source.
ALLOWED_DATA_MODES = (
    "real_api",
    "real_scraped",
    "real_manual",
    "derived",
    "missing",
)

ROSTER_GAPS_PATH = REPORTS_DATA_DIR / "phi_roster_gaps.parquet"
BACKTEST_RESULTS_PATH = REPORTS_DATA_DIR / "backtest_results.json"


@dataclass(frozen=True)
class TableContract:
    """Schema + provenance contract for one table."""

    key: str
    path: Path
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...] = ()
    provenance_columns: tuple[str, ...] = ()
    non_null_columns: tuple[str, ...] = ()
    allowed_data_modes: tuple[str, ...] = ALLOWED_DATA_MODES
    season_or_date_columns: tuple[str, ...] = ()
    is_json: bool = False
    json_required_keys: tuple[str, ...] = ()


@dataclass
class ContractReport:
    """Validation outcome for one table."""

    key: str
    present: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.present and not self.errors


# Reusable provenance bundles.
RAW_PROVENANCE = ("source", "pulled_at", "data_mode")
DERIVED_PROVENANCE = ("data_mode", "built_at")

CONTRACTS: tuple[TableContract, ...] = (
    TableContract(
        key="team_seasons",
        path=TEAM_SEASONS_PATH,
        required_columns=(
            "season",
            "team_abbr",
            "net_rating",
            "off_rating",
            "def_rating",
        ),
        provenance_columns=RAW_PROVENANCE,
        non_null_columns=("season", "team_abbr"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="player_seasons",
        path=PLAYER_SEASONS_PATH,
        required_columns=(
            "season",
            "player_id",
            "player_name",
            "team_abbr",
            "minutes",
            "usage_rate",
        ),
        provenance_columns=RAW_PROVENANCE,
        non_null_columns=("season", "player_id", "player_name"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="player_bio",
        path=PLAYER_BIO_PATH,
        required_columns=("player_id", "player_name", "position", "height_inches"),
        optional_columns=("weight", "draft_year", "draft_number"),
        provenance_columns=RAW_PROVENANCE,
        non_null_columns=("player_id", "player_name"),
    ),
    TableContract(
        key="player_tracking",
        path=PLAYER_TRACKING_PATH,
        required_columns=("player_id", "player_name", "catch_shoot_fg3a", "drives"),
        provenance_columns=RAW_PROVENANCE,
        non_null_columns=("player_id", "player_name"),
    ),
    TableContract(
        key="contracts",
        path=CONTRACTS_PATH,
        required_columns=(
            "player_name",
            "player_id",
            "contract_status",
            "base_salary_millions",
            "cap_hit_millions",
            "contract_aav_millions",
        ),
        optional_columns=(
            "years_remaining",
            "option_status",
            "free_agent_year",
            "extension_status",
            "salary_source",
            "source_url",
        ),
        provenance_columns=("salary_source", "pulled_at", "data_mode"),
        non_null_columns=("player_name", "contract_status"),
        season_or_date_columns=("effective_date",),
    ),
    TableContract(
        key="candidates",
        path=CANDIDATES_PATH,
        required_columns=("player_name", "candidate_type"),
        optional_columns=("player_id", "current_team", "position"),
        provenance_columns=("salary_source", "source_note"),
        non_null_columns=("player_name",),
    ),
    TableContract(
        key="candidate_universe",
        path=CANDIDATE_UNIVERSE_PATH,
        required_columns=(
            "player_id",
            "player_name",
            "candidate_type",
            "candidate_type_reason",
            "acquisition_feasibility",
            "feasibility_tier",
        ),
        provenance_columns=("season", "salary_source", "data_mode"),
        non_null_columns=("player_id", "player_name", "candidate_type"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="player_roles",
        path=PLAYER_ROLE_EXPLANATIONS_PATH,
        required_columns=(
            "player_id",
            "player_name",
            "role_archetype",
            "expected_role",
            "role_confidence",
        ),
        provenance_columns=("season", "data_mode"),
        non_null_columns=("player_id", "player_name", "role_archetype"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="roster_gaps",
        path=ROSTER_GAPS_PATH,
        required_columns=(
            "target_team",
            "target_season",
            "category_key",
            "severity_score",
        ),
        provenance_columns=("target_season", "data_sources"),
        non_null_columns=("target_team", "category_key"),
        season_or_date_columns=("target_season",),
    ),
    TableContract(
        key="candidate_rankings",
        path=CANDIDATE_RANKINGS_ALL_PATH,
        required_columns=(
            "player_name",
            "candidate_type",
            "recommendation",
            "final_fit",
            "why_fit",
            "concerns",
            "data_sources",
            "missing_data_flags",
        ),
        provenance_columns=("season", "data_sources"),
        non_null_columns=("player_name", "candidate_type", "recommendation"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="candidate_rankings_realistic",
        path=CANDIDATE_RANKINGS_REALISTIC_PATH,
        required_columns=(
            "player_name",
            "candidate_type",
            "recommendation",
            "final_fit",
            "why_fit",
        ),
        provenance_columns=("data_sources",),
        non_null_columns=("player_name", "recommendation"),
    ),
    TableContract(
        key="team_fingerprints",
        path=TEAM_FINGERPRINTS_PATH,
        required_columns=("season", "team_abbr", "net_rating"),
        provenance_columns=("season",),
        non_null_columns=("season", "team_abbr"),
        season_or_date_columns=("season",),
    ),
    TableContract(
        key="backtest_results",
        path=BACKTEST_RESULTS_PATH,
        required_columns=(),
        is_json=True,
        json_required_keys=("target_team", "offseasons", "metrics"),
    ),
)

CONTRACTS_BY_KEY = {contract.key: contract for contract in CONTRACTS}


def validate_frame(frame: pd.DataFrame, contract: TableContract) -> ContractReport:
    """Validate a loaded frame against a contract."""
    report = ContractReport(key=contract.key, present=True)

    missing_required = [c for c in contract.required_columns if c not in frame.columns]
    if missing_required:
        report.errors.append(f"missing required columns: {missing_required}")

    for column in contract.non_null_columns:
        if column in frame.columns and frame[column].isna().any():
            n = int(frame[column].isna().sum())
            report.errors.append(f"{n} null values in non-null column '{column}'")

    if "data_mode" in frame.columns:
        bad = sorted(
            set(frame["data_mode"].dropna().astype(str))
            - set(contract.allowed_data_modes)
        )
        if bad:
            report.errors.append(f"illegal data_mode values: {bad}")

    missing_prov = [c for c in contract.provenance_columns if c not in frame.columns]
    if missing_prov:
        report.warnings.append(f"missing provenance columns: {missing_prov}")

    if contract.season_or_date_columns and not any(
        c in frame.columns for c in contract.season_or_date_columns
    ):
        report.warnings.append(
            f"no season/effective_date column ({contract.season_or_date_columns})"
        )
    return report


def validate_contract(contract: TableContract) -> ContractReport:
    """Load the file for a contract and validate it (or report it missing)."""
    if not contract.path.exists():
        return ContractReport(
            key=contract.key,
            present=False,
            errors=[f"file missing: {contract.path}"],
        )
    if contract.is_json:
        return _validate_json(contract)
    frame = (
        pd.read_parquet(contract.path)
        if contract.path.suffix == ".parquet"
        else (pd.read_csv(contract.path))
    )
    return validate_frame(frame, contract)


def validate_all() -> list[ContractReport]:
    """Validate every registered contract."""
    return [validate_contract(contract) for contract in CONTRACTS]


def _validate_json(contract: TableContract) -> ContractReport:
    report = ContractReport(key=contract.key, present=True)
    try:
        payload = json.loads(contract.path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        report.errors.append(f"unreadable JSON: {exc}")
        return report
    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload:
            if isinstance(item, dict):
                keys |= set(item)
    else:
        keys = set(payload) if isinstance(payload, dict) else set()
    missing = [k for k in contract.json_required_keys if k not in keys]
    if missing:
        report.warnings.append(f"missing JSON keys: {missing}")
    return report
