# Acquisition Feasibility

This layer separates contract/status reality from basketball fit.

## Path Counts

| Acquisition Path | Rows | Median Score | Manual Review |
| --- | ---: | ---: | ---: |
| expensive_trade | 17 | 19.4 | 0 |
| free_agent_market | 13 | 72.0 | 0 |
| medium_trade | 62 | 38.5 | 0 |
| minimum_signing | 64 | 88.0 | 0 |
| mle_or_exception_signing | 24 | 76.0 | 0 |
| rookie_scale_trade | 168 | 46.6 | 0 |
| small_trade | 21 | 53.0 | 0 |
| theoretical_only | 57 | 0.0 | 9 |
| unavailable_or_core | 13 | 5.0 | 0 |
| unknown_missing_data | 123 | 20.0 | 123 |

## Manual Review Examples

| Player | Type | Path | Freshness | Missing Flags |
| --- | --- | --- | --- | --- |
| Julius Randle | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| LaMelo Ball | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Jaime Jaquez Jr. | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Collin Gillespie | contract_blocked | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;draft year missing;recent_transaction_present;unknown_acquisition_path |
| Giannis Antetokounmpo | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Bobby Portis | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Kel'el Ware | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Jimmy Butler III | manual_watchlist | theoretical_only | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| GG Jackson | manual_watchlist | theoretical_only | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| Tyler Herro | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Isaiah Stewart | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Ronald Holland II | manual_watchlist | theoretical_only | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| Aaron Wiggins | manual_review_needed | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;recent_transaction_present;unknown_acquisition_path |
| Jordan Goodwin | contract_blocked | unknown_missing_data | conflict_between_sources |  AAV not in public source; option status not in public source;base salary not in public source;base_salary_missing;conflict_between_sources;contract_aav_missing;draft year missing;recent_transaction_present;unknown_acquisition_path |
| Egor Dëmin | manual_watchlist | theoretical_only | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| Tristan Vukcevic | missing_contract_status | unknown_missing_data | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing;unknown_acquisition_path |
| Walter Clayton Jr. | manual_watchlist | theoretical_only | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| Quenton Jackson | missing_contract_status | unknown_missing_data | verified_current |  draft year missing;base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing;unknown_acquisition_path |
| Caleb Love | manual_watchlist | theoretical_only | verified_current |  draft year missing;base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing |
| Javon Small | missing_contract_status | unknown_missing_data | verified_current | base_salary_missing;cap hit missing;cap_hit_missing;contract_aav_missing;unknown_acquisition_path |

## Limits

- This is not exact CBA math.
- Public contract data may lack base salary or AAV.
- True trade availability and team intent are not public.