# MoreyMachine

MoreyMachine is an unofficial NBA front-office analytics project for studying
Philadelphia 76ers roster gaps, contender roster patterns, and realistic player
acquisition targets.

It is not affiliated with Daryl Morey, the Philadelphia 76ers, the NBA, or any
team or league data provider.

## What It Does

MoreyMachine builds a cached real-data pipeline that:

- refreshes NBA team, player, bio, tracking, and contract tables;
- labels historical playoff and quality tiers;
- learns contender fingerprints and roster archetypes;
- diagnoses the current Sixers roster gaps;
- classifies every real player into exactly one candidate type;
- ranks realistic targets with strict recommendation tiers;
- validates the board against hard anti-demo and anti-saturation gates;
- backtests fit rankings against next-season outcomes and raw-stat baselines;
- serves an explanation-first Streamlit app from cached artifacts only.

## Real Data And Missing Data

Real sources currently used:

- NBA.com Stats through `nba_api` for team seasons, player seasons, player bio,
  and player tracking.
- Hand-verified playoff outcomes in `data/manual/playoff_tiers.csv`.
- Basketball-Reference contracts, id-matched to `nba_api` players.
- Manual real-data overrides in `data/manual/contracts.csv` and
  `data/manual/candidates.csv`.

Hard data rules:

- No fake or demo data is used in real mode.
- Missing contracts, salaries, injuries, transactions, availability, and
  candidate status are not invented.
- Missing fields are preserved as missing and surfaced in `missing_data_flags`.
- The app never falls back to `data/demo/` in `REAL_DATA_MODE`.
- "Real-time" means cached and refreshable real data. Streamlit page loads read
  Parquet, CSV, JSON, and Markdown files only; they do not call live APIs.

## Setup

Use Python 3.11 or newer.

```bash
cd /Users/raahil/moreymachine
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
export PYTHONPATH=src
```

Optional local settings can be placed in `.env`:

```bash
REAL_DATA_MODE=true
MOREYMACHINE_ENV=development
MOREYMACHINE_LOG_LEVEL=INFO
MOREYMACHINE_DATA_DIR=data
MOREYMACHINE_NBA_LATEST_SEASON=2025-26
```

## Full Pipeline

Run from the repository root:

```bash
cd /Users/raahil/moreymachine
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

## Validation

Run these before trusting or deploying outputs:

```bash
export PYTHONPATH=src
python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
pytest
PYTHONPATH=src python -c "import moreymachine; print('import ok')"
```

`validate_target_board.py` fails non-zero if the target board regresses,
including:

- more than 10 Priority Targets on the realistic board;
- more than 10% of candidates with `contract_value >= 95`;
- more than 5% with `portability >= 95`;
- collapsed risk-score distribution;
- missing candidate type, source, provenance, or explanation columns;
- current Sixers, unrealistic stars, or missing-contract players leaking into
  the acquisition board;
- missing-contract, unknown-role, severe-risk, or unrealistic players marked as
  Priority Targets;
- ambiguous salary fields or CSV exports missing explanation columns.

## Manual Contracts And Candidates

Manual files are real-data inputs, not demo fixtures.

`data/manual/contracts.csv` columns:

```text
player_name,player_id,current_team,contract_status,base_salary_millions,
cap_hit_millions,contract_aav_millions,years_remaining,option_status,
free_agent_year,extension_status,salary_source,source_url,pulled_at,data_mode,
missing_data_flags
```

Use `data_mode=real_manual` for verified manual entries. If a value is unknown,
leave it blank and explain it in `missing_data_flags`; do not estimate it.

`data/manual/candidates.csv` columns:

```text
player_name,player_id,current_team,position,candidate_type,expected_salary,
salary_source,source_note
```

Manual candidate types must use the taxonomy enforced by the candidate-universe
builder. Do not use manual rows to force a missing or unavailable player into a
realistic recommendation.

After editing manual files, rerun:

```bash
python scripts/refresh_transactions.py
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI
python scripts/validate_target_board.py
```

## Transaction Freshness

`python scripts/refresh_transactions.py` writes
`data/processed/transactions.parquet` from Spotrac's recent NBA transaction
feed. Candidate rows carry `candidate_status_freshness`:

- `verified_current`
- `stale_needs_review`
- `conflict_between_sources`
- `manual_verification_required`

Top-50 realistic/free-agent candidates with a status-changing transaction newer
than the salary pull date are forced into manual review and cannot become
Priority Targets. Recent signings, extensions, and exercised options move stale
free-agent candidates out of free-agent lanes rather than treating old status as
current.

## Score Interpretation

The target board is explanation-first. Every row should include:

- `why_fit`
- `concerns`
- `gaps_addressed`
- `role_on_sixers`
- `salary_context`
- `acquisition_summary`
- `risk_summary`
- `data_sources`
- `missing_data_flags`

Score components:

- `need_match`: how well the player answers PHI's weighted roster gaps.
- `contender_gain`: minutes-aware estimate of how much the player improves
  contender similarity.
- `portability`: playoff-friendly role traits, percentile-scaled so elite scores
  are rare.
- `contract_value`: role-relative price/value signal; missing salary data is not
  treated as a bargain.
- `risk_score`: age, sample, shooting, role, acquisition, contract, and missing
  data risk.
- `final_fit`: blended fit score after risk penalty.

Recommendation tiers are strict. `Priority Target` is capped at 10 and can only
come from the realistic board.

## Backtest

```bash
python scripts/run_backtest.py
```

The backtest uses chronological offseason splits. For each previous season, it
builds roster gaps using only data available through that season, ranks the
historical non-PHI candidate universe, then compares to next-season outcomes.

Backtest outputs:

- `data/reports/backtest_results.json`
- `data/reports/backtest_rankings.parquet`
- `data/reports/backtest_summary.md`

Basketball-fit outcomes are separated from contract surplus. Contract-value
backtesting only runs where historical salary data exists.

## App

```bash
PYTHONPATH=src streamlit run src/moreymachine/app/streamlit_app.py
```

The app pages are:

- Overview
- Data Sources
- Sixers Roster Diagnosis
- Contender Blueprint
- Realistic Target Board
- Free Agent Board
- Trade Target Board
- Unrealistic Watchlist
- Player Detail
- Model Diagnostics
- Backtest Proof

If a required real table is missing, the app shows the exact script to run. It
does not silently use demo data.

## Known Limitations

- Current and historical injury status is not sourced.
- Transaction intent and true trade availability are not sourced.
- Historical free-agent and trade-target statuses are incomplete, so the
  backtest does not invent a free-agent split.
- Contract-value backtesting is limited until historical salary coverage is
  complete.
- `base_salary_millions` and `contract_aav_millions` can be absent when the
  source does not provide them; those fields stay missing rather than estimated.
- The model can lose to simple raw-volume baselines when next-season value is
  dominated by minutes or scoring volume.

## Layout

```text
src/moreymachine/   Reusable package code
data/               Cached local artifacts and manual real-data inputs
scripts/            Pipeline and validation entry points
tests/              Automated tests
```
