# MoreyMachine

MoreyMachine is an unofficial NBA roster-construction project that ranks potential 76ers acquisition targets by fit, role, contract context, risk, and how much they address specific roster gaps.

## Product Summary

MoreyMachine is an unofficial NBA front-office analytics app built around a
simple question:

> If I were trying to improve the Philadelphia 76ers like an analytics-heavy GM,
> which players would actually make sense — and why?

The app does not just rank players by talent or box-score stats. It builds a
target board by combining:

- Philadelphia's current roster gaps
- historical contender team patterns
- player role/archetype modeling
- playoff portability
- contract and salary context
- acquisition feasibility
- risk and missing-data flags

The output is split into separate boards so the app does not pretend every
player is equally available:

- Realistic Target Board
- Free Agent Board
- Trade Target Board
- Unrealistic Watchlist
- Player Detail scouting pages
- Model Diagnostics
- Backtest Proof

The main goal is not to perfectly predict what the Sixers should do. It is to
build a more honest version of a GM-style decision tool: one that explains why a
player fits, what assumptions the model is making, what data may be stale, and
where the recommendation could be wrong.

At its best, MoreyMachine helps answer:

- What type of player does this roster actually need?
- Which players fit that role statistically?
- Which players are cheap or expensive relative to their role?
- Which players look good in the model but are unrealistic to acquire?
- Which recommendations are weakened by missing or stale data?

This project is intentionally built around data integrity. Earlier versions were
too easy to fool with fake/demo rankings or overly confident scores, so the
current version includes validation gates, provenance columns, candidate-type
separation, and explanation fields for every recommendation.

It is not affiliated with Daryl Morey, the Philadelphia 76ers, the NBA, or any
team or league data provider.

## Why I Built This

I wanted to understand what an analytics-heavy GM model would actually have to
consider. At first, the project was basically a fit board: pull some player
stats, score the obvious names, and sort the table.

That was not enough. A real roster question is not just "who is good?" It is
closer to:

> Who fits this roster, at this price, in this role, given what serious playoff
> teams usually need?

That question forced the project into different territory. I had to separate raw
talent from roster fit, role fit, acquisition feasibility, contract context, and
data reliability. A player can look great statistically and still be the wrong
answer if the contract is impossible, the role overlaps with the current roster,
the status is stale, or the data source is missing something important.

The biggest lesson from building this was that the table is the easy part. The
harder part is stopping the table from showing confident nonsense. MoreyMachine
started as a naive board, then went through a rebuild: fake/demo data was removed
from real mode, NBA data was cached locally, score saturation had to be fixed,
candidate types were split more carefully, and the target board became
explanation-first instead of just score-first.

## What The App Does

The Streamlit app is a local dashboard for reading the generated artifacts. It
does not call live APIs during page loads.

| Page | What it is useful for |
| --- | --- |
| Overview | Shows what the system is trying to do, what data is real, what is missing, and how to read the outputs. |
| Data Sources | Audits each table: rows, seasons, source, pull time, freshness, real/manual status, missing fields, and rebuild command. |
| Sixers Roster Diagnosis | Summarizes Philadelphia's biggest roster gaps and why each gap matters in a playoff setting. |
| Contender Blueprint | Compares PHI to deep-playoff team patterns, quality tiers, roster archetypes, and contender benchmarks. |
| Realistic Target Board | Shows only candidates the model currently considers realistic/acquirable, with strict recommendation tiers and explanation columns. |
| Free Agent Board | Separates UFA/RFA/likely free-agent/minimum/MLE candidates and shows salary/source context where available. |
| Trade Target Board | Shows realistic and expensive trade candidates while excluding current Sixers and core/unavailable players. |
| Unrealistic Watchlist | Keeps theoretical fits visible without pretending they are recommendations. |
| Player Detail | Expands one player into a scouting-report-style view: score breakdown, role, gaps addressed, concerns, salary context, and sources. |
| Transaction Review | Flags players whose candidate status may be stale because recent transactions conflict with salary/candidate data. |
| Model Diagnostics | Checks score distributions, recommendation counts, saturation, risk distribution, and validation warnings. |
| Backtest Proof | Compares historical fit rankings to next-season outcomes and simple baselines. |

## The Actual Modeling Idea

MoreyMachine does not ask "Who is the best player?"

It asks:

- What does Philadelphia need?
- What kind of players usually survive deep playoff runs?
- What role would this player realistically play?
- Is the player's value portable to the playoffs?
- Is the contract or acquisition cost reasonable?
- What data is missing, stale, or uncertain?

The final board is a blend of several imperfect signals. None of these scores is
meant to be trusted by itself.

| Score | What it means | What goes into it | What a high score means | How it can mislead |
| --- | --- | --- | --- | --- |
| Need Match | How directly a player addresses the current PHI gaps. | The Sixers roster-gap analysis, player role/archetype features, position, shooting, creation, defense, size, and play-finishing signals. | The player fills something the roster actually needs, not just something he is good at. | It can overrate a specialist if the model identifies the right gap but misses whether that player can stay on the floor in the playoffs. |
| Contender Similarity Gain | How much adding the player moves PHI toward patterns seen in stronger playoff teams. | Team fingerprints, roster archetypes, quality tiers, player roles, and contender-model outputs. | The player helps PHI look more like teams that usually survive deeper rounds. | It depends on historical patterns, so it can miss unusual roster builds or coaching contexts. |
| Playoff Portability | Whether the player's value is likely to translate against playoff defenses. | Role stability, shooting profile, defensive indicators, size/position context, usage, efficiency, and archetype signals. | The player has traits that are less likely to disappear when matchups tighten. | Public stats are a rough proxy. They do not fully capture scheme discipline, decision-making, or how opponents would guard him. |
| Contract Value | Whether the player looks useful relative to known salary context. | Manual and scraped/public contract fields where available: cap hit, AAV, years remaining, option status, salary bucket, and missing-data flags. | The player looks helpful without consuming too much salary flexibility. | Missing or stale contract data can make this score less reliable, so missing salary is not treated as a bargain. |
| Risk | How much uncertainty or downside is attached to the candidate. | Age, role volatility, sample size, shooting stability, missing data, contract uncertainty, candidate type, and acquisition difficulty. | Lower risk means fewer known red flags in the data the project currently has. | It is not a full medical or scouting risk model. Injuries, private information, and locker-room/team context are mostly missing. |
| Acquisition Feasibility | How plausible it is that the player belongs in a real target board lane. | Candidate type, salary bucket, contract status, current team, manual candidate overrides, transaction freshness, and watchlist rules. | The player is closer to an actual free-agent/trade target than a fantasy add. | It still does not know private team intent, exact asking price, or whether the other team would answer the phone. |

## Data Pipeline

The app reads generated files. The scripts build those files.

Current data inputs include:

- `nba_api` / NBA.com Stats for team seasons, player seasons, player bio, and
  tracking-style tables where available.
- Hand-maintained playoff outcomes in `data/manual/playoff_tiers.csv`.
- Public contract data and manual real-data CSVs for contracts/candidates when
  reliable API coverage is not available.
- A recent transaction cache from Spotrac's NBA transaction feed.
- Local Parquet, CSV, JSON, and Markdown artifacts under `data/`.

The important distinction:

> The app is not truly live. It is refreshable.

That means data can be updated by running the pipeline, but the Streamlit app
itself reads cached, validated files. It does not scrape contracts, call
`nba_api`, or fetch transactions during each page load.

This is intentional. If a table is missing in real mode, the app should show a
clear error and the script needed to rebuild it. It should not silently fall back
to demo data.

## Data Integrity And Validation

Earlier versions of the board were too easy to fool. They could produce a
reasonable-looking table even when the inputs were stale, the scores were
saturated, or an unrealistic player leaked into a recommendation tier.

The validation layer exists to make that harder.

Current target-board gates include:

- no demo data in real mode;
- no more than 10 `Priority Target` rows;
- no current Sixers players in acquisition boards;
- unrealistic/watchlist players cannot become priority targets;
- missing-contract players cannot become priority targets;
- stale/manual-review status players cannot become priority targets;
- contract value cannot saturate across the board;
- portability cannot saturate across the board;
- risk scores cannot collapse into one repeated value;
- every candidate needs `candidate_type`;
- every recommendation needs explanation and provenance columns;
- every row needs data-source context;
- the CSV export must carry the explanation columns too.

The goal is not just to make a table. The goal is to make it hard for the app to
show confident nonsense.

The current local check suite is:

```bash
export PYTHONPATH=src
python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
pytest
PYTHONPATH=src python -c "import moreymachine; print('import ok')"
```

Passing these checks means the artifacts satisfy the project's data contracts and
guardrails. It does not prove the basketball recommendations are correct.

## Build Process / What Changed Over Time

This project changed a lot as the failure modes became more obvious.

1. The first version had the shape of a GM board, but it relied too much on
   fake/demo data and loose assumptions.
2. I rebuilt the pipeline around cached real NBA data so the app was not just a
   nice-looking demo.
3. The next issue was score saturation: too many players looked like perfect
   contract values or perfect playoff fits. The scoring model had to be tightened
   so elite scores were rare.
4. Candidate types were split into realistic targets, free agents, trade targets,
   unrealistic/watchlist players, missing-contract players, and manual-review
   cases.
5. The target board became explanation-first. A row now needs `why_fit`,
   `concerns`, `gaps_addressed`, `role_on_sixers`, `salary_context`,
   `acquisition_summary`, `risk_summary`, `data_sources`, and
   `missing_data_flags`.
6. Validation gates were added so regressions fail loudly instead of producing a
   polished but wrong board.
7. Backtesting was added to compare historical rankings against next-season
   outcomes and simple baselines.
8. The biggest remaining issue is candidate-status freshness, especially during
   the offseason.

That last point matters. The model can only be as current as its contract,
transaction, and candidate-status data.

## Limitations

These limitations are not bugs I want to hide. They are the exact places where
public data stops being enough.

- Public contract data can lag or be incomplete.
- Some fields like base salary, cap hit, and AAV may be missing when sources do
  not provide them.
- Transaction status can go stale quickly during the offseason.
- Recent signings, extensions, options, trades, and free-agent status changes
  need verification before they should affect a real board.
- The model does not fully know true trade availability.
- The model does not know private team intent.
- Injury status and medical risk are not fully sourced.
- Historical free-agent and trade status are incomplete, so the backtest cannot
  perfectly simulate real offseasons.
- Contract-value backtesting is limited when historical salary coverage is
  missing.
- Fit score does not mean "the Sixers should actually acquire this player."
- A player can fit statistically but be impossible, overpriced, redundant, or
  just a bad real-world acquisition.
- The model is better at basketball-fit diagnosis than real front-office
  feasibility.

This is why the app separates realistic boards, free-agent boards, trade boards,
watchlists, manual-review rows, and missing-data flags instead of forcing
everything into one confident ranking.

## What Full Real-Time Data Would Improve

A true front-office version would need a stronger status layer than this repo can
currently provide with public and manual data.

Useful future infrastructure would include:

- a live transaction feed;
- a current contract/API feed;
- injury and availability data;
- lineup and on/off data updated daily;
- play-by-play or possession-level data;
- a trade-asset and trade-cost model;
- a team intent/context model;
- a news/status verification layer;
- automatic stale-status warnings;
- a manual review queue for recent signings, extensions, options, and trades.

That would improve the board in practical ways:

- more accurate `candidate_type`;
- better acquisition feasibility;
- better salary context;
- better risk scoring;
- fewer stale offseason recommendations;
- better player-specific explanations;
- clearer separation between "good basketball fit" and "actually obtainable."

Right now, MoreyMachine has a transaction freshness layer, but it is still a
cache plus validation system. It can flag conflicts and force manual review. It
does not fully solve real-time status truth.

## Example Pick Explanation Format

The target board is supposed to explain a pick, not just rank a name.

Example format:

**Player X**

- **Why the model likes him:** He adds a specific skill the current roster is
  missing and his role profile matches what the model values in playoff lineups.
- **Which Sixers gaps he addresses:** Shooting, secondary creation, defensive
  size, rebounding, or whatever gaps the roster diagnosis identified.
- **Role next to Embiid/Maxey:** Spacer, connector, low-usage defender,
  bench creator, movement shooter, small-ball big, or another explicit role.
- **Salary/acquisition context:** Minimum, MLE, likely free agent, realistic
  trade target, expensive but possible, contract blocked, or manual review.
- **Main concerns:** Risk flags such as role volatility, shooting sample, age,
  defense, contract uncertainty, stale transaction status, or missing data.
- **Missing data:** Contract fields, injury data, transaction status, candidate
  status, or other fields the system could not source.
- **Recommendation interpretation:** Whether this is a real target, a conditional
  target, a watchlist player, or a manual-review case.

## Installation

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

## Full Local Pipeline

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
streamlit run src/moreymachine/app/streamlit_app.py
```

`refresh_transactions.py` is included because candidate-status freshness is now
part of the ranking and validation layer.

## Manual Data

Manual files are real-data inputs, not demo fixtures.

Contracts live in `data/manual/contracts.csv`. Use `data_mode=real_manual` for
verified manual rows. If a field is unknown, leave it blank and explain it in
`missing_data_flags`; do not estimate it.

Manual candidate overrides live in `data/manual/candidates.csv`. They should be
used to add sourced context, not to force an unavailable or missing-status player
into a recommendation tier.

After editing manual files, rerun:

```bash
python scripts/refresh_transactions.py
python scripts/build_candidate_universe.py --team PHI
python scripts/rank_candidates.py --team PHI
python scripts/validate_target_board.py
```

## Backtest

```bash
python scripts/run_backtest.py
```

The backtest uses chronological offseason splits. For each historical offseason,
it builds roster gaps using only data available before that offseason, ranks the
candidate universe, then compares to next-season outcomes.

Outputs:

- `data/reports/backtest_results.json`
- `data/reports/backtest_rankings.parquet`
- `data/reports/backtest_summary.md`

The backtest is useful, but it is not a clean simulation of what an NBA team
would have known. Historical contract status, free-agent status, and trade
availability are incomplete. Contract-value backtesting is separated from
basketball-fit backtesting for that reason.

## Run The App

```bash
cd /Users/raahil/moreymachine
source .venv/bin/activate
export PYTHONPATH=src
streamlit run src/moreymachine/app/streamlit_app.py
```

If a required real table is missing, the app should say which file is missing and
which script to run. It should not silently use demo data in real mode.
