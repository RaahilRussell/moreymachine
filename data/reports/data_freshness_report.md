# Data Freshness Report

_Refresh locally with:_ `python scripts/refresh_current_data.py --season latest`

| Table | Rows | Seasons | Source | Pulled at | Data mode | Missing |
|---|---|---|---|---|---|---|
| team_seasons | 330 | 2015-16..2025-26 | nba_api:leaguedashteamstats (NBA.com Stats) | 2026-06-24 | real_api | none |
| player_seasons | 5968 | 2015-16..2025-26 | nba_api:leaguedashplayerstats (NBA.com Stats) | 2026-06-24 | real_api | all-null columns: position, steal_pct, block_pct |
| player_bio | 582 | — | nba_api:playerindex (NBA.com Stats) | 2026-06-24 | real_api | 151 rows carry missing_data_flags |
| player_tracking | 582 | — | nba_api:leaguedashptstats (NBA.com Stats) | 2026-06-24 | real_api | none |
| contracts | 529 | — | https://www.basketball-reference.com/contracts/players.html | 2026-06-24 | real_scraped | none |
| lineup_on_off | — | — | Optional table not collected (lineup/on-off marked missing,  | — | missing | Optional table not collected (lineup/on-off marked missing, not faked). |
