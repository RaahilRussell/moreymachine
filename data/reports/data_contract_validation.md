# Data Contract Validation

| Table | Present | Errors | Warnings |
| --- | --- | --- | --- |
| team_seasons | yes | - | missing provenance columns: ['data_mode'] |
| player_seasons | yes | - | missing provenance columns: ['data_mode'] |
| player_bio | yes | - | missing provenance columns: ['data_mode'] |
| player_tracking | yes | - | missing provenance columns: ['data_mode'] |
| contracts | yes | missing required columns: ['base_salary_millions', 'cap_hit_millions', 'contract_aav_millions'] | missing provenance columns: ['salary_source']; no season/effective_date column (('effective_date',)) |
| candidates | yes | - | - |
| candidate_universe | yes | missing required columns: ['acquisition_feasibility', 'feasibility_tier'] | missing provenance columns: ['data_mode'] |
| player_roles | yes | missing required columns: ['expected_role'] | missing provenance columns: ['data_mode'] |
| roster_gaps | yes | - | missing provenance columns: ['data_sources'] |
| candidate_rankings | yes | - | - |
| candidate_rankings_realistic | yes | - | - |
| team_fingerprints | yes | - | - |
| backtest_results | yes | - | missing JSON keys: ['metrics'] |
