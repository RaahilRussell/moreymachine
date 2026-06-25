"""Hard validation gates for the Sixers target boards.

These gates encode the failure modes the original board audit found: a flood of
Priority targets, saturated contract-value / portability scores, a single risk
value shared by most players, recommendations with no provenance, and current
Sixers or unavailable stars leaking onto the acquisition board. ``validate_boards``
returns a structured report and the CLI/tests fail loudly when any gate trips, so
a regression cannot ship a board that quietly returns to the old behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moreymachine.features.candidate_universe import PHI_ROSTER_2025_26
from moreymachine.utils.paths import (
    CANDIDATE_RANKINGS_ALL_PATH,
    CANDIDATE_RANKINGS_REALISTIC_PATH,
    CANDIDATE_RANKINGS_WATCHLIST_PATH,
)

MAX_PRIORITY_TARGETS = 10
MAX_SATURATION_SHARE = 0.10
MAX_IDENTICAL_RISK_SHARE = 0.50

REQUIRED_EXPLANATION_COLUMNS = (
    "why_fit",
    "concerns",
    "gaps_addressed",
    "role_on_sixers",
    "acquisition_feasibility",
    "expected_rotation_role",
    "salary_context",
    "portability_summary",
    "risk_summary",
    "data_sources",
    "missing_data_flags",
    "explanation_confidence",
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
        lines.append("")
        lines.append("| Gate | Result | Detail |")
        lines.append("| --- | --- | --- |")
        for gate in self.gates:
            mark = "pass" if gate.passed else "**FAIL**"
            lines.append(f"| {gate.name} | {mark} | {gate.detail} |")
        return "\n".join(lines) + "\n"


def validate_boards(
    *,
    all_path: str | Path = CANDIDATE_RANKINGS_ALL_PATH,
    realistic_path: str | Path = CANDIDATE_RANKINGS_REALISTIC_PATH,
    watchlist_path: str | Path = CANDIDATE_RANKINGS_WATCHLIST_PATH,
) -> ValidationReport:
    """Load the boards from disk and run every gate."""
    board_all = _read(all_path)
    realistic = _read(realistic_path)
    watchlist = _read(watchlist_path)
    return validate_board_frames(board_all, realistic, watchlist)


def validate_board_frames(
    board_all: pd.DataFrame,
    realistic: pd.DataFrame,
    watchlist: pd.DataFrame,
) -> ValidationReport:
    """Run every gate against already-loaded board frames."""
    gates = [
        _gate_priority_cap(realistic),
        _gate_saturation(board_all, "contract_value"),
        _gate_saturation(board_all, "portability"),
        _gate_risk_diversity(board_all),
        _gate_provenance(board_all),
        _gate_no_current_sixers(board_all),
        _gate_no_star_in_realistic(realistic),
        _gate_explanation_columns(board_all),
        _gate_watchlist_separation(watchlist),
    ]
    return ValidationReport(gates=tuple(gates))


def _gate_priority_cap(realistic: pd.DataFrame) -> GateResult:
    count = int((realistic.get("recommendation") == "Priority target").sum())
    return GateResult(
        "priority_cap",
        count <= MAX_PRIORITY_TARGETS,
        f"{count} Priority targets (cap {MAX_PRIORITY_TARGETS}).",
    )


def _gate_saturation(board: pd.DataFrame, column: str) -> GateResult:
    if column not in board.columns or board.empty:
        return GateResult(f"{column}_saturation", False, f"{column} column missing.")
    values = pd.to_numeric(board[column], errors="coerce")
    share = float((values >= 99.95).mean())
    return GateResult(
        f"{column}_saturation",
        share <= MAX_SATURATION_SHARE,
        f"{share * 100:.1f}% at 100 (limit {MAX_SATURATION_SHARE * 100:.0f}%).",
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
    limit = MAX_IDENTICAL_RISK_SHARE * 100
    return GateResult(
        "risk_diversity",
        share < MAX_IDENTICAL_RISK_SHARE,
        f"most common risk = {share * 100:.1f}% (limit {limit:.0f}%).",
    )


def _gate_provenance(board: pd.DataFrame) -> GateResult:
    if board.empty:
        return GateResult("recommendation_provenance", True, "empty board.")
    missing_type = board.get("candidate_type", pd.Series(dtype=object)).fillna("")
    missing_source = board.get("data_sources", pd.Series(dtype=object)).fillna("")
    bad = int(((missing_type == "") | (missing_source == "")).sum())
    return GateResult(
        "recommendation_provenance",
        bad == 0,
        f"{bad} rows missing candidate_type or data_sources.",
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
    bad_types = {
        "star_unrealistic",
        "unavailable_core_player",
        "missing_contract_status",
    }
    bad = int(realistic["candidate_type"].isin(bad_types).sum())
    return GateResult(
        "no_star_in_realistic",
        bad == 0,
        f"{bad} unrealistic/missing-contract rows on the realistic board.",
    )


def _gate_explanation_columns(board: pd.DataFrame) -> GateResult:
    missing_cols = [c for c in REQUIRED_EXPLANATION_COLUMNS if c not in board.columns]
    if missing_cols:
        return GateResult(
            "explanation_columns",
            False,
            f"missing columns: {', '.join(missing_cols)}.",
        )
    empty = 0
    for column in ("why_fit", "role_on_sixers"):
        empty += int(board[column].fillna("").astype(str).str.len().lt(3).sum())
    return GateResult(
        "explanation_columns",
        empty == 0,
        "all fit rows carry explanations."
        if empty == 0
        else f"{empty} rows missing why_fit/role_on_sixers text.",
    )


def _gate_watchlist_separation(watchlist: pd.DataFrame) -> GateResult:
    if watchlist.empty:
        return GateResult("watchlist_separation", True, "empty watchlist.")
    recs = set(watchlist.get("recommendation", pd.Series(dtype=object)).dropna())
    bad = recs & {"Priority target", "Strong fit if affordable", "Role-player target"}
    return GateResult(
        "watchlist_separation",
        not bad,
        "watchlist holds no acquisition recommendations."
        if not bad
        else f"watchlist carries recommendation labels: {bad}.",
    )


def _read(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()
