# Target Board Validation

**Overall: PASSED** (0 failing gates)

| Gate | Result | Detail |
| --- | --- | --- |
| priority_cap | pass | 10 Priority targets (cap 10). |
| contract_value_saturation | pass | 0.0% with contract_value >= 95 (limit 10%). |
| portability_saturation | pass | 4.1% with portability >= 95 (limit 5%). |
| risk_diversity | pass | most common risk = 3.2% (limit 50%). |
| candidate_type_present | pass | 0 rows missing candidate_type. |
| recommendation_provenance | pass | 0 rows missing data_sources. |
| explanation_present | pass | every row carries explanations. |
| no_current_sixers | pass | none on board. |
| no_star_in_realistic | pass | 0 unrealistic/watchlist/missing rows on the realistic board. |
| no_unrealistic_priority | pass | 0 unrealistic/watchlist players marked Priority. |
| no_missing_contract_priority | pass | 0 missing-contract players marked Priority. |
| no_unknown_role_priority | pass | 0 Unknown-role players Priority. |
| no_severe_risk_priority | pass | 0 Severe/Unknown-risk Priority. |
| no_stale_priority | pass | 0 stale/manual-review players marked Priority. |
| salary_unambiguous | pass | base/cap/AAV + bucket all present. |
| watchlist_separation | pass | watchlist holds no acquisition recommendations. |
| csv_explanations | pass | CSV carries explanation columns. |
