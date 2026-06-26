# Schema Validation

| Artifact | Status | Rows | Errors | Warnings |
| --- | --- | ---: | ---: | ---: |
| player_seasons | PASS | 5968 | 0 | 1 |
| player_bio | PASS | 582 | 0 | 0 |
| team_seasons | PASS | 330 | 0 | 1 |
| contracts | PASS | 529 | 0 | 0 |
| manual_contracts | PASS | 0 | 0 | 0 |
| transactions | PASS | 110 | 0 | 1 |
| roster_world_phi | PASS | 20 | 0 | 0 |
| contender_blueprints | PASS | 14 | 0 | 0 |
| team_construction_archetypes | PASS | 330 | 0 | 0 |
| phi_roster_gaps | PASS | 19 | 0 | 3 |
| sixers_gap_model | PASS | 20 | 0 | 0 |
| player_roles | PASS | 582 | 0 | 2 |
| player_skill_profiles | PASS | 582 | 0 | 0 |
| candidate_core_compatibility | PASS | 11240 | 0 | 0 |
| candidate_roster_simulation | PASS | 562 | 0 | 0 |
| acquisition_feasibility | SKIP | 0 | 0 | 1 |
| candidate_scenarios | SKIP | 0 | 0 | 1 |
| candidate_fit_rankings_all | PASS | 562 | 0 | 1 |
| candidate_fit_rankings_v2 | SKIP | 0 | 0 | 1 |
| explanation_claims | SKIP | 0 | 0 | 1 |
| evidence_objects | SKIP | 0 | 0 | 1 |
| player_profiles | SKIP | 0 | 0 | 1 |
| player_profiles_index | SKIP | 0 | 0 | 1 |
| player_salary_cards | SKIP | 0 | 0 | 1 |

## Details

### player_seasons

- Path: `data/processed/player_seasons.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### player_bio

- Path: `data/processed/player_bio.parquet`
- Present: `True`
- Clean.

### team_seasons

- Path: `data/processed/team_seasons.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### contracts

- Path: `data/processed/contracts.parquet`
- Present: `True`
- Clean.

### manual_contracts

- Path: `data/manual/contracts.csv`
- Present: `True`
- Clean.

### transactions

- Path: `data/processed/transactions.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### roster_world_phi

- Path: `data/processed/roster_world_phi.parquet`
- Present: `True`
- Clean.

### contender_blueprints

- Path: `data/features/contender_blueprints.parquet`
- Present: `True`
- Clean.

### team_construction_archetypes

- Path: `data/features/team_construction_archetypes.parquet`
- Present: `True`
- Clean.

### phi_roster_gaps

- Path: `data/reports/phi_roster_gaps.parquet`
- Present: `True`
- Warnings:
  - missing data mode column: data_mode
  - missing missing-data column: missing_data_flags
  - no pulled_at/effective_date column present

### sixers_gap_model

- Path: `data/features/sixers_gap_model.parquet`
- Present: `True`
- Clean.

### player_roles

- Path: `data/reports/player_role_explanations.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags
  - no pulled_at/effective_date column present

### player_skill_profiles

- Path: `data/features/player_skill_profiles.parquet`
- Present: `True`
- Clean.

### candidate_core_compatibility

- Path: `data/features/candidate_core_compatibility.parquet`
- Present: `True`
- Clean.

### candidate_roster_simulation

- Path: `data/features/candidate_roster_simulation.parquet`
- Present: `True`
- Clean.

### acquisition_feasibility

- Path: `data/features/acquisition_feasibility.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_scenarios

- Path: `data/features/candidate_scenarios.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_fit_rankings_all

- Path: `data/reports/candidate_fit_rankings_all.parquet`
- Present: `True`
- Warnings:
  - missing data mode column: data_mode

### candidate_fit_rankings_v2

- Path: `data/reports/candidate_fit_rankings_v2.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### explanation_claims

- Path: `data/reports/explanation_claims.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### evidence_objects

- Path: `data/reports/evidence_objects.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_profiles

- Path: `data/reports/player_profiles.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_profiles_index

- Path: `data/reports/player_profiles_index.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_salary_cards

- Path: `data/reports/player_salary_cards.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet
