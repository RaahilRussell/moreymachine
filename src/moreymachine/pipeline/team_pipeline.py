"""Team-scoped GM product pipeline runner."""

from __future__ import annotations

import importlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import (
    SUPPORTED_TEAM_ABBRS,
    ensure_team_output_dirs,
    normalize_team,
)
from moreymachine.context.team_context import load_team_context
from moreymachine.data.lineage import (
    artifact_path,
    make_run_id,
    metadata_path,
    write_artifact,
    write_json_artifact,
    write_metadata_for_artifact,
)
from moreymachine.utils.paths import DATA_DIR, FEATURES_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DATA_DIR


@dataclass(frozen=True)
class PipelineStage:
    """Definition of one team pipeline stage."""

    name: str
    required: bool = True


@dataclass(frozen=True)
class StageResult:
    """Result from one stage."""

    stage_name: str
    status: str
    message: str
    output_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamPipelineResult:
    """End-to-end team pipeline result."""

    team: str
    run_id: str
    status: str
    stages: tuple[StageResult, ...]
    output_dir: str


STAGES: tuple[PipelineStage, ...] = (
    PipelineStage("roster_world"),
    PipelineStage("contender_blueprints"),
    PipelineStage("team_level"),
    PipelineStage("team_comparison"),
    PipelineStage("gap_model"),
    PipelineStage("player_skill_profiles"),
    PipelineStage("compatibility_matrix"),
    PipelineStage("roster_simulation"),
    PipelineStage("acquisition_feasibility"),
    PipelineStage("opportunity_cost"),
    PipelineStage("candidate_scenarios"),
    PipelineStage("candidate_rankings_v2"),
    PipelineStage("move_recommendations"),
    PipelineStage("action_cards"),
    PipelineStage("player_categorization"),
    PipelineStage("help_impact"),
    PipelineStage("fit_breakdowns"),
    PipelineStage("salary_cards"),
    PipelineStage("player_profiles"),
    PipelineStage("best_by_need"),
    PipelineStage("narratives", required=False),
    PipelineStage("scouting_reports", required=False),
    PipelineStage("validation", required=False),
)

STAGE_FUNCTIONS: dict[str, tuple[str, str]] = {
    "roster_world": ("moreymachine.context.roster_world", "build_roster_world"),
    "contender_blueprints": (
        "moreymachine.features.contender_blueprints",
        "build_contender_blueprints",
    ),
    "team_level": ("moreymachine.models.team_level", "build_team_level"),
    "team_comparison": (
        "moreymachine.models.team_comparison",
        "build_team_comparison",
    ),
    "gap_model": ("moreymachine.features.gap_model", "build_gap_model"),
    "player_skill_profiles": (
        "moreymachine.features.player_skill_profiles",
        "build_player_skill_profiles",
    ),
    "compatibility_matrix": (
        "moreymachine.features.compatibility_matrix",
        "build_compatibility_matrix",
    ),
    "roster_simulation": (
        "moreymachine.features.roster_simulation",
        "build_roster_simulation",
    ),
    "acquisition_feasibility": (
        "moreymachine.features.acquisition_feasibility",
        "build_acquisition_feasibility",
    ),
    "opportunity_cost": (
        "moreymachine.models.opportunity_cost",
        "build_opportunity_cost",
    ),
    "candidate_scenarios": (
        "moreymachine.models.scenario_engine",
        "build_candidate_scenarios",
    ),
    "candidate_rankings_v2": (
        "moreymachine.models.recommendation_engine_v2",
        "rank_candidates_v2",
    ),
    "move_recommendations": (
        "moreymachine.models.move_recommendations",
        "build_move_recommendations",
    ),
    "action_cards": ("moreymachine.models.action_cards", "build_action_cards"),
    "player_categorization": (
        "moreymachine.features.player_categorization",
        "build_player_categorization",
    ),
    "help_impact": ("moreymachine.models.help_impact", "build_help_impact"),
    "fit_breakdowns": ("moreymachine.models.fit_breakdown", "build_fit_breakdowns"),
    "salary_cards": ("moreymachine.models.salary_cards", "build_salary_cards"),
    "player_profiles": (
        "moreymachine.models.player_profile_builder",
        "build_player_profiles",
    ),
    "best_by_need": ("moreymachine.models.best_by_need", "build_best_by_need"),
    "narratives": ("moreymachine.llm.narrative_packets", "build_team_narratives"),
    "validation": ("moreymachine.product_validation", "validate_team_product"),
}

COPY_ARTIFACTS: dict[str, tuple[tuple[Path, str, str], ...]] = {
    "roster_world": (
        (PROCESSED_DATA_DIR / "roster_world_phi.parquet", "features", "roster_world.parquet"),
        (REPORTS_DATA_DIR / "roster_world_phi.md", "reports", "roster_world.md"),
    ),
    "contender_blueprints": (
        (FEATURES_DATA_DIR / "contender_blueprints.parquet", "features", "contender_blueprints.parquet"),
        (FEATURES_DATA_DIR / "team_construction_archetypes.parquet", "features", "team_construction_archetypes.parquet"),
        (REPORTS_DATA_DIR / "contender_blueprints.md", "reports", "contender_blueprints.md"),
    ),
    "team_level": (
        (REPORTS_DATA_DIR / "team_level.parquet", "reports", "team_level.parquet"),
        (REPORTS_DATA_DIR / "team_level.json", "reports", "team_level.json"),
        (REPORTS_DATA_DIR / "team_level.md", "reports", "team_level.md"),
    ),
    "team_comparison": (
        (REPORTS_DATA_DIR / "team_comparison.parquet", "reports", "team_comparison.parquet"),
        (REPORTS_DATA_DIR / "team_comparison.json", "reports", "team_comparison.json"),
    ),
    "gap_model": (
        (FEATURES_DATA_DIR / "sixers_gap_model.parquet", "features", "gap_model.parquet"),
        (REPORTS_DATA_DIR / "sixers_gap_model.md", "reports", "gap_model.md"),
    ),
    "player_skill_profiles": (
        (FEATURES_DATA_DIR / "player_skill_profiles.parquet", "features", "player_skill_profiles.parquet"),
    ),
    "compatibility_matrix": (
        (FEATURES_DATA_DIR / "candidate_core_compatibility.parquet", "features", "compatibility_matrix.parquet"),
    ),
    "roster_simulation": (
        (FEATURES_DATA_DIR / "candidate_roster_simulation.parquet", "features", "roster_simulation.parquet"),
    ),
    "acquisition_feasibility": (
        (FEATURES_DATA_DIR / "acquisition_feasibility.parquet", "features", "acquisition_feasibility.parquet"),
    ),
    "opportunity_cost": (
        (FEATURES_DATA_DIR / "opportunity_cost.parquet", "features", "opportunity_cost.parquet"),
        (REPORTS_DATA_DIR / "opportunity_cost.md", "reports", "opportunity_cost.md"),
    ),
    "candidate_scenarios": (
        (FEATURES_DATA_DIR / "candidate_scenarios.parquet", "features", "candidate_scenarios.parquet"),
    ),
    "candidate_rankings_v2": (
        (REPORTS_DATA_DIR / "candidate_fit_rankings_v2.parquet", "reports", "candidate_fit_rankings_v2.parquet"),
        (REPORTS_DATA_DIR / "candidate_fit_rankings_v2.csv", "reports", "candidate_fit_rankings_v2.csv"),
        (REPORTS_DATA_DIR / "candidate_fit_rankings_realistic_v2.parquet", "reports", "candidate_fit_rankings_realistic_v2.parquet"),
        (REPORTS_DATA_DIR / "candidate_fit_rankings_free_agents_v2.parquet", "reports", "candidate_fit_rankings_free_agents_v2.parquet"),
        (REPORTS_DATA_DIR / "candidate_fit_rankings_trade_targets_v2.parquet", "reports", "candidate_fit_rankings_trade_targets_v2.parquet"),
        (REPORTS_DATA_DIR / "candidate_fit_rankings_watchlist_v2.parquet", "reports", "candidate_fit_rankings_watchlist_v2.parquet"),
    ),
    "move_recommendations": (
        (REPORTS_DATA_DIR / "move_recommendations.parquet", "reports", "move_recommendations.parquet"),
    ),
    "action_cards": (
        (REPORTS_DATA_DIR / "action_cards.parquet", "reports", "action_cards.parquet"),
        (REPORTS_DATA_DIR / "action_cards.json", "reports", "action_cards.json"),
    ),
    "player_categorization": (
        (FEATURES_DATA_DIR / "player_categorizations.parquet", "features", "player_categorizations.parquet"),
    ),
    "help_impact": (
        (FEATURES_DATA_DIR / "player_help_impact.parquet", "features", "player_help_impact.parquet"),
    ),
    "fit_breakdowns": (
        (REPORTS_DATA_DIR / "player_fit_breakdowns.parquet", "reports", "player_fit_breakdowns.parquet"),
        (REPORTS_DATA_DIR / "player_fit_breakdowns.json", "reports", "player_fit_breakdowns.json"),
    ),
    "salary_cards": (
        (REPORTS_DATA_DIR / "player_salary_cards.parquet", "reports", "player_salary_cards.parquet"),
    ),
    "player_profiles": (
        (REPORTS_DATA_DIR / "player_profiles.parquet", "reports", "player_profiles.parquet"),
        (REPORTS_DATA_DIR / "player_profiles.json", "reports", "player_profiles.json"),
        (REPORTS_DATA_DIR / "player_profiles_index.parquet", "reports", "player_profiles_index.parquet"),
    ),
    "best_by_need": (
        (REPORTS_DATA_DIR / "best_by_need.parquet", "reports", "best_by_need.parquet"),
    ),
}


def run_team_pipeline(
    team: str,
    skip_refresh: bool = False,
    stages: list[str] | None = None,
    force: bool = False,
    no_ollama: bool = False,
) -> TeamPipelineResult:
    """Run team-scoped pipeline stages."""
    normalized = normalize_team(team)
    context = load_team_context(normalized)
    run_id = make_run_id()
    ensure_team_output_dirs(normalized)
    requested = set(stages or [stage.name for stage in STAGES])
    results: list[StageResult] = []
    for stage in STAGES:
        if stage.name not in requested:
            continue
        result = run_stage(
            stage.name,
            normalized,
            context,
            run_id=run_id,
            skip_refresh=skip_refresh,
            force=force,
            no_ollama=no_ollama,
        )
        results.append(result)
    status = "success" if all(r.status == "success" for r in results) else "warning"
    summary = TeamPipelineResult(
        team=normalized,
        run_id=run_id,
        status=status,
        stages=tuple(results),
        output_dir=str(ensure_team_output_dirs(normalized)["root"]),
    )
    write_json_artifact(
        _result_payload(summary),
        artifact_path(normalized, "metadata", "pipeline_run.json"),
        _base_metadata(normalized, run_id, "pipeline_run"),
    )
    return summary


def run_stage(
    stage_name: str,
    team: str,
    context: dict[str, Any],
    *,
    run_id: str | None = None,
    skip_refresh: bool = False,
    force: bool = False,
    no_ollama: bool = False,
) -> StageResult:
    """Run one stage and copy any known global artifacts into team outputs."""
    normalized = normalize_team(team)
    run_id = run_id or make_run_id()
    output_paths: list[str] = []
    try:
        _call_stage_function(
            stage_name,
            normalized,
            context,
            skip_refresh=skip_refresh,
            force=force,
            no_ollama=no_ollama,
        )
        output_paths.extend(_copy_stage_artifacts(stage_name, normalized, run_id))
        status = "success"
        message = f"{stage_name} complete"
    except ModuleNotFoundError as exc:
        status = "warning"
        message = f"{stage_name} partial: module not available ({exc.name})"
        _write_partial_stage_artifact(normalized, stage_name, run_id, message)
    except FileNotFoundError as exc:
        status = "warning"
        message = f"{stage_name} partial: missing {exc.filename or exc}"
        _write_partial_stage_artifact(normalized, stage_name, run_id, message)
    except Exception as exc:  # pragma: no cover - defensive pipeline boundary
        status = "warning"
        message = f"{stage_name} warning: {type(exc).__name__}: {exc}"
        _write_partial_stage_artifact(normalized, stage_name, run_id, message)
    result = StageResult(stage_name, status, message, tuple(output_paths))
    write_json_artifact(
        asdict(result),
        artifact_path(normalized, "metadata", f"{stage_name}.json"),
        _base_metadata(normalized, run_id, stage_name),
    )
    return result


def _call_stage_function(
    stage_name: str,
    team: str,
    context: dict[str, Any],
    *,
    skip_refresh: bool,
    force: bool,
    no_ollama: bool,
) -> None:
    if stage_name == "scouting_reports":
        _copy_scouting_reports(team)
        return
    target = STAGE_FUNCTIONS.get(stage_name)
    if target is None:
        return
    module_name, function_name = target
    module = importlib.import_module(module_name)
    func = getattr(module, function_name)
    kwargs_options = (
        {"team": team, "context": context, "no_ollama": no_ollama},
        {"team": team, "context": context},
        {"team": team, "skip_refresh": skip_refresh, "force": force},
        {"team": team},
        {},
    )
    last_error: TypeError | None = None
    for kwargs in kwargs_options:
        try:
            func(**kwargs)
            return
        except TypeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error


def _copy_stage_artifacts(stage_name: str, team: str, run_id: str) -> list[str]:
    outputs: list[str] = []
    for source, kind, filename in COPY_ARTIFACTS.get(stage_name, ()):
        if not source.exists():
            continue
        destination = artifact_path(team, kind, filename)
        _copy_artifact(source, destination, team, run_id)
        outputs.append(str(destination))
    return outputs


def _copy_artifact(source: Path, destination: Path, team: str, run_id: str) -> None:
    metadata = _base_metadata(team, run_id, destination.stem)
    metadata["source_files"] = [str(source)]
    metadata["upstream_artifacts"] = [str(source)]
    if source.suffix in {".parquet", ".csv"}:
        frame = pd.read_parquet(source) if source.suffix == ".parquet" else pd.read_csv(source)
        _ensure_common_columns(frame, team, run_id)
        write_artifact(frame, destination, metadata)
    elif source.suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        write_json_artifact(payload, destination, metadata)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        write_metadata_for_artifact(
            destination,
            run_id=run_id,
            source_files=(source,),
            upstream_artifacts=(source,),
            known_limitations=("Copied from global PHI artifact into team-scoped output.",),
        )


def _ensure_common_columns(frame: pd.DataFrame, team: str, run_id: str) -> None:
    if "data_mode" not in frame.columns:
        frame["data_mode"] = "derived"
    if "source_summary" not in frame.columns:
        frame["source_summary"] = "team_pipeline"
    if "run_id" not in frame.columns:
        frame["run_id"] = run_id
    if "created_at" not in frame.columns and "pulled_at" not in frame.columns:
        frame["created_at"] = datetime.now(UTC).isoformat()
    if "missing_data_flags" not in frame.columns:
        frame["missing_data_flags"] = "none"
    if "confidence" not in frame.columns:
        frame["confidence"] = "Medium"
    if "evidence" not in frame.columns:
        frame["evidence"] = f"Copied into {team} team-scoped pipeline output."


def _copy_scouting_reports(team: str) -> None:
    source_dir = REPORTS_DATA_DIR / "scouting_reports"
    destination = ensure_team_output_dirs(team)["scouting_reports"]
    if not source_dir.exists():
        return
    for path in source_dir.glob("*.md"):
        shutil.copy2(path, destination / path.name)


def _write_partial_stage_artifact(
    team: str,
    stage_name: str,
    run_id: str,
    message: str,
) -> None:
    payload = {
        "team": team,
        "stage": stage_name,
        "status": "partial",
        "message": message,
        "confidence": "Low",
        "missing_data_flags": "stage_partial",
        "evidence": "Pipeline recorded a partial stage instead of inventing data.",
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
    }
    write_json_artifact(
        payload,
        artifact_path(team, "metadata", f"{stage_name}_partial.json"),
        _base_metadata(team, run_id, f"{stage_name}_partial"),
    )


def _base_metadata(team: str, run_id: str, artifact_name: str) -> dict[str, Any]:
    return {
        "artifact_name": artifact_name,
        "team": team,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source_files": [],
        "source_urls": [],
        "upstream_artifacts": [],
        "data_mode": "derived",
        "known_limitations": [
            "Team-scoped output is generated from cached local artifacts.",
            "No live API calls are made inside Streamlit page loads.",
        ],
    }


def _result_payload(result: TeamPipelineResult) -> dict[str, Any]:
    return {
        "team": result.team,
        "run_id": result.run_id,
        "status": result.status,
        "output_dir": result.output_dir,
        "stages": [asdict(stage) for stage in result.stages],
    }


def available_pipeline_teams(team: str) -> list[str]:
    """Expand ALL into supported teams."""
    normalized = normalize_team(team)
    if normalized == "ALL":
        return list(SUPPORTED_TEAM_ABBRS)
    return [normalized]
