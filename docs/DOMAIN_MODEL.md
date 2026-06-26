# MoreyMachine Domain Model

This document defines the domain objects used by the industry-grade rebuild.
The names map directly to schema modules under `src/moreymachine/schemas/`.

## Player

A canonical basketball entity.

Required fields:

- `player_id`
- `player_name`
- `normalized_name`
- `current_team`
- `position`
- `height`
- `weight`
- `age`
- `source`
- `pulled_at`
- `data_mode`
- `missing_data_flags`

## Team

A canonical NBA team entity.

Required fields:

- `team_id`
- `team_abbr`
- `team_name`
- `season`
- `source`

## TeamContext

Manual basketball context for one target team. This file can encode
assumptions, but not fake statistics.

Fields:

- `team_abbr`
- `team_name`
- `context_mode`
- `core_players`
- `locked_roles`
- `open_slots`
- `blocked_slots`
- `must_not_violate_rules`
- `manual_notes`

`PHI` has custom context. Other teams can use `GENERIC` context, but the app
must label that lower-confidence assumption set.

## Season

A normalized season key.

Examples:

- `2025-26`
- `2024-25`

## RosterWorld

The full current context for the target team.

Fields:

- `target_team`
- `season`
- `core_players`
- `locked_roles`
- `likely_starters`
- `high_rotation_players`
- `open_roster_slots`
- `blocked_roster_slots`
- `lineup_constraints`
- `strategic_needs`
- `must_not_violate_rules`
- `assumptions`
- `sources`

## TeamLevel

The current-state classification for the selected team.

Fields:

- `team_abbr`
- `team_level`
- `level_score`
- `contender_percentile`
- `closest_archetype`
- `closest_benchmark_teams`
- `main_strengths`
- `main_weaknesses`
- `why_this_level`
- `what_level_requires_next`
- `confidence`
- `evidence`
- `missing_data_flags`

This object is a strategic summary, not a claim that the model fully knows team
quality.

## BenchmarkPath

A comparison between the selected team and a contender benchmark.

Fields:

- `selected_team`
- `benchmark_name`
- `benchmark_type`
- `similarity_score`
- `gap_to_benchmark_score`
- `closest_archetype`
- `strengths_vs_benchmark`
- `weaknesses_vs_benchmark`
- `biggest_delta_stats`
- `biggest_delta_roles`
- `what_needs_to_change`
- `what_not_to_chase`
- `evidence`
- `confidence`
- `missing_data_flags`

## CorePlayer

A current Sixers player whose role meaningfully shapes candidate fit.

Fields:

- `player_id`
- `player_name`
- `core_type`
- `locked_role_status`
- `usage_burden`
- `lineup_constraints`
- `fit_implications`

Core examples:

- Joel Embiid
- Tyrese Maxey
- Paul George

## RosterSlot

A possible role a candidate can occupy on Philadelphia.

Allowed values include:

- `starting_center`
- `backup_center`
- `non_embiid_center_minutes`
- `matchup_big`
- `double_big_stretch_partner`
- `stretch_forward`
- `defensive_forward`
- `3_and_d_wing`
- `movement_shooter`
- `low_usage_spacer`
- `low_usage_connector`
- `point_of_attack_defender`
- `secondary_creator`
- `bench_creator`
- `rebounding_forward`
- `regular_season_depth`
- `developmental_upside`
- `theoretical_star_upgrade`
- `no_clear_role`
- `poor_fit_redundant_role`

## LineupContext

The lineup state where a candidate would actually play.

Fields:

- `lineup_context_id`
- `core_players_present`
- `candidate_slot`
- `usage_context`
- `spacing_context`
- `defensive_context`
- `playoff_viability`
- `evidence`

## ContenderBlueprint

A structural reference model for a type of successful team.

Fields:

- `blueprint_id`
- `blueprint_name`
- `cohort`
- `required_roles`
- `redundant_roles`
- `failure_modes`
- `phi_distance`
- `player_types_that_help`
- `evidence`

## TeamConstructionArchetype

A team-style label derived from roster structure.

Allowed examples:

- `star_center_anchor`
- `heliocentric_guard`
- `wing_depth_switchable`
- `balanced_two_way`
- `defense_first`
- `shooting_pressure`
- `depth_heavy`
- `dual_big`
- `creator_committee`

## TeamGap

A role-specific gap between PHI and a reference blueprint.

Fields:

- `gap_id`
- `gap_name`
- `gap_category`
- `source_blueprint`
- `sixers_current_value`
- `contender_reference_value`
- `severity`
- `confidence`
- `roster_slot_needed`
- `skill_requirements`
- `lineup_contexts`
- `why_it_matters`
- `playoff_failure_mode`
- `what_fixes_it`
- `what_does_not_fix_it`
- `evidence`
- `missing_data_flags`

## SkillProfile

An evidence-backed player skill model.

Fields:

- `player_id`
- `player_name`
- skill dimensions
- evidence stats
- confidence values
- `claim_allowed` booleans
- `missing_data_flags`

## CompatibilityPair

Candidate fit with one current Sixers player or group.

Fields:

- `candidate_id`
- `candidate_name`
- `sixers_player_id`
- `sixers_player_name`
- `compatibility_score`
- `compatibility_type`
- `positives`
- `negatives`
- `conflict_flags`
- `lineup_contexts`
- `evidence`
- `confidence`

## Candidate

A player under acquisition consideration.

Fields:

- `player_id`
- `player_name`
- `candidate_type`
- `candidate_status`
- `contract_state`
- `acquisition_path`
- `board_type`
- `source_summary`
- `missing_data_flags`

## CandidateStatus

Current status freshness and review state.

Allowed values:

- `verified_current`
- `stale_needs_review`
- `conflict_between_sources`
- `manual_verification_required`

## ContractState

The player's salary/contract context.

Fields:

- `contract_status`
- `cap_hit_millions`
- `base_salary_millions`
- `contract_aav_millions`
- `years_remaining`
- `option_status`
- `free_agent_year`
- `salary_source`
- `source_url`
- `pulled_at`
- `missing_data_flags`

## AcquisitionPath

How a player could plausibly be acquired.

Allowed values:

- `minimum_signing`
- `mle_or_exception_signing`
- `free_agent_market`
- `restricted_free_agent_offer`
- `small_trade`
- `medium_trade`
- `expensive_trade`
- `star_trade`
- `rookie_scale_trade`
- `theoretical_only`
- `unavailable_or_core`
- `unknown_missing_data`

## AcquisitionScenario

The acquisition-specific path and uncertainty.

Fields:

- `acquisition_path`
- `acquisition_difficulty`
- `salary_matching_complexity`
- `trade_cost_proxy`
- `apron_or_exception_uncertainty`
- `manual_review_required`
- `evidence`

## CandidateScenario

A basketball role scenario.

Allowed scenario types:

- `best_case`
- `realistic_case`
- `conservative_case`
- `playoff_case`
- `regular_season_only_case`
- `overpay_case`
- `missing_data_case`
- `bad_fit_case`

## Recommendation

The final model opinion for a candidate under scenario constraints.

Fields:

- `recommendation`
- `recommendation_confidence`
- `final_recommendation_score`
- `primary_scenario`
- `primary_roster_slot`
- `contradiction_flags`
- `manual_review_required`
- `source_summary`

## OpportunityCost

The strategic cost of using a resource on a move.

Fields:

- `player_id`
- `player_name`
- `move_type`
- `resource_bucket`
- `opportunity_cost_score`
- `better_alternatives`
- `cheaper_alternatives`
- `roles_blocked_by_this_move`
- `future_flexibility_cost`
- `gap_priority_mismatch`
- `why_this_cost_matters`
- `confidence`
- `evidence`

Opportunity cost prevents expensive or redundant moves from looking clean only
because the player is talented.

## MoveRecommendation

A GM action, not just a player row.

Fields:

- `move_id`
- `move_rank`
- `move_type`
- `player_name`
- `acquisition_path`
- `feasibility_tier`
- `salary_context`
- `roster_gap_helped`
- `team_level_impact`
- `benchmark_impact`
- `expected_role`
- `primary_scenario`
- `why_do_this`
- `why_not_do_this`
- `why_ranked_above_next`
- `what_could_go_wrong`
- `confidence`
- `manual_review_required`
- `evidence`
- `missing_data_flags`
- `final_move_score`

## ActionCard

The summary-first UI card used by the GM Executive Summary.

Fields:

- `action_category`
- `title`
- `player_name`
- `move_type`
- `score`
- `feasibility`
- `confidence`
- `primary_reason`
- `main_risk`
- `evidence`
- `profile_id`

## NarrativePacket

A JSON packet passed to Ollama or the deterministic fallback writer.

Fields:

- `packet_type`
- `team`
- `facts`
- `evidence`
- `missing_data_flags`
- `confidence`
- `source_artifacts`

The packet is the source of truth. The generated text is only a readable view of
the packet.

## ExplanationClaim

A single statement the app wants to show.

Fields:

- `claim`
- `claim_type`
- `allowed`
- `evidence_object_ids`
- `confidence`
- `missing_data_flags`

## EvidenceObject

The structured evidence backing a claim.

Fields:

- `evidence_id`
- `claim`
- `evidence_type`
- `supporting_columns`
- `supporting_values`
- `source`
- `confidence`
- `missing_data_flags`

## PlayerProfile

The central product artifact for each player.

Includes:

- identity
- score summary
- role
- fit with core
- salary/acquisition
- skill profile
- scenarios
- explanation
- evidence
- profile completeness

## ValidationFlag

A structured warning or failure.

Fields:

- `flag_id`
- `player_id`
- `severity`
- `category`
- `message`
- `blocking`
- `evidence`
