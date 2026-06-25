"""Hard validation gates for the Sixers target boards (max rebuild).

These gates encode every failure mode the board must never regress into: a flood
of Priority targets, saturated contract-value / portability scores, a collapsed
risk distribution, recommendations without provenance or explanation, current
Sixers or unavailable stars on the acquisition board, ambiguous salary fields, or
a CSV export missing its explanation columns. ``validate_boards`` returns a
structured report and the CLI/tests fail loudly when any gate trips.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.features.candidate_universe import PHI_ROSTER_2025_26
from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_CSV_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_RANKINGS_WATCHLIST_PATH,
)

MAX_PRIORITY_TARGETS = 10
MAX_CONTRACT_95_SHARE = 0.10
MAX_PORTABILITY_95_SHARE = 0.05
MAX_IDENTICAL_RISK_SHARE = 0.50

PRIORITY_LABEL = "Priority Target"
UNREALISTIC_PRIORITY_TYPES = {
    "star_unrealistic",
    "core_unavailable",
    "expensive_but_possible",
    "contract_blocked",
    "manual_review_needed",
    "unavailable_core_player",
    "manual_watchlist",
}
REALISTIC_EXCLUDED_TYPES = UNREALISTIC_PRIORITY_TYPES | {"missing_contract_status"}

REQUIRED_EXPLANATION_COLUMNS = (
    "why_fit",
    "concerns",
    "gaps_addressed",
    "role_on_sixers",
    "acquisition_summary",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "data_sources",
    "missing_data_flags",
    "explanation_confidence",
)

# Explicit salary fields that must be present so "salary" is never ambiguous.
REQUIRED_SALARY_COLUMNS = (
    "base_salary_millions",
    "cap_hit_millions",
    "contract_aav_millions",
    "salary_bucket",
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of a single validation gate."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate result of all validation gates."""

    gates: tuple[GateResult, ...]

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates)

    @property
    def failures(self) -> tuple[GateResult, ...]:
        return tuple(gate for gate in self.gates if not gate.passed)

    def to_markdown(self) -> str:
        lines = ["# Target Board Validation", ""]
        status = "PASSED" if self.passed else "FAILED"
        lines.append(f"**Overall: {status}** ({len(self.failures)} failing gates)")
        lines += ["", "| Gate | Result | Detail |", "| --- | --- | --- |"]
        for gate in self.gates:
            mark = "pass" if gate.passed else "**FAIL**"
            lines.append(f"| {gate.name} | {mark} | {gate.detail} |")
        return "\n".join(lines) + "\n"


def validate_boards(
    *,
    all_path: str | Path = CANDIDATE_RANKINGS_ALL_PATH,
    realistic_path: str | Path = CANDIDATE_RANKINGS_REALISTIC_PATH,
    watchlist_path: str | Path = CANDIDATE_RANKINGS_WATCHLIST_PATH,
    csv_path: str | Path = CANDIDATE_RANKINGS_CSV_PATH,
) -> ValidationReport:
    """Load the boards from disk and run every gate."""
    return validate_board_frames(
        _read(all_path),
        _read(realistic_path),
        _read(watchlist_path),
        csv_path=Path(csv_path),
    )


def validate_board_frames(
    board_all: pd.DataFrame,
    realistic: pd.DataFrame,
    watchlist: pd.DataFrame,
    *,
    csv_path: Path | None = None,
) -> ValidationReport:
    """Run every gate against already-loaded board frames."""
    gates = [
        _gate_priority_cap(realistic),
        _gate_contract_saturation(board_all),
        _gate_portability_saturation(board_all),
        _gate_risk_diversity(board_all),
        _gate_candidate_type_present(board_all),
        _gate_provenance(board_all),
        _gate_explanation_present(board_all),
        _gate_no_current_sixers(board_all),
        _gate_no_star_in_realistic(realistic),
        _gate_no_unrealistic_priority(board_all),
        _gate_no_missing_contract_priority(board_all),
        _gate_no_unknown_role_priority(board_all),
        _gate_no_severe_risk_priority(board_all),
        _gate_no_stale_priority(board_all),
        _gate_salary_unambiguous(board_all),
        _gate_watchlist_separation(watchlist),
        _gate_csv_explanations(csv_path),
    ]
    return ValidationReport(gates=tuple(gates))


def _gate_priority_cap(realistic: pd.DataFrame) -> GateResult:
    count = int(_text_column(realistic, "recommendation").eq(PRIORITY_LABEL).sum())
    return GateResult(
        "priority_cap",
        count <= MAX_PRIORITY_TARGETS,
        f"{count} Priority targets (cap {MAX_PRIORITY_TARGETS}).",
    )


def _gate_contract_saturation(board: pd.DataFrame) -> GateResult:
    share = _share_at_least(board, "contract_value", 95)
    return GateResult(
        "contract_value_saturation",
        share <= MAX_CONTRACT_95_SHARE,
        f"{share * 100:.1f}% with contract_value >= 95 (limit 10%).",
    )


def _gate_portability_saturation(board: pd.DataFrame) -> GateResult:
    share = _share_at_least(board, "portability", 95)
    return GateResult(
        "portability_saturation",
        share <= MAX_PORTABILITY_95_SHARE,
        f"{share * 100:.1f}% with portability >= 95 (limit 5%).",
    )


def _gate_risk_diversity(board: pd.DataFrame) -> GateResult:
    if "risk_score" not in board.columns or board.empty:
        return GateResult("risk_diversity", False, "risk_score column missing.")
    counts = (
        pd.to_numeric(board["risk_score"], errors="coerce")
        .round(0)
        .value_counts(normalize=True)
    )
    share = float(counts.iloc[0]) if not counts.empty else 1.0
    return GateResult(
        "risk_diversity",
        share <= MAX_IDENTICAL_RISK_SHARE,
        f"most common risk = {share * 100:.1f}% (limit 50%).",
    )


def _gate_candidate_type_present(board: pd.DataFrame) -> GateResult:
    if board.empty:
        return GateResult("candidate_type_present", True, "empty board.")
    types = _text_column(board, "candidate_type")
    bad = int(types.eq("").sum())
    return GateResult(
        "candidate_type_present", bad == 0, f"{bad} rows missing candidate_type."
    )


def _gate_provenance(board: pd.DataFrame) -> GateResult:
    if board.empty:
        return GateResult("recommendation_provenance", True, "empty board.")
    bad = int(_text_column(board, "data_sources").eq("").sum())
    return GateResult(
        "recommendation_provenance", bad == 0, f"{bad} rows missing data_sources."
    )


def _gate_explanation_present(board: pd.DataFrame) -> GateResult:
    missing_cols = [c for c in REQUIRED_EXPLANATION_COLUMNS if c not in board.columns]
    if missing_cols:
        return GateResult(
            "explanation_present", False, f"missing columns: {missing_cols}."
        )
    empty = 0
    for column in REQUIRED_EXPLANATION_COLUMNS:
        empty += int(board[column].fillna("").astype(str).str.strip().eq("").sum())
    return GateResult(
        "explanation_present",
        empty == 0,
        "every row carries explanations."
        if empty == 0
        else f"{empty} rows missing explanation text.",
    )


def _gate_no_current_sixers(board: pd.DataFrame) -> GateResult:
    if board.empty or "player_name" not in board.columns:
        return GateResult("no_current_sixers", True, "no rows to check.")
    leaked = sorted(set(board["player_name"].astype(str)) & set(PHI_ROSTER_2025_26))
    return GateResult(
        "no_current_sixers",
        not leaked,
        "none on board." if not leaked else f"leaked: {', '.join(leaked)}.",
    )


def _gate_no_star_in_realistic(realistic: pd.DataFrame) -> GateResult:
    if realistic.empty or "candidate_type" not in realistic.columns:
        return GateResult("no_star_in_realistic", True, "no rows to check.")
    bad = int(
        _text_column(realistic, "candidate_type").isin(REALISTIC_EXCLUDED_TYPES).sum()
    )
    return GateResult(
        "no_star_in_realistic",
        bad == 0,
        f"{bad} unrealistic/watchlist/missing rows on the realistic board.",
    )


def _gate_no_unrealistic_priority(board: pd.DataFrame) -> GateResult:
    bad = _priority_with(
        board, _text_column(board, "candidate_type").isin(UNREALISTIC_PRIORITY_TYPES)
    )
    return GateResult(
        "no_unrealistic_priority",
        bad == 0,
        f"{bad} unrealistic/watchlist players marked Priority.",
    )


def _gate_no_missing_contract_priority(board: pd.DataFrame) -> GateResult:
    is_missing = _text_column(board, "candidate_type") == "missing_contract_status"
    bad = _priority_with(board, is_missing)
    return GateResult(
        "no_missing_contract_priority",
        bad == 0,
        f"{bad} missing-contract players marked Priority.",
    )


def _gate_no_unknown_role_priority(board: pd.DataFrame) -> GateResult:
    bad = _priority_with(board, _text_column(board, "expected_role") == "Unknown")
    return GateResult(
        "no_unknown_role_priority", bad == 0, f"{bad} Unknown-role players Priority."
    )


def _gate_no_severe_risk_priority(board: pd.DataFrame) -> GateResult:
    severe = board.get("risk_tier", pd.Series(dtype=object)).isin(("Severe", "Unknown"))
    bad = _priority_with(board, severe)
    return GateResult(
        "no_severe_risk_priority", bad == 0, f"{bad} Severe/Unknown-risk Priority."
    )


def _gate_no_stale_priority(board: pd.DataFrame) -> GateResult:
    stale = _text_column(board, "candidate_status_freshness").isin(
        ("stale_needs_review", "manual_verification_required")
    )
    bad = _priority_with(board, stale)
    return GateResult(
        "no_stale_priority",
        bad == 0,
        f"{bad} stale/manual-review players marked Priority.",
    )


def _gate_salary_unambiguous(board: pd.DataFrame) -> GateResult:
    missing = [c for c in REQUIRED_SALARY_COLUMNS if c not in board.columns]
    if missing:
        return GateResult(
            "salary_unambiguous",
            False,
            f"ambiguous salary - missing explicit fields: {missing}.",
        )
    cap_hit = pd.to_numeric(board["cap_hit_millions"], errors="coerce")
    flags = _text_column(board, "missing_data_flags").str.lower()
    salary_context = _text_column(board, "salary_context").str.lower()
    missing_cap_not_flagged = int(
        (
            cap_hit.isna()
            & ~flags.str.contains("cap hit missing", regex=False)
            & ~salary_context.str.contains("no cap figure", regex=False)
        ).sum()
    )
    empty_bucket = int(_text_column(board, "salary_bucket").eq("").sum())
    bad = missing_cap_not_flagged + empty_bucket
    return GateResult(
        "salary_unambiguous",
        bad == 0,
        "base/cap/AAV + bucket all present."
        if bad == 0
        else f"{bad} salary rows lack explicit value, bucket, or missing-data flag.",
    )


def _gate_watchlist_separation(watchlist: pd.DataFrame) -> GateResult:
    if watchlist.empty:
        return GateResult("watchlist_separation", True, "empty watchlist.")
    recs = set(watchlist.get("recommendation", pd.Series(dtype=object)).dropna())
    bad = recs & {PRIORITY_LABEL, "Strong Fit If Affordable", "Role-Player Target"}
    return GateResult(
        "watchlist_separation",
        not bad,
        "watchlist holds no acquisition recommendations."
        if not bad
        else f"watchlist carries recommendation labels: {bad}.",
    )


def _gate_csv_explanations(csv_path: Path | None) -> GateResult:
    if csv_path is None:
        return GateResult("csv_explanations", True, "CSV check skipped.")
    if not csv_path.exists():
        return GateResult("csv_explanations", False, f"CSV missing: {csv_path}.")
    columns = set(pd.read_csv(csv_path, nrows=1).columns)
    missing = [c for c in REQUIRED_EXPLANATION_COLUMNS if c not in columns]
    return GateResult(
        "csv_explanations",
        not missing,
        "CSV carries explanation columns."
        if not missing
        else f"CSV missing explanation columns: {missing}.",
    )


def _priority_with(board: pd.DataFrame, mask: pd.Series) -> int:
    if board.empty or "recommendation" not in board.columns:
        return 0
    aligned = mask.reindex(board.index, fill_value=False).fillna(False)
    return int(((board["recommendation"] == PRIORITY_LABEL) & aligned).sum())


def _share_at_least(board: pd.DataFrame, column: str, threshold: float) -> float:
    if column not in board.columns or board.empty:
        return 1.0
    values = pd.to_numeric(board[column], errors="coerce")
    return float((values >= threshold).mean())


def _text_column(board: pd.DataFrame, column: str) -> pd.Series:
    if column not in board.columns:
        return pd.Series("", index=board.index, dtype=object)
    return board[column].fillna("").astype(str).str.strip()


def _read(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()
