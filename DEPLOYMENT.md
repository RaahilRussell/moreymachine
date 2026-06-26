# MoreyMachine Deployment

MoreyMachine deploys as a Streamlit app backed by committed, cached real-data
artifacts. It does not fetch NBA data or scrape contracts during page loads.

Unofficial project. Not affiliated with Daryl Morey, the Philadelphia 76ers, the
NBA, or any data provider.

## Deployment Rule

Build and validate the data locally first, then deploy the app with the generated
`data/` artifacts included. In `REAL_DATA_MODE=true`, missing real files produce
clear app errors and demo files are never substituted.

## Local Build Before Deploy

```bash
cd moreymachine
source .venv/bin/activate
export PYTHONPATH=src

python scripts/refresh_current_data.py --season latest
python scripts/refresh_transactions.py
python scripts/build_playoff_tiers.py
python scripts/build_quality_tiers.py
python scripts/build_team_fingerprints.py
python scripts/train_contender_model.py
python scripts/train_outcome_tier_model.py
python scripts/build_roster_archetypes.py
python scripts/build_player_archetypes.py
python scripts/build_player_roles.py
python scripts/analyze_roster_gaps.py --team PHI
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI
python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
python scripts/run_backtest.py
PYTHONPATH=src streamlit run src/moreymachine/app/streamlit_app.py
```

## Final Checks

```bash
export PYTHONPATH=src
python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
pytest
PYTHONPATH=src python -c "import moreymachine; print('import ok')"
```

## Streamlit Community Cloud

1. Push the repository, including the validated `data/` artifacts.
2. Create a new Streamlit app from the repository.
3. Set the main file path to:

   ```text
   src/moreymachine/app/streamlit_app.py
   ```

4. Use the root `requirements.txt`.
5. Keep `REAL_DATA_MODE=true`.
6. Deploy.

The Data Sources page will show rows, seasons, source, pulled-at timestamp,
freshness age, real/manual status, missing fields, and rebuild commands for each
registered table.

## Hugging Face Spaces

1. Create a Streamlit Space.
2. Upload or connect this repository with the validated `data/` artifacts.
3. Keep `requirements.txt` at the repository root.
4. Set the app file to `src/moreymachine/app/streamlit_app.py`.
5. Keep `REAL_DATA_MODE=true`.

## Local App Run

```bash
cd moreymachine
source .venv/bin/activate
export PYTHONPATH=src
streamlit run src/moreymachine/app/streamlit_app.py
```

If the default port is busy, use:

```bash
streamlit run src/moreymachine/app/streamlit_app.py --server.port 8510
```

## Updating Data After Deploy

Refresh locally, commit the changed artifacts, and redeploy:

```bash
python scripts/refresh_current_data.py --season latest
python scripts/refresh_transactions.py
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI
python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
python scripts/run_backtest.py
```

Do not add runtime API calls to Streamlit pages. Real-time means the cached data
can be refreshed and redeployed, not live API calls inside page loads.

## Manual Data

Manual contracts live in `data/manual/contracts.csv`. Manual candidates live in
`data/manual/candidates.csv`.

Only enter sourced real values. Use `missing_data_flags` or `source_note` to
explain blanks. Do not fabricate contract, salary, injury, transaction,
availability, or candidate-status fields.

## Known Deployment Limitations

- Historical injury, transaction, and availability data are not sourced.
- Historical free-agent/trade status is incomplete, so the backtest does not
  show a free-agent split unless that data is sourced later.
- Contract-value backtesting is limited when historical salary data is absent.
- Streamlit Cloud storage is read-only at runtime for this use case; refresh data
  locally and commit regenerated artifacts.
