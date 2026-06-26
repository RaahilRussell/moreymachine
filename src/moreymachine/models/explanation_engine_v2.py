"""Evidence-based explanation engine v2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.data.lineage import new_run_id, write_metadata_for_artifact
from moreymachine.features.acquisition_feasibility import ACQUISITION_FEASIBILITY_PATH
from moreymachine.features.player_skill_profiles import PLAYER_SKILL_PROFILES_PATH
from moreymachine.models.recommendation_engine_v2 import CANDIDATE_FIT_RANKINGS_V2_PATH
from moreymachine.models.scenario_engine import CANDIDATE_SCENARIOS_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

EXPLANATION_CLAIMS_PATH = REPORTS_DATA_DIR / "explanation_claims.parquet"
EVIDENCE_OBJECTS_PATH = REPORTS_DATA_DIR / "evidence_objects.parquet"
PLAYER_EXPLANATIONS_V2_PATH = REPORTS_DATA_DIR / "player_explanations_v2.parquet"


@dataclass(frozen=True)
class ExplanationBuildResult:
    """Summary from building explanation artifacts."""

    claims: int
    evidence_objects: int
    player_explanations: int
    claims_path: Path
    evidence_path: Path
    explanations_path: Path


def build_explanations_v2(
    *,
    rankings_path: str | Path = CANDIDATE_FIT_RANKINGS_V2_PATH,
    skill_profiles_path: str | Path = PLAYER_SKILL_PROFILES_PATH,
    acquisition_path: str | Path = ACQUISITION_FEASIBILITY_PATH,
    scenarios_path: str | Path = CANDIDATE_SCENARIOS_PATH,
    claims_path: str | Path = EXPLANATION_CLAIMS_PATH,
    evidence_path: str | Path = EVIDENCE_OBJECTS_PATH,
    explanations_path: str | Path = PLAYER_EXPLANATIONS_V2_PATH,
) -> ExplanationBuildResult:
    """Build claim, evidence, and player explanation artifacts."""
    rankings = pd.read_parquet(rankings_path)
    skills = pd.read_parquet(skill_profiles_path)
    acquisition = pd.read_parquet(acquisition_path)
    scenarios = pd.read_parquet(scenarios_path)
    frame = rankings.merge(skills, on="player_id", how="left", suffixes=("", "_skill"))
    frame = frame.merge(
        acquisition,
        left_on="player_id",
        right_on="candidate_id",
        how="left",
        suffixes=("", "_acquisition"),
    )
    scenario_lookup = _scenario_lookup(scenarios)
    claim_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    explanation_rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        claims, evidence = _claims_and_evidence(row, scenario_lookup)
        claim_rows.extend(claims)
        evidence_rows.extend(evidence)
        explanation_rows.append(
            _player_explanation(row, claims, evidence, scenario_lookup)
        )

    claims_frame = pd.DataFrame(claim_rows)
    evidence_frame = pd.DataFrame(evidence_rows)
    explanation_frame = pd.DataFrame(explanation_rows)
    claim_output = Path(claims_path)
    evidence_output = Path(evidence_path)
    explanation_output = Path(explanations_path)
    for path in (claim_output, evidence_output, explanation_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    claims_frame.to_parquet(claim_output, index=False)
    evidence_frame.to_parquet(evidence_output, index=False)
    explanation_frame.to_parquet(explanation_output, index=False)

    run_id = new_run_id()
    for artifact in (claim_output, evidence_output, explanation_output):
        write_metadata_for_artifact(
            artifact,
            run_id=run_id,
            source_files=(
                rankings_path,
                skill_profiles_path,
                acquisition_path,
                scenarios_path,
            ),
            upstream_artifacts=(
                rankings_path,
                skill_profiles_path,
                acquisition_path,
                scenarios_path,
            ),
            known_limitations=(
                "Explanations can only claim what structured evidence supports.",
                "Missing or stale data is surfaced rather than inferred.",
            ),
        )

    return ExplanationBuildResult(
        claims=len(claims_frame),
        evidence_objects=len(evidence_frame),
        player_explanations=len(explanation_frame),
        claims_path=claim_output,
        evidence_path=evidence_output,
        explanations_path=explanation_output,
    )


def _claims_and_evidence(
    row: dict[str, Any], scenario_lookup: dict[int, dict[str, dict[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims = []
    evidence = []
    for spec in _claim_specs(row, scenario_lookup):
        evidence_id = _evidence_id(row["player_id"], spec["claim_type"])
        evidence.append(
            {
                "evidence_id": evidence_id,
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "claim": spec["claim"],
                "evidence_type": spec["evidence_type"],
                "supporting_columns": json.dumps(spec["supporting_columns"]),
                "supporting_values": json.dumps(
                    spec["supporting_values"], sort_keys=True
                ),
                "source": spec["source"],
                "source_url": row.get("source_url") or "",
                "confidence": spec["confidence"],
                "pulled_at": datetime.now(UTC).date().isoformat(),
                "data_mode": "derived",
                "missing_data_flags": spec["missing_data_flags"],
            }
        )
        claims.append(
            {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "claim": spec["claim"],
                "claim_type": spec["claim_type"],
                "allowed": spec["allowed"],
                "evidence_object_ids": json.dumps([evidence_id]),
                "confidence": spec["confidence"],
                "source": spec["source"],
                "pulled_at": datetime.now(UTC).date().isoformat(),
                "data_mode": "derived",
                "missing_data_flags": spec["missing_data_flags"],
            }
        )
    return claims, evidence


def _claim_specs(
    row: dict[str, Any], scenario_lookup: dict[int, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    player_id = int(row["player_id"])
    scenarios = scenario_lookup.get(player_id, {})
    primary_slot = row.get("primary_roster_slot")
    role = row.get("expected_role_on_phi")
    recommendation = row.get("recommendation")
    gaps = _json_list(row.get("gaps_addressed"))
    missing_flags = _missing_flags(row)
    specs = [
        _spec(
            row,
            "recommendation",
            f"Recommendation is {recommendation}.",
            True,
            [
                "final_recommendation_score",
                "recommendation",
                "recommendation_confidence",
            ],
            {
                "score": row.get("final_recommendation_score"),
                "recommendation": recommendation,
                "confidence": row.get("recommendation_confidence"),
            },
        ),
        _spec(
            row,
            "role",
            f"Projected role is {role}.",
            bool(primary_slot and primary_slot != "no_clear_role"),
            ["primary_roster_slot", "expected_role_on_phi", "role_confidence"],
            {
                "primary_roster_slot": primary_slot,
                "expected_role_on_phi": role,
                "role_confidence": row.get("role_confidence"),
            },
        ),
        _spec(
            row,
            "starter",
            _starter_claim(row),
            bool(row.get("starter_possible")),
            ["starter_possible", "primary_roster_slot", "contradiction_flags"],
            {
                "starter_possible": bool(row.get("starter_possible")),
                "primary_roster_slot": primary_slot,
                "contradiction_flags": row.get("contradiction_flags"),
            },
        ),
        _skill_claim(row, "spacing", "spot_up_spacing", "spaces the floor"),
        _skill_claim(row, "rim_protection", "rim_protection", "protects the rim"),
        _skill_claim(row, "wing_defense", "wing_defense_proxy", "adds wing defense"),
        _skill_claim(
            row,
            "creation",
            "secondary_creation",
            "adds secondary creation",
        ),
        _skill_claim(
            row,
            "rebounding",
            "defensive_rebounding",
            "helps defensive rebounding",
        ),
        _spec(
            row,
            "playoff_rotation",
            _playoff_claim(row),
            bool(row.get("playoff_rotation_possible")),
            ["playoff_rotation_possible", "playoff_role_score"],
            {
                "playoff_rotation_possible": bool(row.get("playoff_rotation_possible")),
                "playoff_role_score": row.get("playoff_role_score"),
            },
        ),
        _spec(
            row,
            "acquisition",
            _acquisition_claim(row),
            not bool(row.get("manual_review_required")),
            [
                "acquisition_path",
                "acquisition_feasibility_score",
                "manual_review_required",
            ],
            {
                "acquisition_path": row.get("acquisition_path"),
                "feasibility_score": row.get("acquisition_feasibility_score"),
                "manual_review_required": bool(row.get("manual_review_required")),
            },
        ),
        _spec(
            row,
            "missing_data",
            _missing_claim(missing_flags),
            True,
            ["missing_data_flags"],
            {"missing_data_flags": missing_flags},
            confidence="Low" if missing_flags else "High",
            missing_flags=";".join(missing_flags) if missing_flags else "none",
        ),
    ]
    if scenarios:
        realistic = scenarios.get("realistic_case", {})
        specs.append(
            _spec(
                row,
                "primary_scenario",
                realistic.get("upside_case", row.get("realistic_case") or ""),
                bool(realistic),
                ["primary_scenario", "realistic_case"],
                {
                    "primary_scenario": row.get("primary_scenario"),
                    "realistic_case": row.get("realistic_case"),
                },
                source="candidate_scenarios",
            )
        )
    if gaps:
        specs.append(
            _spec(
                row,
                "gaps_addressed",
                f"Addresses: {', '.join(gaps[:4])}.",
                True,
                ["gaps_addressed", "gap_match_score"],
                {"gaps_addressed": gaps, "gap_match_score": row.get("gap_match_score")},
            )
        )
    return specs


def _spec(
    row: dict[str, Any],
    claim_type: str,
    claim: str,
    allowed: bool,
    supporting_columns: list[str],
    supporting_values: dict[str, Any],
    *,
    evidence_type: str = "structured_artifact",
    source: str = "candidate_fit_rankings_v2",
    confidence: str | None = None,
    missing_flags: str | None = None,
) -> dict[str, Any]:
    return {
        "claim_type": claim_type,
        "claim": claim,
        "allowed": bool(allowed),
        "evidence_type": evidence_type,
        "supporting_columns": supporting_columns,
        "supporting_values": supporting_values,
        "source": source,
        "confidence": confidence or row.get("recommendation_confidence") or "Medium",
        "missing_data_flags": missing_flags or row.get("missing_data_flags") or "none",
    }


def _skill_claim(
    row: dict[str, Any], claim_type: str, dimension: str, allowed_phrase: str
) -> dict[str, Any]:
    allowed = bool(row.get(f"{dimension}_claim_allowed"))
    if allowed:
        claim = f"{allowed_phrase}."
    else:
        claim = f"Cannot verify that he {allowed_phrase}."
    return _spec(
        row,
        claim_type,
        claim,
        allowed,
        [
            dimension,
            f"{dimension}_claim_allowed",
            f"{dimension}_evidence_stat_1",
            f"{dimension}_evidence_stat_2",
            f"{dimension}_evidence_stat_3",
        ],
        {
            "score": row.get(dimension),
            "claim_allowed": allowed,
            "evidence_stat_1": row.get(f"{dimension}_evidence_stat_1"),
            "evidence_stat_2": row.get(f"{dimension}_evidence_stat_2"),
            "evidence_stat_3": row.get(f"{dimension}_evidence_stat_3"),
        },
        source="player_skill_profiles",
        confidence=row.get(f"{dimension}_confidence") or "Medium",
        missing_flags=row.get(f"{dimension}_missing_data_flags") or "none",
    )


def _starter_claim(row: dict[str, Any]) -> str:
    if bool(row.get("starter_possible")):
        return "Starter projection is allowed by the simulated roster slot."
    return "Do not project as a starter from current roster simulation."


def _playoff_claim(row: dict[str, Any]) -> str:
    if bool(row.get("playoff_rotation_possible")):
        return "Has a simulated playoff-rotation pathway."
    return "Playoff-rotation claim is not verified."


def _acquisition_claim(row: dict[str, Any]) -> str:
    if bool(row.get("manual_review_required")):
        return "Acquisition status requires manual review before recommendation."
    return (
        f"Acquisition path is {row.get('acquisition_path')} with feasibility "
        f"{row.get('acquisition_feasibility_score')}."
    )


def _missing_claim(flags: list[str]) -> str:
    if not flags:
        return "No critical missing data flags were generated."
    return "Missing or stale data flags: " + ", ".join(flags[:6])


def _player_explanation(
    row: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    scenario_lookup: dict[int, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    player_id = int(row["player_id"])
    scenarios = scenario_lookup.get(player_id, {})
    allowed_claims = [claim["claim"] for claim in claims if claim["allowed"]]
    blocked_claims = [claim["claim"] for claim in claims if not claim["allowed"]]
    realistic = scenarios.get("realistic_case", {})
    bad_fit = scenarios.get("bad_fit_case", {})
    missing_flags = _missing_flags(row)
    return {
        "player_id": player_id,
        "player_name": row.get("player_name"),
        "executive_summary": _executive_summary(row),
        "role_on_sixers": row.get("expected_role_on_phi"),
        "primary_scenario_explanation": realistic.get(
            "upside_case", row.get("realistic_case") or ""
        ),
        "why_the_model_likes_him": _why_like(row, allowed_claims),
        "what_he_helps_most": _json_text(row.get("gaps_addressed")),
        "what_he_does_not_solve": _json_text(row.get("gaps_not_addressed")),
        "fit_with_embiid": row.get("compatibility_with_embiid"),
        "fit_with_maxey": row.get("compatibility_with_maxey"),
        "fit_with_george": row.get("compatibility_with_george"),
        "lineup_context": row.get("expected_minutes_context"),
        "contract_and_acquisition_context": _acquisition_claim(row),
        "main_concerns": _concerns(row, bad_fit, blocked_claims),
        "missing_or_stale_data": _missing_claim(missing_flags),
        "why_this_could_be_wrong": _why_wrong(row, bad_fit),
        "recommendation_interpretation": _recommendation_interpretation(row),
        "evidence_table": json.dumps(evidence, sort_keys=True),
        "confidence": row.get("recommendation_confidence"),
    }


def _executive_summary(row: dict[str, Any]) -> str:
    return (
        f"{row.get('player_name')} is a {row.get('recommendation')} as "
        f"{row.get('expected_role_on_phi')} with score "
        f"{row.get('final_recommendation_score')}."
    )


def _why_like(row: dict[str, Any], allowed_claims: list[str]) -> str:
    claims = [claim for claim in allowed_claims if "Cannot verify" not in claim]
    if not claims:
        return "The model does not have enough supported claims for a strong case."
    return " ".join(claims[:3])


def _concerns(
    row: dict[str, Any], bad_fit: dict[str, Any], blocked_claims: list[str]
) -> str:
    pieces = []
    flags = _json_list(row.get("contradiction_flags"))
    if flags:
        pieces.append("Contradictions: " + ", ".join(flags[:4]))
    if blocked_claims:
        pieces.append("Unsupported claims: " + " ".join(blocked_claims[:3]))
    if bad_fit:
        pieces.append(str(bad_fit.get("downside_case") or ""))
    return (
        " ".join(piece for piece in pieces if piece) or "Concerns are evidence-limited."
    )


def _why_wrong(row: dict[str, Any], bad_fit: dict[str, Any]) -> str:
    if bool(row.get("manual_review_required")):
        return "Status or contract data may be stale enough to change the board."
    if bad_fit:
        return str(bad_fit.get("risk_case") or "Scenario assumptions may fail.")
    return "The role, price, or playoff translation could be wrong."


def _recommendation_interpretation(row: dict[str, Any]) -> str:
    recommendation = row.get("recommendation")
    if recommendation == "Priority Target":
        return (
            "High-confidence role fit with feasible acquisition and few contradictions."
        )
    if recommendation == "Strong Fit If Affordable":
        return (
            "Basketball fit is strong, but price or availability controls the answer."
        )
    if recommendation == "Role-Player Target":
        return "Useful role fit, not a complete roster solution."
    if recommendation == "Only If Cheap":
        return "Worth considering only if cost stays below the projected role."
    if recommendation == "Manual Review Required":
        return "Do not treat as a recommendation until status data is checked."
    if recommendation == "Unrealistic / Unavailable":
        return "Theoretical fit or talent, not a realistic acquisition recommendation."
    return "The model does not recommend pursuing this player from current evidence."


def _scenario_lookup(frame: pd.DataFrame) -> dict[int, dict[str, dict[str, Any]]]:
    lookup: dict[int, dict[str, dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        lookup.setdefault(int(row["player_id"]), {})[str(row["scenario_type"])] = row
    return lookup


def _evidence_id(player_id: Any, claim_type: str) -> str:
    return f"{player_id}_{claim_type}"


def _missing_flags(row: dict[str, Any]) -> list[str]:
    flags = _split_flags(row.get("missing_data_flags"))
    return sorted(flag for flag in flags if flag != "none")


def _json_list(value: Any) -> list[str]:
    if not value or pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        return [str(item) for item in json.loads(value)]
    except (TypeError, json.JSONDecodeError):
        return [str(value)]


def _json_text(value: Any) -> str:
    items = _json_list(value)
    return ", ".join(items) if items else "none identified"


def _split_flags(value: Any) -> list[str]:
    if value in (None, "", "none") or pd.isna(value):
        return []
    return [part for part in str(value).split(";") if part and part != "none"]
