# MoreyMachine

MoreyMachine is an unofficial NBA front-office analytics engine for studying
contender roster construction and player fit.

This project is not affiliated with Daryl Morey, the Philadelphia 76ers, or the
NBA.

## Real data only

MoreyMachine runs in `REAL_DATA_MODE` by default. Every ranking is built from
real sources with displayed provenance (`source`, `pulled_at`, season, row
count) and an explanation. The app never silently falls back to demo data: a
missing real file produces a loud "missing data" message with the exact command
to build it. See `data/reports/real_data_audit.md` for the audit that motivated
this, and the in-app **Data Sources** page for live provenance.

Real sources: NBA.com advanced stats via `nba_api`; hand-verified playoff
results (2015-16 to 2024-25); and real Basketball-Reference contract salaries.

## Setup

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

The editable install makes `moreymachine` imports work from the repository root
while keeping reusable code under `src/moreymachine`.

Optional local settings can be placed in `.env`:

```bash
REAL_DATA_MODE=true
MOREYMACHINE_ENV=development
MOREYMACHINE_LOG_LEVEL=INFO
MOREYMACHINE_DATA_DIR=data
MOREYMACHINE_NBA_LATEST_SEASON=2025-26
```

## Project Checks

Verify the folder structure and package imports:

```bash
python scripts/check_project.py
```

Run tests:

```bash
python -m pytest
```

Fetch NBA team and player season stats into `data/processed`:

```bash
python scripts/fetch_nba_data.py --latest-season 2025-26
```

Raw NBA API responses are cached under `data/raw/nba_api`, so repeated runs reuse
the cache instead of calling the same endpoints again.

Refresh all real current-season data (team/player stats, player bio, tracking,
and Basketball-Reference contracts) in one command:

```bash
python scripts/refresh_current_data.py --season latest
```

This writes `player_bio.parquet`, `player_tracking.parquet`, and
`contracts.parquet` alongside the season stats, and a freshness report to
`data/reports/data_freshness_report.md`. Cached real responses are reused; demo
data is never substituted.

Real playoff outcomes ship in `data/manual/playoff_tiers.csv` (one row per
team-season, 2015-16 to 2024-25), generated from the auditable brackets in
`moreymachine/data/playoff_results.py`:

```text
season,team_abbr,playoff_tier,playoff_result,source_note
```

The current, not-yet-resolved season is intentionally left unlabeled rather than
fabricated. Playoff tiers:

```text
0 = missed playoffs
1 = lost first round
2 = lost second round
3 = lost conference finals
4 = lost finals
5 = champion
```

Join manual tiers onto team seasons:

```bash
python scripts/build_playoff_tiers.py
```

Build regular-season quality tiers into `team_seasons_with_tiers.parquet`:

```bash
python scripts/build_quality_tiers.py
```

Quality tiers are assigned within each season using rank/percentile logic from
the best available regular-season strength signal: net rating, rating margin,
point differential per game, win percentage, or wins.

```text
0 = bottom 10 team
1 = below average
2 = average / play-in level
3 = playoff-level
4 = top-10 net rating
5 = top-5 net rating / elite
```

Build team-season fingerprint features:

```bash
python scripts/build_team_fingerprints.py
```

Fingerprints are saved to `data/features/team_fingerprints.parquet` and include
ratings, pace, shooting, turnover, rebounding, free-throw, and three-point
profile columns, plus estimated shooting pressure, possession control, two-way
balance, playoff labels, and quality labels.

Train the contender model:

```bash
python scripts/train_contender_model.py
```

The trainer predicts `deep_playoff` from `team_fingerprints.parquet` using
chronological validation across logistic regression, random forest, and gradient
boosting candidates. It writes the selected model to `data/models`, validation
metrics to `data/reports/contender_model_metrics.json`, and validation
predictions to `data/reports/contender_model_predictions.parquet`.

Train the playoff outcome tier model:

```bash
python scripts/train_outcome_tier_model.py
```

The outcome trainer predicts `playoff_tier` with random forest and gradient
boosting candidates. It writes tier probabilities, expected playoff tier, and
predicted tier to `data/reports/outcome_tier_predictions.parquet`, and writes
confusion matrices, mean absolute tier error, and top feature importances to
`data/reports/outcome_tier_metrics.json`.

Build roster construction archetype clusters:

```bash
python scripts/build_roster_archetypes.py --k 5 --pca-components 3
```

The archetype builder clusters team fingerprints with median imputation,
`StandardScaler`, PCA, and KMeans. It writes assignments to
`data/features/team_roster_archetypes.parquet` and a cluster summary with
suggested archetype names to `data/reports/roster_archetype_summary.csv`.

Analyze Sixers roster gaps:

```bash
python scripts/analyze_roster_gaps.py --target-team PHI
```

The gap engine compares the target team-season, defaulting to the latest PHI
season in `team_fingerprints.parquet`, against conference-finals-or-better
teams, successful teams from the same roster archetype, and top-5 net rating
teams. It writes `data/reports/phi_roster_gaps.parquet` and
`data/reports/phi_roster_gaps.md` with target values, elite averages,
percentiles, gap sizes, severity scores, and explanations for shooting
pressure, role-player shooting, defense, rebounding, turnover control,
pace/transition, bench or rotation depth when available, usage concentration
when available, and a playoff portability proxy.

Build player role archetype clusters:

```bash
python scripts/build_player_archetypes.py --min-minutes 500 --k 8 --pca-components 3
```

The player archetype builder filters to rotation players by minutes, derives
role features from player season stats where possible, encodes position buckets
when available, then clusters with median imputation, `StandardScaler`, PCA, and
KMeans. It writes assignments to `data/features/player_archetypes.parquet` and a
summary to `data/reports/player_archetype_summary.csv`.

Build the real candidate watchlist (players + salaries):

```bash
python scripts/fetch_candidates.py --team PHI
```

This pulls the candidate pool from real `nba_api` players and matches real
current salaries from Basketball-Reference's contracts page into
`data/manual/candidates.csv`. Salaries that cannot be matched online are left
blank and flagged `missing` (contracts are never invented) for manual entry.

Build player roles and archetypes from real bio + tracking data:

```bash
python scripts/build_player_roles.py
```

The role engine percentile-scales eleven role dimensions (creation, spacing,
movement shooting, rim pressure, connector, wing defense, rim protection,
rebounding, usage dependency, low-usage fit, sample reliability) from real
player bio (position/height/draft) and tracking (catch-and-shoot, drives,
passing, rebound chances, rim defense), then assigns one of fifteen archetypes.
It writes `data/reports/player_role_explanations.parquet`.

Classify the candidate universe:

```bash
python scripts/build_candidate_universe.py --team PHI
```

This assigns every real player exactly one `candidate_type` from a closed
twelve-type taxonomy (free agent, likely free agent, minimum/MLE/rookie-scale,
realistic/expensive trade target, star-unrealistic, unavailable core, current
Sixer, manual watchlist, missing contract) using real contracts, bio, and a
percentile-scaled quality proxy. Current Sixers are split into
`current_roster_reference.parquet`; the rest land in `candidate_universe.parquet`.

Build the explanation-first target boards:

```bash
python scripts/rank_candidates.py --team PHI
```

The target board engine scores the universe with the saturation-free
`candidate_scoring` engine (surplus-based contract value, percentile-scaled
portability, an eight-factor risk model with tiers, minutes-aware contender
gain) and attaches an explanation to every row: why_fit, concerns, the specific
Sixers gaps addressed, projected role next to the core, salary context,
portability/risk summaries, data sources, missing-data flags, and explanation
confidence. Recommendation tiers are capped at ten Priority targets drawn only
from the realistic board. It writes five split boards
(`candidate_fit_rankings_{all,realistic,free_agents,trade_targets,unrealistic_watchlist}.parquet`).

Validate the boards against hard quality gates:

```bash
python scripts/validate_target_board.py
```

Validation fails non-zero (and writes `data/reports/target_board_validation.md`)
if the realistic board has more than ten Priority targets, contract value or
portability saturates above 10% at 100, a single risk value covers more than half
the pool, any recommendation lacks provenance, a current Sixer or unrealistic
star reaches the realistic board, or explanation columns are missing.

Run offseason backtests:

```bash
python scripts/run_backtest.py --target-team PHI --top-k 10
```

The backtest uses only data before each offseason, builds the target team's
historical roster gap, ranks that offseason's candidate pool, then joins to
next-season outcomes. It compares MoreyMachine against previous-season points,
previous-season impact, salary, and random baselines using Spearman correlation,
top-quartile outcome gaps, top-target hit rates, and average top-target value.
It writes `data/reports/backtest_results.json`,
`data/reports/backtest_rankings.parquet`, and
`data/reports/backtest_summary.md`.

Run the Streamlit dashboard:

```bash
python scripts/run_app.py
```

The dashboard reads existing real Parquet/CSV outputs only and never fetches
live data. In `REAL_DATA_MODE` it never reads `data/demo/`; missing artifacts
render a loud "missing data" message with the command to build them. The
**Data Sources** page shows every table's source, rows, seasons, last update,
and real/manual status.

For online deployment, use `src/moreymachine/app/streamlit_app.py` as the app
entry point on Streamlit Community Cloud or Hugging Face Spaces. See
`DEPLOYMENT.md` for step-by-step instructions.

Format and lint:

```bash
python -m ruff format .
python -m ruff check .
```

## Full pipeline

To rebuild every artifact from real data in order:

```bash
export PYTHONPATH=src
python scripts/refresh_current_data.py --season latest
python scripts/build_playoff_tiers.py
python scripts/build_quality_tiers.py
python scripts/build_team_fingerprints.py
python scripts/train_contender_model.py
python scripts/train_outcome_tier_model.py
python scripts/build_roster_archetypes.py
python scripts/build_player_archetypes.py
python scripts/build_player_roles.py
python scripts/analyze_roster_gaps.py --target-team PHI
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI
python scripts/validate_target_board.py
python scripts/run_backtest.py --target-team PHI
python scripts/run_app.py
```

## Layout

```text
src/moreymachine/   Reusable package code
data/               Local data artifacts, ignored where appropriate
notebooks/          Exploratory notebooks only
scripts/            Project maintenance scripts
tests/              Automated tests
```
