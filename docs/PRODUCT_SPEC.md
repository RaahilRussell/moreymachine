# Product Spec

MoreyMachine should feel like an internal basketball-operations product, not a
CSV viewer. The main object is a strategic action backed by player profiles,
scenario logic, salary context, evidence, and validation.

## Product Goals

The product should let a user:

1. Select a team.
2. See the team's current level.
3. See the closest contender benchmark and archetype.
4. See what the team needs to become a real contender.
5. See ranked strategic actions.
6. See free-agent, trade, internal, cheap-depth, and stay-put routes.
7. Click or search any player or move.
8. Open a full player profile or strategy memo.
9. See fit score and why.
10. See what the player helps most.
11. See what the player does not solve.
12. See the actual projected role on the selected roster.
13. See whether that role is open, blocked, or scenario-dependent.
14. See fit with Embiid, Maxey, George, and the current roster for PHI.
15. See salary, contract, acquisition path, feasibility, and uncertainty.
16. See best-case, realistic-case, downside-case, playoff-case, and overpay-case
    scenarios.
17. See evidence behind every claim.
18. See missing or stale data.
19. See why the model could be wrong.
20. Compare players and moves side by side.
21. Rank players by need, not just total fit score.

## Page Order

### 1. GM Executive Summary

Shows selected team, current level, closest build type, closest benchmark, top
gap, best route, top three actions, what not to do, manual review items, and
confidence. This page is summary-first and uses action cards, not a dataframe.

### 2. Product Summary

Explains what MoreyMachine does, what refreshable real data means, and what the
model can and cannot claim.

### 3. Team Selector / Analyze Any Team

Shows team context mode, available artifacts, generic-context warnings, and the
exact command to run missing analysis outputs.

### 4. Data Sources / Freshness

Shows team-scoped and global artifacts, sources, pulled-at timestamps, run IDs,
missing fields, stale status warnings, and refresh commands.

### 5. Current Team Roster World

Shows core players, locked slots, open slots, blocked slots, constraints,
current player roles, and assumptions.

### 6. Team Level

Shows level score, classification, strengths, weaknesses, confidence, and what
the next level requires.

### 7. Contender Blueprint Explorer

Shows champions, finalists, conference finalists, top-net-rating teams, and
construction archetypes. Includes selected-team comparison and what kinds of
players move the team closer to each blueprint.

### 8. Benchmark Path

Compares the selected team to champion average, finalist average, conference
finalist average, top-net-rating cohorts, Boston-style, Denver-style,
OKC-style, and a selected custom benchmark.

### 9. Gap Priority Model

Gap cards include severity, evidence, what fixes it, what does not fix it,
playoff failure mode, and required skills.

### 10. Move Recommendations

Shows ranked action cards first, then a filterable table. Includes best
overall, best free agent, best trade, best cheap/depth route, stay-put/internal,
avoid, and manual-review actions.

### 11. Target Board V2

Segmented tabs:

- Priority Targets
- Strong Fits If Affordable
- Role-Player Targets
- Only If Cheap
- Avoid
- Free Agents
- Trade Targets
- Minimum/MLE Candidates
- Backup Center Options
- Wing Defense Options
- Shooting Options
- Bench Creation Options
- Regular-Season Depth
- Unrealistic Watchlist
- Manual Review Needed

Every tab explains what it means, shows top player cards, offers filters, and
links rows to player profiles. Empty segments show a clean empty state.

### 12. Player Detail V2

Every player must be searchable/selectable.

Sections:

- Header
- Score Overview
- What He Helps Most
- What He Does Not Solve
- Role on Team
- Fit With Core
- Salary + Acquisition
- Scenarios
- Evidence Table
- Concerns
- Recommendation Interpretation

### 13. Player Compare

Compare 2-4 players across fit score, salary, acquisition path, top help areas,
compatibility, risk, role slot, scenarios, recommendation, and concerns.

### 14. Move Compare

Compare selected moves by route, feasibility, need addressed, expected role,
opportunity cost, scenario, confidence, and risk.

### 15. Best By Need

Click a need and see ranked players for backup center, wing defense, shooting,
bench creation, point-of-attack defense, rebounding, size, regular-season depth,
playoff rotation piece, stretch forward, and matchup big.

### 16. Player Skill Profiles

Searchable player skill view showing skill dimensions, evidence stats,
confidence, missing fields, and claim gates.

### 17. Player-to-Player Compatibility

Candidate versus Embiid, Maxey, George, bench/current roster groups. Shows
positives, negatives, evidence, and conflict flags.

### 18. Roster Slot Simulation

Shows candidate slots, blocked slots, starter/closing/playoff flags, lineup
contexts, and role conflicts.

### 19. Candidate Scenarios

Shows best case, realistic case, downside, playoff, regular season, overpay, and
missing-data scenarios.

### 20. Transaction Review

Shows status-freshness issues, recent transactions after salary pull dates,
candidate type conflicts, and rows requiring manual review.

### 21. Manual Review Queue

Shows stale status, missing contracts, low confidence, contradiction flags, and
blocked unsupported claims.

### 22. Reasoning Diagnostics

Shows validation gates, contradiction warnings, generic-template detection,
unsupported-claim detection, and players needing manual review.

### 23. Backtest Proof

Explains what the backtest supports and what it does not support. It should not
claim the model predicts front-office truth.

### 24. Limitations / Missing Data

Shows honest limitations around transaction freshness, injury/status limits,
contract availability, true trade availability, private team intent, and
backtest status limitations.

## UI Standard

- Sidebar owns team, benchmark, quick player search, and artifact status.
- Top of every page is summary cards.
- Recommendation cards appear before dataframes.
- Evidence lives in expanders or tables below the summary.
- Empty states explain the missing artifact and show the exact command to run.
- Every repeated widget has a stable key.
- The app never fetches NBA data inside a page load.

## Player Profile Requirements

Each profile must include identity, fit score, recommendation, confidence,
manual review flag, contradiction flags, role and roster slot, fit with core,
salary/acquisition card, skill summaries, scenarios, evidence, top help areas,
does-not-help, and why the model could be wrong.
