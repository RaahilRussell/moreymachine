"""Transparent acquisition and contract feasibility layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.utils.paths import (
    CANDIDATE_UNIVERSE_PATH,
    CONTRACTS_PATH,
    FEATURES_DATA_DIR,
    REPORTS_DATA_DIR,
    TRANSACTIONS_PATH,
)

ACQUISITION_FEASIBILITY_PATH = FEATURES_DATA_DIR / "acquisition_feasibility.parquet"
ACQUISITION_FEASIBILITY_REPORT_PATH = REPORTS_DATA_DIR / "acquisition_feasibility.md"


@dataclass(frozen=True)
class AcquisitionFeasibilityResult:
    """Summary from building acquisition feasibility."""

    rows: int
    manual_review_required: int
    unknown_paths: int
    output_path: Path
    report_path: Path


def build_acquisition_feasibility(
    *,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    contracts_path: str | Path = CONTRACTS_PATH,
    transactions_path: str | Path = TRANSACTIONS_PATH,
    output_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    report_path: str | Path = ACQUISITION_FEASIBILITY_REPORT_PATH,
) -> AcquisitionFeasibilityResult:
    """Build contract/acquisition feasibility rows for candidates."""
    candidates = pd.read_parquet(candidate_universe_path)
    contracts = _optional_parquet(contracts_path)
    transactions = _optional_parquet(transactions_path)
    merged = _merge_contracts(candidates, contracts)
    latest_transactions = _latest_transactions(transactions)
    rows = [
        _acquisition_row(row, latest_transactions)
        for row in merged.to_dict(orient="records")
    ]
    frame = pd.DataFrame(rows)

    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    report.write_text(_render_report(frame), encoding="utf-8")

    run_id = new_run_id()
    for artifact in (output, report):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(candidate_universe_path, contracts_path, transactions_path),
            upstream_artifacts=(
                candidate_universe_path,
                contracts_path,
                transactions_path,
            ),
            known_limitations=(
                "This is a transparent feasibility proxy, not exact CBA modeling.",
                "True trade price, team intent, and medical information are not "
                "sourced.",
                "Missing salary fields remain missing and trigger manual review.",
            ),
        )

    return AcquisitionFeasibilityResult(
        rows=len(frame),
        manual_review_required=int(frame["manual_review_required"].sum()),
        unknown_paths=int((frame["acquisition_path"] == "unknown_missing_data").sum()),
        output_path=output,
        report_path=report,
    )


def _optional_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(file_path)


def _merge_contracts(candidates: pd.DataFrame, contracts: pd.DataFrame) -> pd.DataFrame:
    if contracts.empty:
        return candidates.copy()
    contract_cols = [
        "player_id",
        "source_url",
        "salary_context",
        "missing_data_flags",
        "pulled_at",
        "effective_date",
    ]
    available = [col for col in contract_cols if col in contracts.columns]
    merged = candidates.merge(
        contracts[available].drop_duplicates("player_id"),
        on="player_id",
        how="left",
        suffixes=("", "_contract"),
    )
    return merged


def _latest_transactions(transactions: pd.DataFrame) -> dict[int, dict[str, Any]]:
    if transactions.empty or "player_id" not in transactions.columns:
        return {}
    out = {}
    frame = transactions.dropna(subset=["player_id"]).copy()
    frame["transaction_date"] = pd.to_datetime(
        frame["transaction_date"], errors="coerce"
    )
    frame = frame.sort_values("transaction_date", ascending=False)
    for row in frame.to_dict(orient="records"):
        player_id = int(row["player_id"])
        out.setdefault(player_id, row)
    return out


def _acquisition_row(
    row: dict[str, Any], latest_transactions: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    candidate_type = str(row.get("candidate_type") or "")
    player_id = int(row["player_id"])
    cap_hit = _nullable_float(row.get("cap_hit_millions"))
    base = _nullable_float(row.get("base_salary_millions"))
    aav = _nullable_float(row.get("contract_aav_millions"))
    years = _nullable_float(row.get("years_remaining"))
    freshness = str(
        row.get("candidate_status_freshness") or "manual_verification_required"
    )
    path = _acquisition_path(candidate_type, cap_hit, years)
    score = _score(row, path, cap_hit, freshness)
    manual_review, review_flags = _manual_review_flags(row, cap_hit, freshness, path)
    latest_transaction = latest_transactions.get(player_id, {})
    if latest_transaction:
        review_flags.append("recent_transaction_present")
    missing_flags = _missing_flags(row, cap_hit, base, aav, review_flags)
    evidence = {
        "candidate_type": candidate_type,
        "contract_status": row.get("contract_status"),
        "cap_hit_millions": cap_hit,
        "base_salary_millions": base,
        "contract_aav_millions": aav,
        "years_remaining": years,
        "candidate_status_freshness": freshness,
        "latest_transaction_date": _date_text(
            latest_transaction.get("transaction_date")
        ),
        "latest_transaction_type": latest_transaction.get("transaction_type", ""),
        "salary_source": row.get("salary_source"),
    }
    return {
        "candidate_id": player_id,
        "candidate_name": row.get("player_name"),
        "candidate_type": candidate_type,
        "contract_status": row.get("contract_status") or "missing",
        "salary_bucket": _salary_bucket(cap_hit),
        "cap_hit_millions": cap_hit,
        "base_salary_millions": base,
        "contract_aav_millions": aav,
        "years_remaining": years,
        "option_status": row.get("option_status") or "missing",
        "acquisition_path": path,
        "acquisition_difficulty": _difficulty(path, cap_hit, candidate_type),
        "acquisition_feasibility_score": score,
        "feasibility_tier": _feasibility_tier(score),
        "trade_cost_proxy": _trade_cost_proxy(row, path, cap_hit),
        "salary_matching_complexity": _salary_matching_complexity(path, cap_hit),
        "apron_or_exception_uncertainty": _apron_uncertainty(path, cap_hit),
        "source_quality": _source_quality(cap_hit, base, aav, row),
        "freshness_status": freshness,
        "manual_review_required": bool(manual_review),
        "evidence": json.dumps(evidence, sort_keys=True),
        "source": row.get("salary_source") or "candidate_universe/contracts",
        "source_url": row.get("source_url") or row.get("salary_source") or "",
        "pulled_at": row.get("salary_pulled_at")
        or row.get("pulled_at_contract")
        or datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(sorted(set(missing_flags)))
        if missing_flags
        else "none",
    }


def _acquisition_path(
    candidate_type: str, cap_hit: float | None, years: float | None
) -> str:
    free_agent_paths = {
        "minimum_candidate": "minimum_signing",
        "mle_candidate": "mle_or_exception_signing",
        "unrestricted_free_agent": "free_agent_market",
        "likely_free_agent": "free_agent_market",
        "restricted_free_agent": "restricted_free_agent_offer",
    }
    if candidate_type in free_agent_paths:
        return free_agent_paths[candidate_type]
    if candidate_type == "rookie_scale_trade_target":
        return "rookie_scale_trade"
    if candidate_type in {"star_unrealistic", "manual_watchlist"}:
        return "theoretical_only"
    if candidate_type in {"core_unavailable", "unavailable_core_player"}:
        return "unavailable_or_core"
    if candidate_type in {"missing_contract_status", "manual_review_needed"}:
        return "unknown_missing_data"
    if candidate_type == "contract_blocked":
        return "unknown_missing_data"
    if cap_hit is None:
        return "unknown_missing_data"
    if cap_hit <= 8:
        return "small_trade"
    if cap_hit <= 25:
        return "medium_trade"
    if cap_hit <= 40:
        return "expensive_trade"
    if years and years >= 3:
        return "star_trade"
    return "expensive_trade"


def _score(
    row: dict[str, Any], path: str, cap_hit: float | None, freshness: str
) -> float:
    base = {
        "minimum_signing": 88,
        "mle_or_exception_signing": 76,
        "free_agent_market": 72,
        "restricted_free_agent_offer": 55,
        "small_trade": 62,
        "medium_trade": 50,
        "expensive_trade": 34,
        "star_trade": 15,
        "rookie_scale_trade": 56,
        "theoretical_only": 8,
        "unavailable_or_core": 5,
        "unknown_missing_data": 20,
    }.get(path, 20)
    quality = _nullable_float(row.get("quality_percentile")) or 0
    if path.endswith("trade") or path == "rookie_scale_trade":
        base -= min(20, quality * 18)
    if cap_hit and cap_hit > 35:
        base -= 10
    if freshness in {
        "stale_needs_review",
        "manual_verification_required",
        "conflict_between_sources",
    }:
        base -= 15
    return round(max(0.0, min(100.0, float(base))), 2)


def _manual_review_flags(
    row: dict[str, Any],
    cap_hit: float | None,
    freshness: str,
    path: str,
) -> tuple[bool, list[str]]:
    flags = []
    if freshness in {
        "stale_needs_review",
        "manual_verification_required",
        "conflict_between_sources",
    }:
        flags.append(freshness)
    if cap_hit is None and path not in {
        "minimum_signing",
        "mle_or_exception_signing",
        "free_agent_market",
    }:
        flags.append("cap_hit_missing")
    if row.get("contract_status") in (None, "", "missing", "unknown"):
        flags.append("contract_status_missing")
    if path == "unknown_missing_data":
        flags.append("unknown_acquisition_path")
    return bool(flags), flags


def _missing_flags(
    row: dict[str, Any],
    cap_hit: float | None,
    base: float | None,
    aav: float | None,
    review_flags: list[str],
) -> list[str]:
    flags = set(review_flags)
    flags.update(_split_flags(row.get("missing_data_flags")))
    flags.update(_split_flags(row.get("missing_data_flags_contract")))
    if cap_hit is None:
        flags.add("cap_hit_missing")
    if base is None:
        flags.add("base_salary_missing")
    if aav is None:
        flags.add("contract_aav_missing")
    return sorted(flag for flag in flags if flag != "none")


def _salary_bucket(cap_hit: float | None) -> str:
    if cap_hit is None:
        return "missing"
    if cap_hit <= 3:
        return "minimum_or_low"
    if cap_hit <= 14:
        return "exception_range"
    if cap_hit <= 25:
        return "medium"
    if cap_hit <= 40:
        return "expensive"
    return "max_or_near_max"


def _difficulty(path: str, cap_hit: float | None, candidate_type: str) -> str:
    if path in {"theoretical_only", "unavailable_or_core"}:
        return "not realistically available"
    if path == "unknown_missing_data":
        return "unknown until contract/status is verified"
    if path in {"minimum_signing", "mle_or_exception_signing"}:
        return "signing path depends on market and exceptions"
    if path == "restricted_free_agent_offer":
        return "restricted market creates matching risk"
    if cap_hit and cap_hit > 25:
        return "salary matching and trade cost are difficult"
    if candidate_type.endswith("trade_target"):
        return "trade requires assets and team willingness"
    return "moderate public-data feasibility"


def _trade_cost_proxy(row: dict[str, Any], path: str, cap_hit: float | None) -> str:
    quality = _nullable_float(row.get("quality_percentile")) or 0
    if path in {"theoretical_only", "star_trade"} or quality >= 0.93:
        return "star_or_unavailable_cost"
    if path in {"minimum_signing", "mle_or_exception_signing", "free_agent_market"}:
        return "no_trade_cost"
    if cap_hit is None:
        return "unknown"
    if cap_hit <= 8 and quality < 0.70:
        return "low_to_medium"
    if cap_hit <= 25 and quality < 0.85:
        return "medium"
    return "high"


def _salary_matching_complexity(path: str, cap_hit: float | None) -> str:
    if path in {
        "minimum_signing",
        "mle_or_exception_signing",
        "free_agent_market",
        "restricted_free_agent_offer",
    }:
        return "none_or_exception_dependent"
    if cap_hit is None:
        return "unknown"
    if cap_hit <= 8:
        return "low"
    if cap_hit <= 25:
        return "medium"
    return "high"


def _apron_uncertainty(path: str, cap_hit: float | None) -> str:
    if path in {"minimum_signing"}:
        return "low"
    if path in {"mle_or_exception_signing", "free_agent_market"}:
        return "medium_exception_dependent"
    if cap_hit is None:
        return "unknown"
    if cap_hit > 25:
        return "high_salary_matching_uncertainty"
    return "medium"


def _source_quality(
    cap_hit: float | None, base: float | None, aav: float | None, row: dict[str, Any]
) -> str:
    if cap_hit is None:
        return "low_missing_cap_hit"
    if base is None or aav is None:
        return "medium_cap_hit_only"
    if row.get("salary_source"):
        return "high"
    return "medium"


def _feasibility_tier(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 55:
        return "Medium"
    if score >= 35:
        return "Low"
    if score >= 15:
        return "Very Low"
    return "Theoretical"


def _nullable_float(value: Any) -> float | None:
    try:
        if value in (None, "") or pd.isna(value):
            return None
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or pd.isna(value):
        return []
    return [part for part in str(value).split(";") if part and part != "none"]


def _date_text(value: Any) -> str:
    if value in (None, "") or pd.isna(value):
        return ""
    return str(value)[:10]


def _render_report(frame: pd.DataFrame) -> str:
    lines = [
        "# Acquisition Feasibility",
        "",
        "This layer separates contract/status reality from basketball fit.",
        "",
        "## Path Counts",
        "",
        "| Acquisition Path | Rows | Median Score | Manual Review |",
        "| --- | ---: | ---: | ---: |",
    ]
    for path, group in frame.groupby("acquisition_path"):
        lines.append(
            f"| {path} | {len(group)} | "
            f"{group['acquisition_feasibility_score'].median():.1f} | "
            f"{int(group['manual_review_required'].sum())} |"
        )
    lines.extend(
        [
            "",
            "## Manual Review Examples",
            "",
            _manual_review_table(frame[frame["manual_review_required"]].head(20)),
            "",
            "## Limits",
            "",
            "- This is not exact CBA math.",
            "- Public contract data may lack base salary or AAV.",
            "- True trade availability and team intent are not public.",
        ]
    )
    return "\n".join(lines)


def _manual_review_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows currently require manual review."
    lines = [
        "| Player | Type | Path | Freshness | Missing Flags |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in frame.to_dict(orient="records"):
        lines.append(
            f"| {row['candidate_name']} | {row['candidate_type']} | "
            f"{row['acquisition_path']} | {row['freshness_status']} | "
            f"{row['missing_data_flags']} |"
        )
    return "\n".join(lines)
