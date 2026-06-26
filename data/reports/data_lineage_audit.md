# Data Lineage Audit

- Run ID: `20260626T081108Z-a5a32d2d`
- Identity source rows: `6877`
- Resolved canonical players: `1554`
- Duplicate normalized-name keys: `0`
- Unresolved identity rows: `73`
- Artifacts discovered: `112`
- Metadata sidecars written: `112`

## Duplicate Player Keys

No duplicate normalized-name keys with multiple player IDs.

## Artifact Metadata Sidecars

| Artifact | Sidecar |
| --- | --- |
| `data/features/candidate_universe.parquet` | `data/features/candidate_universe.parquet.metadata.json` |
| `data/features/player_archetypes.parquet` | `data/features/player_archetypes.parquet.metadata.json` |
| `data/features/player_roles.parquet` | `data/features/player_roles.parquet.metadata.json` |
| `data/features/team_fingerprints.parquet` | `data/features/team_fingerprints.parquet.metadata.json` |
| `data/features/team_roster_archetypes.parquet` | `data/features/team_roster_archetypes.parquet.metadata.json` |
| `data/manual/candidates.csv` | `data/manual/candidates.csv.metadata.json` |
| `data/manual/contracts.csv` | `data/manual/contracts.csv.metadata.json` |
| `data/manual/playoff_tiers.csv` | `data/manual/playoff_tiers.csv.metadata.json` |
| `data/processed/contracts.parquet` | `data/processed/contracts.parquet.metadata.json` |
| `data/processed/contracts_raw.parquet` | `data/processed/contracts_raw.parquet.metadata.json` |
| `data/processed/player_bio.parquet` | `data/processed/player_bio.parquet.metadata.json` |
| `data/processed/player_seasons.parquet` | `data/processed/player_seasons.parquet.metadata.json` |
| `data/processed/player_tracking.parquet` | `data/processed/player_tracking.parquet.metadata.json` |
| `data/processed/team_seasons.parquet` | `data/processed/team_seasons.parquet.metadata.json` |
| `data/processed/team_seasons_with_tiers.parquet` | `data/processed/team_seasons_with_tiers.parquet.metadata.json` |
| `data/processed/transactions.parquet` | `data/processed/transactions.parquet.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2015_16_35de25b9e0bfe31d.json` | `data/raw/nba_api/leaguedashplayerstats/2015_16_35de25b9e0bfe31d.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2015_16_93fb2d6f57f13a28.json` | `data/raw/nba_api/leaguedashplayerstats/2015_16_93fb2d6f57f13a28.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2016_17_5b6e758331461fcb.json` | `data/raw/nba_api/leaguedashplayerstats/2016_17_5b6e758331461fcb.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2016_17_e3703735ad5a0b3f.json` | `data/raw/nba_api/leaguedashplayerstats/2016_17_e3703735ad5a0b3f.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2017_18_600c77853cbc57ed.json` | `data/raw/nba_api/leaguedashplayerstats/2017_18_600c77853cbc57ed.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2017_18_ee350a4b05870e66.json` | `data/raw/nba_api/leaguedashplayerstats/2017_18_ee350a4b05870e66.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2018_19_a31addb573dd8e4a.json` | `data/raw/nba_api/leaguedashplayerstats/2018_19_a31addb573dd8e4a.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2018_19_ffaf9186bb926f7c.json` | `data/raw/nba_api/leaguedashplayerstats/2018_19_ffaf9186bb926f7c.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2019_20_57537b6247caf750.json` | `data/raw/nba_api/leaguedashplayerstats/2019_20_57537b6247caf750.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2019_20_796c31307f4f31e4.json` | `data/raw/nba_api/leaguedashplayerstats/2019_20_796c31307f4f31e4.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2020_21_20f1c973a1ebb5a6.json` | `data/raw/nba_api/leaguedashplayerstats/2020_21_20f1c973a1ebb5a6.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2020_21_9760bfd432185de5.json` | `data/raw/nba_api/leaguedashplayerstats/2020_21_9760bfd432185de5.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2021_22_3b0f6cb8023bdba7.json` | `data/raw/nba_api/leaguedashplayerstats/2021_22_3b0f6cb8023bdba7.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2021_22_b899da5288b01ad8.json` | `data/raw/nba_api/leaguedashplayerstats/2021_22_b899da5288b01ad8.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2022_23_39ddb9aafe49236d.json` | `data/raw/nba_api/leaguedashplayerstats/2022_23_39ddb9aafe49236d.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2022_23_d7930fe83502c0aa.json` | `data/raw/nba_api/leaguedashplayerstats/2022_23_d7930fe83502c0aa.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2023_24_12ee384737cc7ac1.json` | `data/raw/nba_api/leaguedashplayerstats/2023_24_12ee384737cc7ac1.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2023_24_9e6a0a9421e35dbc.json` | `data/raw/nba_api/leaguedashplayerstats/2023_24_9e6a0a9421e35dbc.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2024_25_12bb106f515ad1e6.json` | `data/raw/nba_api/leaguedashplayerstats/2024_25_12bb106f515ad1e6.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2024_25_e64f04af120b4cfb.json` | `data/raw/nba_api/leaguedashplayerstats/2024_25_e64f04af120b4cfb.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2025_26_6e4319c1027abf12.json` | `data/raw/nba_api/leaguedashplayerstats/2025_26_6e4319c1027abf12.json.metadata.json` |
| `data/raw/nba_api/leaguedashplayerstats/2025_26_9f20c6bcd0479972.json` | `data/raw/nba_api/leaguedashplayerstats/2025_26_9f20c6bcd0479972.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_155db194cb0750a2.json` | `data/raw/nba_api/leaguedashptstats/2025_26_155db194cb0750a2.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_565f545a87bee653.json` | `data/raw/nba_api/leaguedashptstats/2025_26_565f545a87bee653.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_5736bd427941d18e.json` | `data/raw/nba_api/leaguedashptstats/2025_26_5736bd427941d18e.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_626f3d4586506f3f.json` | `data/raw/nba_api/leaguedashptstats/2025_26_626f3d4586506f3f.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_88fe5c31bedcd91a.json` | `data/raw/nba_api/leaguedashptstats/2025_26_88fe5c31bedcd91a.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_9102e9427e0589ee.json` | `data/raw/nba_api/leaguedashptstats/2025_26_9102e9427e0589ee.json.metadata.json` |
| `data/raw/nba_api/leaguedashptstats/2025_26_f979a20c32c43cbb.json` | `data/raw/nba_api/leaguedashptstats/2025_26_f979a20c32c43cbb.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2015_16_35de25b9e0bfe31d.json` | `data/raw/nba_api/leaguedashteamstats/2015_16_35de25b9e0bfe31d.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2015_16_86bc91cc84c1a32f.json` | `data/raw/nba_api/leaguedashteamstats/2015_16_86bc91cc84c1a32f.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2015_16_93fb2d6f57f13a28.json` | `data/raw/nba_api/leaguedashteamstats/2015_16_93fb2d6f57f13a28.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2016_17_0b11b057f6cdf625.json` | `data/raw/nba_api/leaguedashteamstats/2016_17_0b11b057f6cdf625.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2016_17_5b6e758331461fcb.json` | `data/raw/nba_api/leaguedashteamstats/2016_17_5b6e758331461fcb.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2016_17_e3703735ad5a0b3f.json` | `data/raw/nba_api/leaguedashteamstats/2016_17_e3703735ad5a0b3f.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2017_18_210acd200f1952c1.json` | `data/raw/nba_api/leaguedashteamstats/2017_18_210acd200f1952c1.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2017_18_600c77853cbc57ed.json` | `data/raw/nba_api/leaguedashteamstats/2017_18_600c77853cbc57ed.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2017_18_ee350a4b05870e66.json` | `data/raw/nba_api/leaguedashteamstats/2017_18_ee350a4b05870e66.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2018_19_592c288ceeb6c5b8.json` | `data/raw/nba_api/leaguedashteamstats/2018_19_592c288ceeb6c5b8.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2018_19_a31addb573dd8e4a.json` | `data/raw/nba_api/leaguedashteamstats/2018_19_a31addb573dd8e4a.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2018_19_ffaf9186bb926f7c.json` | `data/raw/nba_api/leaguedashteamstats/2018_19_ffaf9186bb926f7c.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2019_20_57537b6247caf750.json` | `data/raw/nba_api/leaguedashteamstats/2019_20_57537b6247caf750.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2019_20_796c31307f4f31e4.json` | `data/raw/nba_api/leaguedashteamstats/2019_20_796c31307f4f31e4.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2019_20_e5f96b19ca1a4402.json` | `data/raw/nba_api/leaguedashteamstats/2019_20_e5f96b19ca1a4402.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2020_21_20f1c973a1ebb5a6.json` | `data/raw/nba_api/leaguedashteamstats/2020_21_20f1c973a1ebb5a6.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2020_21_9760bfd432185de5.json` | `data/raw/nba_api/leaguedashteamstats/2020_21_9760bfd432185de5.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2020_21_e20811b469c516aa.json` | `data/raw/nba_api/leaguedashteamstats/2020_21_e20811b469c516aa.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2021_22_3b0f6cb8023bdba7.json` | `data/raw/nba_api/leaguedashteamstats/2021_22_3b0f6cb8023bdba7.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2021_22_b899da5288b01ad8.json` | `data/raw/nba_api/leaguedashteamstats/2021_22_b899da5288b01ad8.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2021_22_f757ce09e3c53920.json` | `data/raw/nba_api/leaguedashteamstats/2021_22_f757ce09e3c53920.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2022_23_39ddb9aafe49236d.json` | `data/raw/nba_api/leaguedashteamstats/2022_23_39ddb9aafe49236d.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2022_23_bb6461f933e56744.json` | `data/raw/nba_api/leaguedashteamstats/2022_23_bb6461f933e56744.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2022_23_d7930fe83502c0aa.json` | `data/raw/nba_api/leaguedashteamstats/2022_23_d7930fe83502c0aa.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2023_24_12ee384737cc7ac1.json` | `data/raw/nba_api/leaguedashteamstats/2023_24_12ee384737cc7ac1.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2023_24_9e6a0a9421e35dbc.json` | `data/raw/nba_api/leaguedashteamstats/2023_24_9e6a0a9421e35dbc.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2023_24_db69739f1eb5780f.json` | `data/raw/nba_api/leaguedashteamstats/2023_24_db69739f1eb5780f.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2024_25_12bb106f515ad1e6.json` | `data/raw/nba_api/leaguedashteamstats/2024_25_12bb106f515ad1e6.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2024_25_713df6a5781029e4.json` | `data/raw/nba_api/leaguedashteamstats/2024_25_713df6a5781029e4.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2024_25_e64f04af120b4cfb.json` | `data/raw/nba_api/leaguedashteamstats/2024_25_e64f04af120b4cfb.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2025_26_3d866f455ac1bc24.json` | `data/raw/nba_api/leaguedashteamstats/2025_26_3d866f455ac1bc24.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2025_26_6e4319c1027abf12.json` | `data/raw/nba_api/leaguedashteamstats/2025_26_6e4319c1027abf12.json.metadata.json` |
| `data/raw/nba_api/leaguedashteamstats/2025_26_9f20c6bcd0479972.json` | `data/raw/nba_api/leaguedashteamstats/2025_26_9f20c6bcd0479972.json.metadata.json` |
| `data/raw/nba_api/playerindex/2025_26_7bd2990ccde6e7eb.json` | `data/raw/nba_api/playerindex/2025_26_7bd2990ccde6e7eb.json.metadata.json` |
| `data/reports/REBUILD_HANDOFF.md` | `data/reports/REBUILD_HANDOFF.md.metadata.json` |
| `data/reports/_phi_roster_gaps_stat.md` | `data/reports/_phi_roster_gaps_stat.md.metadata.json` |
| `data/reports/backtest_rankings.parquet` | `data/reports/backtest_rankings.parquet.metadata.json` |
| `data/reports/backtest_results.json` | `data/reports/backtest_results.json.metadata.json` |
| `data/reports/backtest_summary.md` | `data/reports/backtest_summary.md.metadata.json` |
| `data/reports/candidate_fit_rankings.csv` | `data/reports/candidate_fit_rankings.csv.metadata.json` |
| `data/reports/candidate_fit_rankings.parquet` | `data/reports/candidate_fit_rankings.parquet.metadata.json` |
| `data/reports/candidate_fit_rankings_all.parquet` | `data/reports/candidate_fit_rankings_all.parquet.metadata.json` |
| `data/reports/candidate_fit_rankings_free_agents.parquet` | `data/reports/candidate_fit_rankings_free_agents.parquet.metadata.json` |
| `data/reports/candidate_fit_rankings_realistic.parquet` | `data/reports/candidate_fit_rankings_realistic.parquet.metadata.json` |
| `data/reports/candidate_fit_rankings_trade_targets.parquet` | `data/reports/candidate_fit_rankings_trade_targets.parquet.metadata.json` |
| `data/reports/candidate_fit_rankings_unrealistic_watchlist.parquet` | `data/reports/candidate_fit_rankings_unrealistic_watchlist.parquet.metadata.json` |
| `data/reports/candidate_universe.parquet` | `data/reports/candidate_universe.parquet.metadata.json` |
| `data/reports/candidate_universe_summary.md` | `data/reports/candidate_universe_summary.md.metadata.json` |
| `data/reports/contender_model_metrics.json` | `data/reports/contender_model_metrics.json.metadata.json` |
| `data/reports/contender_model_predictions.parquet` | `data/reports/contender_model_predictions.parquet.metadata.json` |
| `data/reports/current_roster_reference.parquet` | `data/reports/current_roster_reference.parquet.metadata.json` |
| `data/reports/data_contract_validation.md` | `data/reports/data_contract_validation.md.metadata.json` |
| `data/reports/data_freshness_report.md` | `data/reports/data_freshness_report.md.metadata.json` |
| `data/reports/data_lineage_audit.md` | `data/reports/data_lineage_audit.md.metadata.json` |
| `data/reports/industry_rebuild_audit.md` | `data/reports/industry_rebuild_audit.md.metadata.json` |
| `data/reports/max_rebuild_audit.md` | `data/reports/max_rebuild_audit.md.metadata.json` |
| `data/reports/outcome_tier_metrics.json` | `data/reports/outcome_tier_metrics.json.metadata.json` |
| `data/reports/outcome_tier_predictions.parquet` | `data/reports/outcome_tier_predictions.parquet.metadata.json` |
| `data/reports/phi_roster_gaps.md` | `data/reports/phi_roster_gaps.md.metadata.json` |
| `data/reports/phi_roster_gaps.parquet` | `data/reports/phi_roster_gaps.parquet.metadata.json` |
| `data/reports/player_archetype_summary.csv` | `data/reports/player_archetype_summary.csv.metadata.json` |
| `data/reports/player_role_explanations.parquet` | `data/reports/player_role_explanations.parquet.metadata.json` |
| `data/reports/real_data_audit.md` | `data/reports/real_data_audit.md.metadata.json` |
| `data/reports/roster_archetype_summary.csv` | `data/reports/roster_archetype_summary.csv.metadata.json` |
| `data/reports/schema_validation.md` | `data/reports/schema_validation.md.metadata.json` |
| `data/reports/target_board_audit.md` | `data/reports/target_board_audit.md.metadata.json` |
| `data/reports/target_board_validation.md` | `data/reports/target_board_validation.md.metadata.json` |

## Current Limitations

- This audit can infer rows, columns, seasons, and data modes.
- Script-specific upstream dependencies are generic until each builder writes its own metadata through `moreymachine.data.lineage`.
- Entity resolution does not invent IDs for unresolved manual/status rows.