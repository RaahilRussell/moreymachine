# Pipeline DAG

This file defines the target end-to-end pipeline. Scripts should be runnable
from the repository root with `PYTHONPATH=src`.

## Current Foundation Scripts

| Script | Inputs | Outputs | Depends on |
| --- | --- | --- | --- |
| `scripts/refresh_current_data.py --season latest` | NBA.com via `nba_api` | `data/processed/team_seasons.parquet`, `player_seasons.parquet`, `player_bio.parquet`, `player_tracking.parquet`, contracts where configured | none |
| `scripts/refresh_transactions.py` | Spotrac recent transaction feed | `data/processed/transactions.parquet` | none |
| `scripts/build_playoff_tiers.py` | `data/manual/playoff_tiers.csv`, team seasons | `data/processed/team_seasons_with_tiers.parquet` | refresh current data |
| `scripts/build_quality_tiers.py` | player seasons | quality tier columns/artifacts | refresh current data |
| `scripts/build_team_fingerprints.py` | team seasons with tiers | `data/features/team_fingerprints.parquet` | playoff tiers |
| `scripts/train_contender_model.py` | team fingerprints | model + metrics | team fingerprints |
| `scripts/train_outcome_tier_model.py` | team seasons with tiers | model + metrics | playoff tiers |
| `scripts/build_roster_archetypes.py` | team seasons/fingerprints | `data/features/team_roster_archetypes.parquet` | team fingerprints |
| `scripts/build_player_archetypes.py` | player seasons | `data/features/player_archetypes.parquet` | refresh current data |
| `scripts/build_player_roles.py` | player seasons, bio, tracking | `data/features/player_roles.parquet` | refresh current data |
| `scripts/analyze_roster_gaps.py --team PHI` | team fingerprints, current data | `data/reports/phi_roster_gaps.parquet`, `.md` | team fingerprints |
| `scripts/build_candidate_universe.py --team PHI` | player seasons, contracts, transactions, manual candidates | `data/features/candidate_universe.parquet`, `data/reports/current_roster_reference.parquet` | refresh current data, refresh transactions |
| `scripts/rank_candidates.py --team PHI` | candidate universe, roles, gaps, contracts | current v1 boards | candidate universe, roles, gaps |
| `scripts/run_backtest.py` | historical seasons, candidate universe logic | backtest reports | current foundation |

## New Industry Rebuild Scripts

| Script | Inputs | Outputs | Depends on |
| --- | --- | --- | --- |
| `scripts/validate_all_schemas.py` | generated artifacts | schema validation report | schemas |
| `scripts/audit_data_lineage.py` | generated artifacts + metadata | lineage audit report | entity resolution, lineage |
| `scripts/build_roster_world.py` | current roster reference, player roles, contracts, `data/manual/team_context/phi.yml` | `data/processed/roster_world_phi.parquet`, `data/reports/roster_world_phi.md` | candidate universe, player roles |
| `scripts/build_contender_blueprints.py` | team seasons, team fingerprints, playoff tiers | `data/features/contender_blueprints.parquet`, `team_construction_archetypes.parquet`, report | team fingerprints |
| `scripts/build_gap_model.py` | roster world, contender blueprints, existing gap data | `data/features/sixers_gap_model.parquet`, report | roster world, blueprints |
| `scripts/build_player_skill_profiles.py` | player seasons, player roles, tracking, bio | `data/features/player_skill_profiles.parquet`, examples report | player roles |
| `scripts/build_compatibility_matrix.py` | roster world, skill profiles, candidate universe | `data/features/candidate_core_compatibility.parquet`, examples report | roster world, skill profiles |
| `scripts/simulate_roster_slots.py` | roster world, gap model, skill profiles, compatibility | `data/features/candidate_roster_simulation.parquet`, examples report | compatibility, gap model |
| `scripts/build_acquisition_feasibility.py` | candidate universe, contracts, transactions | `data/features/acquisition_feasibility.parquet`, report | candidate universe |
| `scripts/build_candidate_scenarios.py` | roster simulation, acquisition feasibility, gap model, compatibility | `data/features/candidate_scenarios.parquet`, report | roster simulation, acquisition feasibility |
| `scripts/rank_candidates_v2.py --team PHI` | all v2 feature artifacts | v2 split candidate boards | scenarios |
| `scripts/build_player_categorization.py` | v2 rankings, skill profiles, acquisition, roster simulation | `data/features/player_categorizations.parquet` | v2 rankings |
| `scripts/build_help_impact.py` | gap model, skill profiles, roster simulation | `data/features/player_help_impact.parquet` | gap model, skill profiles |
| `scripts/build_fit_breakdowns.py` | v2 rankings and component artifacts | fit breakdown parquet/json | v2 rankings |
| `scripts/build_salary_cards.py` | contracts, acquisition feasibility, candidate universe | `data/reports/player_salary_cards.parquet` | acquisition feasibility |
| `scripts/build_explanations_v2.py` | v2 rankings, skill profiles, acquisition, scenarios | explanation claims, evidence objects, player explanations | v2 rankings |
| `scripts/build_player_profiles.py` | v2 rankings, explanations, profile support artifacts | `data/reports/player_profiles.parquet`, `.json`, index | explanations plus all profile support artifacts |
| `scripts/build_best_by_need.py` | help impact, v2 rankings, gap model | `data/reports/best_by_need.parquet` | help impact |
| `scripts/export_scouting_reports.py` | player profiles | `data/reports/scouting_reports/{slug}.md` | player profiles |
| `scripts/validate_reasoning_v2.py` | v2 boards, profiles, explanations, validation flags | reasoning validation report | player profiles |
| `scripts/validate_player_profiles.py` | player profiles | profile validation report | player profiles |

## Team-Scoped GM Product Scripts

| Script | Inputs | Outputs | Depends on |
| --- | --- | --- | --- |
| `scripts/run_team_pipeline.py --team PHI` | cached global artifacts, manual team context | `data/team_outputs/{TEAM}/...` | existing pipeline artifacts |
| `scripts/build_team_level.py --team PHI` | team seasons/fingerprints, contender blueprints, team context | `data/team_outputs/{TEAM}/reports/team_level.parquet`, `.json`, `.md` | roster world, contender blueprints |
| `scripts/build_team_comparison.py --team PHI` | team level, contender blueprints, team seasons | `data/team_outputs/{TEAM}/reports/team_comparison.parquet`, `.json` | team level, blueprints |
| `scripts/build_opportunity_cost.py --team PHI` | v2 rankings, roster simulation, acquisition feasibility, gap model | `data/team_outputs/{TEAM}/features/opportunity_cost.parquet` | v2 rankings, acquisition |
| `scripts/build_move_recommendations.py --team PHI` | v2 rankings, opportunity cost, gap model, team comparison | `data/team_outputs/{TEAM}/reports/move_recommendations.parquet` | opportunity cost |
| `scripts/build_action_cards.py --team PHI` | move recommendations, player profiles | `data/team_outputs/{TEAM}/reports/action_cards.parquet`, `.json` | move recommendations, profiles |
| `scripts/build_narratives.py --team PHI` | action cards, team level, comparison, profiles, best by need | `data/team_outputs/{TEAM}/narratives/*.json` | action cards, profiles |
| `scripts/validate_product_v2.py` | team-scoped outputs and app code | product validation report | team pipeline |

Team-scoped outputs keep the app from assuming PHI-only paths forever. PHI uses
custom context. Other teams may use generic context, but the app and validation
must show that lower-confidence state.

## Target Full Pipeline

```bash
export PYTHONPATH=src

python scripts/refresh_current_data.py --season latest
python scripts/refresh_transactions.py
python scripts/build_playoff_tiers.py
python scripts/build_quality_tiers.py
python scripts/build_team_fingerprints.py
python scripts/train_contender_model.py
python scripts/train_outcome_tier_model.py
python scripts/build_roster_archetypes.py
python scripts/build_player_archetypes.py
python scripts/build_player_roles.py
python scripts/analyze_roster_gaps.py --team PHI
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI

python scripts/validate_all_schemas.py
python scripts/audit_data_lineage.py
python scripts/build_roster_world.py
python scripts/build_contender_blueprints.py
python scripts/build_gap_model.py
python scripts/build_player_skill_profiles.py
python scripts/build_compatibility_matrix.py
python scripts/simulate_roster_slots.py
python scripts/build_acquisition_feasibility.py
python scripts/build_candidate_scenarios.py
python scripts/rank_candidates_v2.py --team PHI
python scripts/build_player_categorization.py
python scripts/build_help_impact.py
python scripts/build_fit_breakdowns.py
python scripts/build_salary_cards.py
python scripts/build_explanations_v2.py
python scripts/build_player_profiles.py
python scripts/build_best_by_need.py
python scripts/export_scouting_reports.py

python scripts/run_team_pipeline.py --team PHI --skip-refresh
python scripts/build_narratives.py --team PHI

python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
python scripts/validate_reasoning_v2.py
python scripts/validate_player_profiles.py
python scripts/validate_product_v2.py
pytest
python -c "import moreymachine; print('import ok')"
```

## Artifact Dependency Rules

- V2 recommendations cannot run before roster simulation and scenario artifacts
  exist.
- Explanations cannot run before evidence objects exist.
- Player profiles cannot run before salary cards, help impact, fit breakdowns,
  scenarios, and v2 recommendations exist.
- Streamlit v2 pages read cached artifacts only.
- Validation must run after artifact generation and before deployment.

## Team Output Directory Contract

Each team output directory should contain:

```text
data/team_outputs/{TEAM}/features/
data/team_outputs/{TEAM}/reports/
data/team_outputs/{TEAM}/narratives/
data/team_outputs/{TEAM}/scouting_reports/
data/team_outputs/{TEAM}/metadata/
```

Every artifact should include `data_mode`, `source_summary`, `created_at` or
`pulled_at`, `run_id`, `missing_data_flags`, `confidence`, and `evidence` where
the file type supports tabular fields. Every artifact should also have a
same-file `.metadata.json` sidecar.
