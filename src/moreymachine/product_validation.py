"""GM product validation suite."""

from __future__ import annotations

import json
import py_compile
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import ensure_team_output_dirs, normalize_team
from moreymachine.data.lineage import make_run_id, write_json_artifact


@dataclass(frozen=True)
class ProductValidationFailure:
    """One product validation failure."""

    gate: str
    message: str


@dataclass(frozen=True)
class ProductValidationResult:
    """Product validation result."""

    team: str
    passed: bool
    failures: tuple[ProductValidationFailure, ...]
    report_path: str
    json_path: str

    def to_markdown(self) -> str:
        lines = [
            f"# {self.team} Product Validation v2",
            "",
            f"Passed: {self.passed}",
            "",
        ]
        if not self.failures:
            lines.append("No validation failures.")
        else:
            lines.extend(f"- {failure.gate}: {failure.message}" for failure in self.failures)
        return "\n".join(lines)


REQUIRED_TEAM_ARTIFACTS = (
    "reports/team_level.parquet",
    "reports/team_level.json",
    "reports/team_comparison.parquet",
    "features/gap_model.parquet",
    "reports/move_recommendations.parquet",
    "reports/action_cards.parquet",
    "reports/action_cards.json",
    "reports/candidate_fit_rankings_v2.parquet",
    "reports/player_profiles.parquet",
)


def validate_team_product(
    *,
    team: str = "PHI",
    context: dict[str, Any] | None = None,
) -> ProductValidationResult:
    """Validate the generated GM operating-system product."""
    normalized = normalize_team(team)
    root = ensure_team_output_dirs(normalized)["root"]
    failures: list[ProductValidationFailure] = []
    _check_app_compile(failures)
    _check_duplicate_widget_keys(failures)
    _check_artifacts(root, failures)

    rankings = _read_frame(root / "reports/candidate_fit_rankings_v2.parquet")
    profiles = _read_frame(root / "reports/player_profiles.parquet")
    moves = _read_frame(root / "reports/move_recommendations.parquet")
    action_cards = _read_frame(root / "reports/action_cards.parquet")
    realistic = _read_frame(root / "reports/candidate_fit_rankings_realistic_v2.parquet")

    if not rankings.empty:
        _check_rankings(rankings, failures)
    if not profiles.empty:
        _check_profiles(profiles, failures)
    if not moves.empty:
        _check_moves(moves, failures)
    if not action_cards.empty:
        _check_action_cards(action_cards, failures)
    if not realistic.empty:
        _check_realistic_board(realistic, failures)
    _check_narrative(root, failures)

    report_path = root / "reports/product_validation_v2.md"
    json_path = root / "metadata/product_validation_v2.json"
    result = ProductValidationResult(
        team=normalized,
        passed=not failures,
        failures=tuple(failures),
        report_path=str(report_path),
        json_path=str(json_path),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result.to_markdown(), encoding="utf-8")
    write_json_artifact(
        {
            "team": normalized,
            "passed": result.passed,
            "failures": [asdict(failure) for failure in failures],
            "created_at": datetime.now(UTC).isoformat(),
        },
        json_path,
        {
            "artifact_name": "product_validation_v2",
            "team": normalized,
            "run_id": make_run_id(),
            "created_at": datetime.now(UTC).isoformat(),
            "source_files": [str(root)],
            "upstream_artifacts": list(REQUIRED_TEAM_ARTIFACTS),
            "data_mode": "derived",
            "known_limitations": [
                "Validation checks product contracts and guardrails, not basketball truth.",
            ],
        },
    )
    return result


def _check_app_compile(failures: list[ProductValidationFailure]) -> None:
    try:
        py_compile.compile("src/moreymachine/app/streamlit_app.py", doraise=True)
    except py_compile.PyCompileError as exc:
        failures.append(ProductValidationFailure("app_compile", str(exc)))


def _check_duplicate_widget_keys(failures: list[ProductValidationFailure]) -> None:
    text = Path("src/moreymachine/app/streamlit_app.py").read_text(encoding="utf-8")
    keys = re.findall(r"key=[\"']([^\"']+)[\"']", text)
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        failures.append(
            ProductValidationFailure(
                "duplicate_widget_keys",
                "Duplicate literal Streamlit keys: " + ", ".join(duplicates),
            )
        )


def _check_artifacts(root: Path, failures: list[ProductValidationFailure]) -> None:
    if not root.exists():
        failures.append(ProductValidationFailure("team_output_dir", f"{root} missing"))
    for relative in REQUIRED_TEAM_ARTIFACTS:
        path = root / relative
        if not path.exists():
            failures.append(ProductValidationFailure("required_artifact", f"{relative} missing"))


def _check_rankings(
    rankings: pd.DataFrame,
    failures: list[ProductValidationFailure],
) -> None:
    if "player_profile_id" not in rankings.columns or rankings["player_profile_id"].fillna("").eq("").any():
        failures.append(ProductValidationFailure("candidate_profile_id", "Every candidate row needs player_profile_id."))
    priority = rankings[rankings["recommendation"].eq("Priority Target")]
    if not priority.empty:
        stale = priority["missing_data_flags"].fillna("").str.contains("stale|unknown|manual|conflict", case=False)
        if stale.any():
            failures.append(ProductValidationFailure("priority_unknown_or_stale_status", "Priority Target has stale/unknown/manual status flag."))
        if "no_clear_role" in priority.columns and priority["no_clear_role"].fillna(False).astype(bool).any():
            failures.append(ProductValidationFailure("priority_no_clear_role", "Priority Target has no_clear_role."))
        bad_types = {"star_unrealistic", "core_unavailable", "manual_watchlist", "missing_contract_status"}
        if priority["candidate_type"].isin(bad_types).any():
            failures.append(ProductValidationFailure("priority_theoretical_or_unavailable", "Priority Target has unavailable/theoretical candidate type."))
    _check_center_starter(rankings, "rankings", failures)


def _check_profiles(
    profiles: pd.DataFrame,
    failures: list[ProductValidationFailure],
) -> None:
    required = (
        "score_breakdown_json",
        "help_areas_json",
        "does_not_help_json",
        "salary_card_json",
        "best_case_scenario",
        "realistic_scenario",
        "downside_scenario",
        "playoff_scenario",
    )
    for column in required:
        if column not in profiles.columns or profiles[column].fillna("").astype(str).eq("").any():
            failures.append(ProductValidationFailure("profile_schema", f"profile missing {column}"))
    salary_missing = _column(profiles, "salary_card_json").fillna("").astype(str).eq("{}")
    flags = _column(profiles, "missing_data_flags").fillna("").astype(str)
    if salary_missing.any() and not flags.str.contains("salary|cap_hit|contract", case=False).any():
        failures.append(ProductValidationFailure("profile_salary_flag", "Missing salary card lacks salary/contract flag."))
    if _frame_contains_text(profiles, "No major concerns"):
        failures.append(ProductValidationFailure("empty_concern_text", "Profile contains 'No major concerns'."))
    _check_center_starter(profiles, "profiles", failures)


def _check_moves(
    moves: pd.DataFrame,
    failures: list[ProductValidationFailure],
) -> None:
    for column in ("why_do_this", "why_not_do_this", "evidence"):
        if column not in moves.columns or moves[column].fillna("").astype(str).eq("").any():
            failures.append(ProductValidationFailure("move_evidence", f"move row missing {column}"))
    if _frame_contains_text(moves, "No major concerns"):
        failures.append(ProductValidationFailure("move_empty_concern_text", "Move contains 'No major concerns'."))


def _check_action_cards(
    cards: pd.DataFrame,
    failures: list[ProductValidationFailure],
) -> None:
    required_categories = {
        "best_overall_action",
        "best_realistic_free_agent",
        "best_realistic_trade",
        "best_low_cost_depth",
        "best_backup_center_route",
        "best_wing_defense_route",
        "best_shooting_route",
        "best_internal_or_stay_put",
        "top_avoid_move",
        "manual_review_action",
    }
    categories = set(cards.get("action_category", pd.Series(dtype=str)).astype(str))
    missing = sorted(required_categories - categories)
    if missing:
        failures.append(ProductValidationFailure("action_card_categories", "Missing categories: " + ", ".join(missing)))
    for column in ("why_do_this", "why_not_do_this", "evidence"):
        if column not in cards.columns or cards[column].fillna("").astype(str).eq("").any():
            failures.append(ProductValidationFailure("action_card_evidence", f"action card missing {column}"))


def _check_realistic_board(
    realistic: pd.DataFrame,
    failures: list[ProductValidationFailure],
) -> None:
    theoretical = {"star_unrealistic", "core_unavailable", "manual_watchlist", "unavailable_core_player"}
    if "candidate_type" in realistic.columns and realistic["candidate_type"].isin(theoretical).any():
        failures.append(ProductValidationFailure("theoretical_in_realistic_board", "Theoretical-only player appears in realistic board."))


def _check_narrative(root: Path, failures: list[ProductValidationFailure]) -> None:
    narrative = root / "narratives/gm_executive_summary.md"
    fallback = root / "narratives/deterministic_fallback_summary.md"
    if not narrative.exists() and not fallback.exists():
        failures.append(ProductValidationFailure("gm_narrative", "No GM narrative or deterministic fallback exists."))


def _check_center_starter(
    frame: pd.DataFrame,
    label: str,
    failures: list[ProductValidationFailure],
) -> None:
    if not {"position", "starter_possible", "two_big_compatible"}.issubset(frame.columns):
        return
    position = frame["position"].fillna("").astype(str)
    starter = frame["starter_possible"].fillna(False).astype(bool)
    two_big = frame["two_big_compatible"].fillna(False).astype(bool)
    conflict = position.str.contains("C") & starter & ~two_big
    if conflict.any():
        failures.append(ProductValidationFailure("phi_center_starter_conflict", f"{label} has center starter without two-big compatibility."))


def _read_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series([""] * len(frame), index=frame.index, dtype=object)


def _frame_contains_text(frame: pd.DataFrame, needle: str) -> bool:
    if frame.empty:
        return False
    text = frame.fillna("").apply(
        lambda row: " ".join(str(value) for value in row.to_list()),
        axis=1,
    )
    return bool(text.str.contains(needle, case=False, regex=False).any())
