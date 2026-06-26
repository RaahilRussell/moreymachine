# Product Spec

The rebuilt app should feel like an internal roster-decision product, not a CSV
viewer. The main object is a player profile. Boards are entry points into those
profiles.

## Product Goals

The product should let a user:

1. See a target board.
2. Click or search any player.
3. Open a full player profile.
4. See fit score and why.
5. See what the player helps most.
6. See what the player does not solve.
7. See the actual projected role on the Sixers.
8. See whether that role is open, blocked, or scenario-dependent.
9. See fit with Embiid, Maxey, George, and the current roster.
10. See salary, contract, acquisition path, feasibility, and uncertainty.
11. See best-case, realistic-case, downside-case, playoff-case, and overpay-case
    scenarios.
12. See evidence behind every claim.
13. See missing or stale data.
14. See why the model could be wrong.
15. Compare players side by side.
16. Rank players by need, not just total fit score.

## Pages

### 1. Product Summary

Explains what MoreyMachine does, what "refreshable real data" means, and what
the model can and cannot claim.

### 2. Data Sources / Freshness

Shows:

- artifacts;
- sources;
- pulled-at timestamps;
- run IDs;
- missing fields;
- stale status warnings;
- refresh commands.

### 3. Current Sixers Roster World

Shows:

- core players;
- locked slots;
- open slots;
- blocked slots;
- constraints;
- current player roles;
- assumptions.

### 4. Contender Blueprint Explorer

Shows champions, finalists, conference finalists, top-net-rating teams, and
construction archetypes. Includes PHI comparison and what kinds of players move
PHI closer to each blueprint.

### 5. Sixers Gap Model

Gap cards include:

- severity;
- evidence;
- what fixes it;
- what does not fix it;
- playoff failure mode;
- required skills.

### 6. Player Skill Profiles

Searchable player skill view showing skill dimensions, evidence stats,
confidence, missing fields, and `claim_allowed` booleans.

### 7. Player-to-Player Compatibility

Candidate versus:

- Embiid;
- Maxey;
- George;
- bench/current roster groups.

Shows positives, negatives, evidence, and conflict flags.

### 8. Roster Slot Simulation

Shows candidate slots, blocked slots, starter/closing/playoff flags, lineup
contexts, and role conflicts.

### 9. Candidate Scenarios

Shows:

- best case;
- realistic case;
- downside;
- playoff;
- regular season;
- overpay;
- missing data.

### 10. Target Board V2

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

Every tab explains what it means and links each row to a player profile.

### 11. Player Detail V2

Every player must be searchable/selectable.

Sections:

- Header
- Score Overview
- What He Helps Most
- What He Does Not Solve
- Role on Sixers
- Fit With Core
- Salary + Acquisition
- Scenarios
- Evidence Table
- Concerns
- Recommendation Interpretation

### 12. Player Compare

Compare 2-4 players across:

- fit score;
- salary;
- acquisition path;
- top help areas;
- compatibility;
- risk;
- role slot;
- scenarios;
- recommendation;
- concerns.

### 13. Best By Need

Click a need and see ranked players:

- backup center;
- wing defense;
- shooting;
- bench creation;
- point-of-attack defense;
- rebounding;
- size;
- regular-season depth;
- playoff rotation piece;
- stretch forward;
- matchup big.

### 14. Reasoning Diagnostics

Shows:

- validation gates;
- contradiction warnings;
- generic-template detection;
- unsupported-claim detection;
- players needing manual review.

### 15. Backtest Proof

Explains what the backtest supports and what it does not support. It should not
claim the model predicts front-office truth.

### 16. Limitations / Missing Data

Honest limitations:

- transaction freshness;
- injury/status limits;
- contract availability;
- true trade availability;
- private team intent;
- backtest status limitations.

## Player Profile Requirements

Each profile must include:

- identity;
- fit score;
- recommendation;
- confidence;
- manual review flag;
- contradiction flags;
- role and roster slot;
- fit with core;
- salary/acquisition card;
- skill summaries;
- scenarios;
- help areas;
- does-not-help areas;
- evidence objects;
- missing data;
- why this could be wrong.

## UI Rules

- No player row without `player_profile_id`.
- No recommendation without scenario.
- No starter label unless `starter_possible` is true.
- No unsupported claim language.
- Manual-review candidates should be visibly flagged.
- Missing data should be displayed close to the claim it affects.
- Boards should be filterable but profiles should be the primary decision view.

