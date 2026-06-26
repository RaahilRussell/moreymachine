"""Salary and acquisition cards."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.acquisition_feasibility import ACQUISITION_FEASIBILITY_PATH
from moreymachine.utils.paths import CANDIDATE_UNIVERSE_PATH, REPORTS_DATA_DIR

PLAYER_SALARY_CARDS_PATH = REPORTS_DATA_DIR / "player_salary_cards.parquet"


@dataclass(frozen=True)
class SalaryCardsResult:
    """Summary from building salary cards."""

    rows: int
    manual_review: int
    output_path: Path


def build_salary_cards(
    *,
    candidate_universe_path: str | Path = CANDIDATE_UNIVERSE_PATH,
    acquisition_feasibility_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    output_path: str | Path = PLAYER_SALARY_CARDS_PATH,
) -> SalaryCardsResult:
    """Build one salary/acquisition card per candidate."""
    candidates = pd.read_parquet(candidate_universe_path)
    acquisition = pd.read_parquet(acquisition_feasibility_path)
    frame = acquisition.merge(
        candidates,
        left_on="candidate_id",
        right_on="player_id",
        how="left",
        suffixes=("", "_candidate"),
    )
    rows = [_salary_card(row) for row in frame.to_dict(orient="records")]
    out = pd.DataFrame(rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    write_metadata_for_artifact(
        output,
        run_id=new_run_id(),
        source_files=(candidate_universe_path, acquisition_feasibility_path),
        upstream_artifacts=(candidate_universe_path, acquisition_feasibility_path),
        known_limitations=(
            "Cards separate cap hit, base salary, and AAV because sources differ.",
            "Missing or stale status remains missing/manual review.",
        ),
    )
    return SalaryCardsResult(
        rows=len(out),
        manual_review=int(out["manual_review_needed"].sum()),
        output_path=output,
    )


def _salary_card(row: dict[str, Any]) -> dict[str, Any]:
    missing = _split_flags(row.get("missing_data_flags"))
    source = row.get("salary_source") or row.get("source") or ""
    cap_hit = _nullable(row.get("cap_hit_millions"))
    base = _nullable(row.get("base_salary_millions"))
    aav = _nullable(row.get("contract_aav_millions"))
    warnings = _warning_flags(row, missing, cap_hit, base, aav)
    return {
        "player_id": row.get("candidate_id"),
        "player_name": row.get("candidate_name"),
        "salary_card_title": _title(row, cap_hit),
        "salary_summary": _summary(row, cap_hit, base, aav),
        "contract_status": row.get("contract_status") or "missing",
        "cap_hit_millions": cap_hit,
        "base_salary_millions": base,
        "contract_aav_millions": aav,
        "years_remaining": _nullable(row.get("years_remaining")),
        "option_status": row.get("option_status") or "missing",
        "free_agent_year": row.get("free_agent_year"),
        "salary_bucket": row.get("salary_bucket") or "missing",
        "salary_source": source,
        "source_url": row.get("source_url") or source,
        "source_note": (
            "salary card from acquisition feasibility and candidate universe"
        ),
        "freshness_status": row.get("freshness_status")
        or "manual_verification_required",
        "acquisition_path": row.get("acquisition_path"),
        "feasibility_tier": row.get("feasibility_tier"),
        "what_makes_him_easy_or_hard_to_get": row.get("acquisition_difficulty"),
        "what_data_is_missing": _missing_text(warnings),
        "manual_review_needed": bool(row.get("manual_review_required")),
        "salary_warning_flags": json.dumps(warnings),
        "pulled_at": row.get("pulled_at") or datetime.now(UTC).date().isoformat(),
        "data_mode": "derived",
        "missing_data_flags": ";".join(warnings) if warnings else "none",
    }


def _title(row: dict[str, Any], cap_hit: float | None) -> str:
    if cap_hit is None:
        return f"{row.get('candidate_name')} - salary missing"
    return f"{row.get('candidate_name')} - {cap_hit:.1f}M cap hit"


def _summary(
    row: dict[str, Any],
    cap_hit: float | None,
    base: float | None,
    aav: float | None,
) -> str:
    parts = [
        f"contract status: {row.get('contract_status') or 'missing'}",
        f"path: {row.get('acquisition_path')}",
        f"feasibility: {row.get('feasibility_tier')}",
    ]
    parts.append(f"cap hit: {_money(cap_hit)}")
    parts.append(f"base salary: {_money(base)}")
    parts.append(f"AAV: {_money(aav)}")
    return "; ".join(parts)


def _warning_flags(
    row: dict[str, Any],
    missing: list[str],
    cap_hit: float | None,
    base: float | None,
    aav: float | None,
) -> list[str]:
    flags = set(missing)
    if cap_hit is None:
        flags.add("cap_hit_missing")
    if base is None:
        flags.add("base_salary_missing")
    if aav is None:
        flags.add("contract_aav_missing")
    if bool(row.get("manual_review_required")):
        flags.add("manual_review_needed")
    freshness = str(row.get("freshness_status") or "")
    if freshness in {"stale_needs_review", "manual_verification_required"}:
        flags.add(freshness)
    return sorted(flag for flag in flags if flag != "none")


def _missing_text(flags: list[str]) -> str:
    if not flags:
        return "No salary warning flags generated."
    return ", ".join(flags)


def _money(value: float | None) -> str:
    if value is None:
        return "missing"
    return f"{value:.1f}M"


def _nullable(value: Any) -> float | None:
    try:
        if value in (None, "") or pd.isna(value):
            return None
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]
