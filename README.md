# MoreyMachine

MoreyMachine is an unofficial NBA front-office analytics engine for studying
contender roster construction and player fit.

This project is not affiliated with Daryl Morey, the Philadelphia 76ers, or the
NBA.

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

Add manual playoff outcomes in `data/manual/playoff_tiers_template.csv` with
one row per team-season:

```text
season,team_abbr,playoff_tier,playoff_result
```

Playoff tiers:

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

Rank acquisition candidates:

```bash
python scripts/rank_candidates.py --top-n 50
```

The candidate fit model ranks free agent or trade targets from player stats,
target roster gaps, player archetypes, optional contract estimates, optional
precomputed playoff portability scores, and the contender model artifact when
available. It writes `data/reports/candidate_fit_rankings.parquet` with need
match, contender similarity gain, playoff portability, contract value, risk,
final GM Fit Score, recommendation labels, fit explanations, and concerns.

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

The dashboard reads existing Parquet and JSON outputs only. It does not fetch
live data. For Streamlit Community Cloud, use
`src/moreymachine/app/streamlit_app.py` as the app entry point after the package
dependencies are installed.

Format and lint:

```bash
python -m black .
python -m ruff check .
```

## Layout

```text
src/moreymachine/   Reusable package code
data/               Local data artifacts, ignored where appropriate
notebooks/          Exploratory notebooks only
scripts/            Project maintenance scripts
tests/              Automated tests
```
