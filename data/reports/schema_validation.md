# Schema Validation

| Artifact | Status | Rows | Errors | Warnings |
| --- | --- | ---: | ---: | ---: |
| player_seasons | PASS | 5968 | 0 | 1 |
| player_bio | PASS | 582 | 0 | 0 |
| team_seasons | PASS | 330 | 0 | 1 |
| contracts | PASS | 529 | 0 | 0 |
| manual_contracts | PASS | 0 | 0 | 0 |
| transactions | PASS | 110 | 0 | 1 |
| roster_world_phi | SKIP | 0 | 0 | 1 |
| contender_blueprints | SKIP | 0 | 0 | 1 |
| team_construction_archetypes | SKIP | 0 | 0 | 1 |
| phi_roster_gaps | PASS | 19 | 0 | 3 |
| sixers_gap_model | SKIP | 0 | 0 | 1 |
| player_roles | PASS | 582 | 0 | 2 |
| player_skill_profiles | SKIP | 0 | 0 | 1 |
| candidate_core_compatibility | SKIP | 0 | 0 | 1 |
| candidate_roster_simulation | SKIP | 0 | 0 | 1 |
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

- Path: `/Users/raahil/moreymachine/data/processed/player_seasons.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### player_bio

- Path: `/Users/raahil/moreymachine/data/processed/player_bio.parquet`
- Present: `True`
- Clean.

### team_seasons

- Path: `/Users/raahil/moreymachine/data/processed/team_seasons.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### contracts

- Path: `/Users/raahil/moreymachine/data/processed/contracts.parquet`
- Present: `True`
- Clean.

### manual_contracts

- Path: `/Users/raahil/moreymachine/data/manual/contracts.csv`
- Present: `True`
- Clean.

### transactions

- Path: `/Users/raahil/moreymachine/data/processed/transactions.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags

### roster_world_phi

- Path: `/Users/raahil/moreymachine/data/processed/roster_world_phi.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### contender_blueprints

- Path: `/Users/raahil/moreymachine/data/features/contender_blueprints.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### team_construction_archetypes

- Path: `/Users/raahil/moreymachine/data/features/team_construction_archetypes.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### phi_roster_gaps

- Path: `/Users/raahil/moreymachine/data/reports/phi_roster_gaps.parquet`
- Present: `True`
- Warnings:
  - missing data mode column: data_mode
  - missing missing-data column: missing_data_flags
  - no pulled_at/effective_date column present

### sixers_gap_model

- Path: `/Users/raahil/moreymachine/data/features/sixers_gap_model.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_roles

- Path: `/Users/raahil/moreymachine/data/reports/player_role_explanations.parquet`
- Present: `True`
- Warnings:
  - missing missing-data column: missing_data_flags
  - no pulled_at/effective_date column present

### player_skill_profiles

- Path: `/Users/raahil/moreymachine/data/features/player_skill_profiles.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_core_compatibility

- Path: `/Users/raahil/moreymachine/data/features/candidate_core_compatibility.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_roster_simulation

- Path: `/Users/raahil/moreymachine/data/features/candidate_roster_simulation.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### acquisition_feasibility

- Path: `/Users/raahil/moreymachine/data/features/acquisition_feasibility.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_scenarios

- Path: `/Users/raahil/moreymachine/data/features/candidate_scenarios.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### candidate_fit_rankings_all

- Path: `/Users/raahil/moreymachine/data/reports/candidate_fit_rankings_all.parquet`
- Present: `True`
- Warnings:
  - missing data mode column: data_mode

### candidate_fit_rankings_v2

- Path: `/Users/raahil/moreymachine/data/reports/candidate_fit_rankings_v2.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### explanation_claims

- Path: `/Users/raahil/moreymachine/data/reports/explanation_claims.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### evidence_objects

- Path: `/Users/raahil/moreymachine/data/reports/evidence_objects.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_profiles

- Path: `/Users/raahil/moreymachine/data/reports/player_profiles.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_profiles_index

- Path: `/Users/raahil/moreymachine/data/reports/player_profiles_index.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet

### player_salary_cards

- Path: `/Users/raahil/moreymachine/data/reports/player_salary_cards.parquet`
- Present: `False`
- Warnings:
  - artifact not generated yet
