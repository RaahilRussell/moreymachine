"""Synthetic v2 artifact helpers for reasoning validation tests."""

from __future__ import annotations

import json

import pandas as pd


def base_reasoning_frames() -> dict[str, pd.DataFrame]:
    """Return a minimal internally consistent v2 artifact set."""
    rankings = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "position": "F",
                "candidate_type": "realistic_trade_target",
                "board_type": "realistic",
                "recommendation": "Role-Player Target",
                "primary_roster_slot": "low_usage_spacer",
                "primary_scenario": "1_realistic_case",
                "scenario_robustness_score": 70.0,
                "acquisition_feasibility_score": 70.0,
                "manual_review_required": False,
                "missing_data_flags": "none",
                "gaps_addressed": json.dumps(["Role-player shooting volume"]),
                "fit_with_embiid": "70.0 / positive",
                "fit_with_maxey": "70.0 / positive",
                "fit_with_george": "70.0 / positive",
                "starter_possible": False,
                "two_big_compatible": False,
                "contradiction_flags": json.dumps([]),
                "final_recommendation_score": 61.0,
            }
        ]
    )
    claim_specs = [
        ("spacing", True, "spaces the floor."),
        ("rim_protection", False, "Cannot verify that he protects the rim."),
        ("wing_defense", False, "Cannot verify that he adds wing defense."),
        (
            "point_of_attack_defense",
            False,
            "Cannot verify that he adds point-of-attack defense.",
        ),
        ("creation", False, "Cannot verify that he adds secondary creation."),
        ("rebounding", False, "Cannot verify that he helps defensive rebounding."),
        (
            "starter",
            False,
            "Do not project as a starter from current roster simulation.",
        ),
    ]
    claims = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "claim_type": claim_type,
                "claim": claim,
                "allowed": allowed,
                "evidence_object_ids": json.dumps([f"1_{claim_type}"]),
            }
            for claim_type, allowed, claim in claim_specs
        ]
    )
    evidence = pd.DataFrame(
        [
            {
                "evidence_id": f"1_{claim_type}",
                "player_id": 1,
                "player_name": "Test Wing",
                "claim": claim,
                "evidence_type": "structured_artifact",
                "supporting_columns": json.dumps(["test"]),
                "supporting_values": json.dumps({"test": True}),
                "source": "test",
                "confidence": "Medium",
                "missing_data_flags": "none",
            }
            for claim_type, _, claim in claim_specs
        ]
    )
    profiles = pd.DataFrame(
        [
            {
                "player_profile_id": "1-test-wing",
                "player_id": 1,
                "player_name": "Test Wing",
                "position": "F",
                "recommendation": "Role-Player Target",
                "explanation_confidence": "Medium",
                "missing_data_flags": "none",
                "primary_roster_slot": "low_usage_spacer",
                "starter_possible": False,
                "two_big_compatible": False,
                "contradiction_flags": json.dumps([]),
                "top_gaps_helped": "Role-player shooting volume",
                "gaps_not_helped": "Wing defense",
                "fit_with_embiid": "70.0 / positive",
                "fit_with_maxey": "70.0 / positive",
                "fit_with_george": "70.0 / positive",
                "realistic_scenario": json.dumps({"scenario_type": "realistic_case"}),
                "best_case_scenario": json.dumps({"scenario_type": "best_case"}),
                "executive_summary": "Test Wing has a narrow role-player case.",
                "why_the_model_likes_him": "Test Wing has verified spacing.",
                "main_concerns": "Test Wing: cost and role must stay narrow.",
                "why_this_could_be_wrong": "The role could be too small.",
                "recommendation_interpretation": "Useful role fit.",
                "evidence_summary": "spacing evidence",
            }
        ]
    )
    profile_index = pd.DataFrame(
        [
            {
                "player_profile_id": "1-test-wing",
                "player_id": 1,
                "player_name": "Test Wing",
                "profile_path": "data/reports/scouting_reports/1-test-wing.md",
            }
        ]
    )
    salary_cards = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "cap_hit_millions": 5.0,
                "salary_warning_flags": json.dumps([]),
                "missing_data_flags": "none",
            }
        ]
    )
    help_impact = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "top_help_areas": json.dumps([{"help_area": "shooting"}]),
                "does_not_help": json.dumps([{"gap": "wing defense"}]),
            }
        ]
    )
    fit_breakdowns = pd.DataFrame(
        [{"player_id": 1, "player_name": "Test Wing", "component_cards": "[]"}]
    )
    best_by_need = pd.DataFrame(
        [
            {
                "need_id": "shooting_volume",
                "top_players": json.dumps([{"player_id": 1}]),
                "why_these_players_fit": "supported spacing",
            }
        ]
    )
    roster_simulation = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "position": "F",
                "primary_roster_slot": "low_usage_spacer",
                "starter_possible": False,
                "two_big_compatible": False,
                "contradiction_flags": json.dumps([]),
            }
        ]
    )
    compatibility = pd.DataFrame(
        [
            {
                "candidate_id": 1,
                "candidate_name": "Test Wing",
                "sixers_player_name": player,
                "evidence": json.dumps({"test": True}),
                "confidence": "medium",
            }
            for player in ("Joel Embiid", "Tyrese Maxey", "Paul George")
        ]
    )
    scenarios = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Test Wing",
                "scenario_type": "realistic_case",
            }
        ]
    )
    candidate_universe = pd.DataFrame(
        [
            {
                "player_id": 1,
                "candidate_status_freshness": "verified_current",
                "missing_data_flags": "none",
            }
        ]
    )
    return {
        "rankings": rankings,
        "claims": claims,
        "evidence": evidence,
        "profiles": profiles,
        "profile_index": profile_index,
        "salary_cards": salary_cards,
        "help_impact": help_impact,
        "fit_breakdowns": fit_breakdowns,
        "best_by_need": best_by_need,
        "roster_simulation": roster_simulation,
        "compatibility": compatibility,
        "scenarios": scenarios,
        "candidate_universe": candidate_universe,
    }


def gate_names(result) -> set[str]:
    """Return failing gate names from a validation result."""
    return {issue.gate for issue in result.errors}
