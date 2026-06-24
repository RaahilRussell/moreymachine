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
