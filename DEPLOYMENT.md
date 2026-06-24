# MoreyMachine Deployment

MoreyMachine runs online from **real, precomputed Parquet/CSV files**. The app
never calls the NBA API or scrapes salaries at runtime, and in `REAL_DATA_MODE`
(the default) it never falls back to demo data — missing files render explicit
"missing data" guidance instead.

> Unofficial project. Not affiliated with Daryl Morey, the Philadelphia 76ers,
> or the NBA.

## 1. Build the real data locally (once, before deploying)

Run the pipeline in order. Each step writes real artifacts under `data/`:

```bash
python scripts/fetch_nba_data.py            # nba_api -> team_seasons / player_seasons (+ provenance)
python scripts/build_playoff_tiers.py       # join real playoff tiers
python scripts/build_quality_tiers.py       # within-season quality tiers
python scripts/build_team_fingerprints.py   # team fingerprints + engineered scores
python scripts/train_contender_model.py     # deep-playoff model + metrics
python scripts/train_outcome_tier_model.py  # playoff-tier (0-5) model + metrics
python scripts/build_roster_archetypes.py   # team roster archetypes
python scripts/build_player_archetypes.py   # player archetypes
python scripts/fetch_candidates.py --team PHI    # real candidates + BBRef salaries
python scripts/analyze_roster_gaps.py --team PHI # PHI roster gap report
python scripts/rank_candidates.py --team PHI     # GM Fit Score rankings
python scripts/run_backtest.py              # backtest vs baselines
streamlit run src/moreymachine/app/streamlit_app.py
```

The fetch/salary steps need network access and run **locally only**. Commit the
resulting `data/processed`, `data/features`, `data/models`, `data/reports`, and
`data/manual` artifacts so the deployed app can load them without any live calls.

## 2. Streamlit Community Cloud

1. Push the repository (including the committed `data/` artifacts) to GitHub.
2. Create a new app from the repository.
3. Set the main file path to:

   ```text
   src/moreymachine/app/streamlit_app.py
   ```

4. Use the default Python environment and root `requirements.txt`.
5. `REAL_DATA_MODE` defaults to `true`; leave it set so the app refuses demo data.
6. Deploy. The **Data Sources** page shows every table's source, rows, seasons,
   last update, and real/manual status.

## 3. Hugging Face Spaces

1. Create a Space with the Streamlit SDK.
2. Connect or upload this repository (with committed `data/` artifacts).
3. Set the app file to `src/moreymachine/app/streamlit_app.py`.
4. Ensure `requirements.txt` is at the repository root.
5. Start the Space.

## 4. Local run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
# build data (section 1), then:
streamlit run src/moreymachine/app/streamlit_app.py
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `REAL_DATA_MODE` | `true` | When on, the app/pipeline fail loudly on missing real files and never read `data/demo`. |
| `MOREYMACHINE_NBA_START_SEASON` | `2015-16` | First season to fetch. |
| `MOREYMACHINE_NBA_LATEST_SEASON` | current | Last season to fetch. |

## Demo data

`data/demo/` contains tiny, clearly-labeled toy files used only for offline UI
experiments. They are **never** loaded in `REAL_DATA_MODE` and are not part of
the dataset registry, so they can never enter real rankings.
