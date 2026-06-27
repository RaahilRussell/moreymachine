# MoreyMachine

MoreyMachine is an unofficial NBA roster-construction project that has grown into a basketball-operations / GM operating system. It starts at the team level, identifies the benchmark path, turns gaps into priorities, and only then ranks potential moves and player targets.

It is not affiliated with Daryl Morey, the Philadelphia 76ers, the NBA, or any team or league data provider.

## Product Summary

MoreyMachine is an unofficial NBA front-office analytics app built around a simple question:

> If I were trying to improve the Philadelphia 76ers like an analytics-heavy GM, which players would actually make sense, and why?

The app used to be too table-driven: useful rows, not enough actual decision flow. The current version is strategy-first. It builds a team read, compares that team to contender benchmarks, identifies the gaps that matter, then turns those gaps into action cards, move recommendations, target boards, player profiles, and evidence.

The app does not rank players by talent or box-score stats alone. It builds the basketball case by combining:

- Philadelphia's current roster gaps
- historical contender team patterns
- player role and archetype modeling
- playoff portability
- contract and salary context
- acquisition feasibility
- risk and missing-data flags

The output is split into separate views so the app does not pretend every player is equally available:

- Target Board v2
- Free Agent and Trade Target segments
- Unrealistic Watchlist
- Player Detail scouting pages
- Player Compare
- Best By Need
- Model and reasoning diagnostics
- Backtest proof

The main goal is not to perfectly predict what the Sixers should do. It is to build a more honest version of a GM-style decision tool: one that explains why a player fits, what assumptions the model is making, what data may be stale, and where the recommendation could be wrong.

At its best, MoreyMachine helps answer:

- What type of player does this roster actually need?
- Which players fit that role statistically?
- Which players are cheap or expensive relative to that role?
- Which players look good in the model but are unrealistic to acquire?
- Which recommendations are weakened by missing or stale data?

This project is intentionally built around data integrity. Earlier versions were too easy to fool with fake/demo rankings or overly confident scores, so the current version includes validation gates, provenance columns, candidate-type separation, scenario-aware role logic, evidence objects, and player profiles for every recommendation.

## GM Executive Summary

The first page is designed to answer the questions a GM-style user would ask before opening any table:

- what team is selected
- what level the team is currently at
- which contender archetype or benchmark it is closest to
- what the roster needs to become a real contender
- what to do first
- what not to do
- which players and moves matter
- why the model believes that
- what missing data could change the answer

The executive summary is built from action cards and validated artifacts, not from a raw ranking table. If the narrative layer is disabled or Ollama is unavailable, the app shows a deterministic fallback summary generated from the same structured JSON.

## Why I Built This

I wanted to understand what an analytics-heavy GM model would actually have to consider. I did not want to rank players by points per game, sort by a fit score, and call it a front-office tool.

The real question was more specific:

> Who fits this roster, at this price, with this role, given what serious playoff teams usually need?

That question forced the project to separate raw talent, roster fit, acquisition feasibility, role conflict, contract context, and data reliability. A player can be good and still be a bad answer for Philadelphia. A center can be useful and still not be a starter next to Joel Embiid. A cheap player can be interesting and still not solve a real playoff gap. A star can look perfect statistically and still belong on a watchlist instead of the realistic board.

I started with a simple fit board, realized it was too naive, then rebuilt the project around cached real data, provenance, validation, roster-slot logic, and explanations. The table is not the hard part. The hard part is stopping the table from saying confident basketball things it cannot support.

## Industry-Grade Reasoning Architecture

MoreyMachine does not rank players directly from stats. The current pipeline is sequenced so the product understands the roster context before it recommends anyone:

```text
raw/cached data
-> entity resolution
-> data lineage
-> current Sixers roster world
-> contract/status state
-> contender blueprint
-> Sixers gap model
-> player skill profiles
-> player-to-player compatibility
-> roster slot + minutes simulation
-> acquisition feasibility
-> scenario engine
-> recommendation engine v2
-> evidence-based explanation engine
-> player profile builder
-> reasoning/profile validation
-> Streamlit product UI
```

The important rule is that general player quality cannot override roster-slot logic. A candidate is not called a starter unless the simulated Sixers role supports it. A player does not get credit for spacing, defense, rim protection, rebounding, or creation unless the skill-profile gates allow that claim. A recommendation is not allowed to outrun scenario robustness, acquisition feasibility, stale status, or missing contract context.

## Team Selector / Analyze Any Team

The app is team-scoped. The sidebar has a selected team, benchmark selector, quick player search, artifact status, and the exact pipeline command needed when outputs are missing.

Philadelphia has custom context because Embiid, Maxey, and George create specific roster constraints. Other teams can still be selected, but missing team-specific artifacts are shown honestly. The app should not silently fall back to Philadelphia outputs for another team.

The team pipeline command is:

```bash
python3 scripts/run_team_pipeline.py --team PHI --skip-refresh
```

Optional flags:

```bash
python3 scripts/run_team_pipeline.py --team PHI --skip-refresh --stages team_level,move_recommendations --no-ollama
```

## Benchmark Comparison

The team comparison layer is meant to make the target concrete. It compares the selected team to champion average, finalist average, conference finalist average, top net-rating groups, style benchmarks, and current teams when the data is available.

The comparison does not say "be Boston" or "be Denver" as a slogan. It asks which measurable traits are close, which are far away, and what level of improvement is required before a team can be treated like a credible contender.

## Move Recommendations

Move recommendations are downstream of roster simulation, compatibility, feasibility, opportunity cost, scenarios, and evidence validation. That order matters. A player cannot become a real recommendation just because he has a high general fit score.

The action-card layer turns the board into decision categories:

- best overall action
- best realistic free-agent action
- best realistic trade action
- best low-cost depth action
- best backup-center route
- best wing-defense route
- best shooting route
- best internal or stay-put action
- top avoid move
- manual review action

Every move card needs `why_do_this`, `why_not_do_this`, and evidence. If the evidence is missing, the system should say that instead of smoothing it over.

## Ollama Narrative Layer

Ollama is optional and disabled by default. It is never the source of truth.

The narrative layer sends structured JSON packets to Ollama only after the pipeline has already produced validated team level, comparison, action cards, rankings, and evidence. Every prompt includes the rule that it must use only the JSON and must not invent facts. If Ollama is unavailable, the deterministic fallback summary is used.

Default config lives at `data/manual/llm_config.yml`.

## Professional App Design

The Streamlit app is a summary-first GM console — the "War Room". No page opens with a giant dataframe before explaining what matters. The visual system (`src/moreymachine/app/ui.py`) gives meaning a consistent color vocabulary: court navy for the brand, a single hardwood-amber accent, signal red reserved for "avoid" and high-severity gaps, and mono numerals so every metric reads like a scoreboard.

Navigation is grouped into the GM's actual workflow instead of a flat list, using `st.navigation` sections:

```text
War Room
  -> Command Center            (status band, scoreboard KPIs, do-first decision
                                cards, biggest gaps, closest benchmark, GM read)
Team Read
  -> Roster & Depth Chart      (depth chart by role, contention window, composition)
  -> Team Level
  -> Benchmark Path            (distance-by-dimension bars)
  -> Gap Priority Model        (severity-ranked bars)
  -> Contender Blueprints
Decisions
  -> Move Recommendations      (action cards rendered as decision cards)
  -> Target Board
  -> Best By Need
  -> Move Compare
Player Research
  -> Player Detail / Compare / Skill Profiles / Core Compatibility
  -> Roster Slot Simulation / Candidate Scenarios
Front Office Ops
  -> Transaction Review / Manual Review Queue / Data Sources / Analyze Any Team
Trust & Method
  -> Reasoning Diagnostics / Backtest Proof / Limitations / How It Reasons
```

The Command Center is the landing page: a team status band, a scoreboard KPI strip, the top "do first" moves as decision cards (each with the call, why to do it, and what would make it wrong), the biggest roster gaps as severity bars, and the distance to the closest contender benchmark. The Roster & Depth Chart adds the planning view a GM opens first — who is on the team, where they slot, and how the contention window looks against the core's ages.

Repeated widgets use stable unique keys. Empty states are clean and useful: if an artifact is missing, the UI shows the exact command to rebuild it.

## Interactive Player Profiles

The app is now built around the player profile, not just the board row. Clicking or searching a player should answer:

- why he is ranked there
- what he helps most
- what he does not solve
- what role he would actually play on this Sixers roster
- whether that role is open, blocked, or scenario-dependent
- how he fits with Embiid, Maxey, and George
- what the salary/acquisition reality looks like
- what the best-case, realistic-case, downside, playoff, overpay, and missing-data scenarios are
- what evidence supports the claims
- what could make the recommendation wrong

Each profile is generated from structured artifacts, not by parsing a final CSV. The profile includes score breakdowns, salary cards, help-impact rows, scenarios, evidence objects, unsupported-claim flags, and missing/stale data flags.

## Best By Need

The board is useful, but total score is not always the right way to search. MoreyMachine also builds `best_by_need` rankings for questions like:

- backup center
- non-Embiid rim protection
- wing defense
- point-of-attack defense
- shooting volume
- movement shooting
- bench creation
- low-usage connector
- rebounding
- size
- regular-season depth
- playoff rotation piece
- stretch forward
- matchup big

This matters because the best player overall is not always the best answer to a specific roster problem.

## Data Pipeline

The app reads generated files. The scripts build those files.

Current data inputs include:

- `nba_api` / NBA.com Stats for team seasons, player seasons, player bio, and available tracking-style tables
- manual playoff outcomes in `data/manual/playoff_tiers.csv`
- public and manual real-data contract/candidate files when reliable API coverage is not available
- a cached recent transaction feed
- local Parquet, CSV, JSON, and Markdown artifacts under `data/`

The key distinction:

> The app is not truly live. It is refreshable.

That means data can be updated by running the pipeline, but the Streamlit app itself reads cached, validated files. It does not scrape contracts, call `nba_api`, or fetch transactions during page loads. If a required artifact is missing, the app shows the script needed to rebuild it.

## Data Integrity and Validation

Earlier versions were too easy to fool. They could show a polished table even when the board used demo rows, score distributions saturated, unrealistic players leaked into recommendation tiers, or a player was given credit for a skill the evidence did not support.

The current validation layer checks things like:

- no demo data in real mode
- no more than 10 Priority Targets
- no current Sixers players in acquisition boards
- unrealistic/watchlist players cannot become Priority Targets
- missing-contract or stale-status players cannot become Priority Targets
- contract value and portability cannot saturate across the board
- risk scores cannot collapse into one repeated value
- every recommendation needs explanation and provenance columns
- every claim needs an evidence object
- no unsupported spacing, defense, rim protection, rebounding, creation, or starter claims
- no center-starter conflict with Embiid
- no high recommendation without a clear roster role
- every board player needs a player profile, salary card, help areas, scenarios, and evidence summary

Passing the checks means the artifacts satisfy the project's contracts and guardrails. It does not prove basketball truth.

## Build Process / What Changed Over Time

This project changed as the failure modes became obvious:

1. The first version had the shape of a GM board but relied too much on fake/demo data.
2. I rebuilt the pipeline around cached real NBA data.
3. The next problem was score saturation: too many players looked like perfect contract values or perfect playoff fits.
4. Candidate types were split into realistic targets, free agents, trade targets, watchlist players, missing-contract rows, and manual-review cases.
5. Explanations and provenance were added to every recommendation.
6. Validation gates and backtesting were added so failures would be loud.
7. The latest rebuild added roster-world context, compatibility with Embiid/Maxey/George, roster-slot simulation, scenario-aware recommendations, evidence objects, player profiles, scouting-report exports, and reasoning validation.

The biggest remaining issue is candidate-status freshness. Transactions, options, extensions, and free-agent status can change faster than a local public-data pipeline can keep up.

## What Full Real-Time Data Would Improve

A true front-office version would need stronger status infrastructure than this repo can provide with public and manual data:

- live transaction feed
- current contract/API feed
- injury and availability data
- lineup and on/off data updated daily
- play-by-play or possession-level data
- trade asset and trade-cost model
- team intent/context model
- news/status verification layer
- automatic stale-status warnings
- manual review queue for recent signings, extensions, options, and trades

That would improve candidate type, acquisition feasibility, salary context, risk scoring, stale-offseason warnings, and player-specific explanations.

## Limitations

These limitations are not things I want to hide. They are the places where public data stops being enough.

- Public contract data can lag or be incomplete.
- Base salary, cap hit, and AAV are separated because sources do not always provide all three.
- Transaction status can go stale quickly during the offseason.
- The model does not fully know true trade availability.
- The model does not know private team intent.
- Injury status and medical risk are not fully sourced.
- Historical free-agent and trade status are incomplete, so backtesting cannot perfectly simulate real offseasons.
- Contract-value backtesting is limited when historical salary coverage is missing.
- Fit score does not mean "the Sixers should actually acquire this player."
- A player can fit statistically but be impossible, overpriced, redundant, or dumb to acquire.
- MoreyMachine is better at basketball-fit diagnosis than real-world front-office feasibility.

## Example Pick Explanation Format

The app is designed to explain a pick like this, using a real player profile row when available:

```text
Player X

Why the model likes him:
Which Sixers gaps he addresses:
Role next to Embiid/Maxey/George:
Salary/acquisition context:
Main concerns:
Missing data:
Recommendation interpretation:
Evidence:
```

If the evidence is missing, the app should say the claim cannot be verified instead of filling in a scouting phrase.

## Running Locally

```bash
git clone <repo-url>
cd moreymachine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python3 scripts/run_team_pipeline.py --team PHI --skip-refresh
python3 scripts/build_narratives.py --team PHI
streamlit run src/moreymachine/app/streamlit_app.py
```

## Full Local Pipeline

Run from the repository root:

```bash
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

python scripts/validate_all_schemas.py
python scripts/audit_data_lineage.py
python scripts/build_roster_world.py
python scripts/build_contender_blueprints.py
python scripts/build_gap_model.py
python scripts/build_player_skill_profiles.py
python scripts/build_compatibility_matrix.py
python scripts/simulate_roster_slots.py
python scripts/build_acquisition_feasibility.py
python scripts/build_candidate_scenarios.py
python scripts/rank_candidates_v2.py --team PHI
python scripts/build_player_categorization.py
python scripts/build_help_impact.py
python scripts/build_fit_breakdowns.py
python scripts/build_salary_cards.py
python scripts/build_explanations_v2.py
python scripts/build_player_profiles.py
python scripts/build_best_by_need.py
python scripts/export_scouting_reports.py

python scripts/validate_data_contracts.py
python scripts/validate_target_board.py
python scripts/validate_reasoning_v2.py
python scripts/validate_player_profiles.py
python scripts/run_backtest.py
pytest
python -c "import moreymachine; print('import ok')"

streamlit run src/moreymachine/app/streamlit_app.py
```

## Manual Contracts And Candidates

Manual contracts live in `data/manual/contracts.csv`. Manual candidates live in `data/manual/candidates.csv`.

Only enter sourced real values. If a contract, salary, injury, transaction, availability, or status field is missing, leave it missing and explain it with `missing_data_flags` or `source_note`. Do not use placeholder numbers to make the board look complete.

## Interpreting Scores

The score is a product artifact, not advice. It combines need match, skill evidence, compatibility with the core, roster-slot fit, contender-blueprint fit, playoff role, scenario robustness, acquisition feasibility, contract value, risk, uncertainty, and contradiction penalties.

The useful question is not "who has the highest score?" It is "what role is the model actually projecting, what evidence supports that role, and what would make the recommendation wrong?"
