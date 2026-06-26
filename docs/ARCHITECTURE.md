# MoreyMachine Architecture

This document defines the target architecture for the industry-grade rebuild.
The important change is sequencing: the product must understand the roster world
before it ranks candidates, and it must validate evidence before it makes
basketball claims.

## Layered Flow

```text
raw/cached data
-> entity resolution
-> data lineage
-> team context
-> current Sixers roster world
-> contract/status state
-> contender/championship blueprint
-> team level
-> benchmark comparison
-> Sixers gap model
-> player skill profiles
-> player-to-player compatibility
-> roster slot + minutes simulation
-> acquisition feasibility
-> opportunity cost
-> scenario engine
-> recommendation engine v2
-> move recommendation engine
-> action cards
-> evidence-based explanation engine
-> player profile builder
-> best-by-need engine
-> Ollama/deterministic narrative packets
-> player profile validation
-> Streamlit product UI
```

No downstream layer should silently infer facts that an upstream layer did not
provide. Missing contract, status, transaction, injury, or availability data must
stay missing and travel with the player profile.

## GM Operating System Layer

The product is no longer only a target board. The first page should answer a
front-office strategy question:

> What is this team, what benchmark is it chasing, what needs to change, what
> should the GM do first, and what could make the recommendation wrong?

The team-scoped pipeline writes artifacts under
`data/team_outputs/{TEAM}/`:

- `features/` for derived basketball features;
- `reports/` for decision artifacts used by the UI;
- `narratives/` for deterministic or Ollama-summarized JSON;
- `scouting_reports/` for player memo exports;
- `metadata/` for run state and validation summaries.

The GM operating-system layer consumes the player-profile rebuild but changes
the product object from "highest fit score" to "ranked strategic action."
Candidate rows still exist, but move recommendations and action cards are what
drive the executive summary.

## Team-Scoped Execution

`scripts/run_team_pipeline.py --team PHI` is the preferred end-to-end command
for the Streamlit product. It does not fetch live data inside the app. It reads
cached/global artifacts, builds or copies team-scoped outputs, and marks partial
results when required upstream data is unavailable.

For non-PHI teams, the pipeline may run with generic assumptions until a custom
team context file exists. Generic context must be visible in the app and should
lower confidence where roster-slot assumptions are not team-specific.

## Narrative Layer

Ollama is an optional readability layer, not a data source. Prompts receive
structured JSON packets that already include evidence, confidence, missing data,
and validation flags. If Ollama is disabled or unavailable, deterministic
fallback summaries are written so the app remains usable and factual.

## 1. Data Ingestion

Current inputs:

- `nba_api` / NBA.com stats for team seasons, player seasons, player bio, and
  tracking-style tables.
- Public/manual contract data.
- Manual candidate overrides.
- Recent transaction cache.
- Manual playoff outcomes.

Target responsibility:

- Pull or read source data.
- Keep raw source columns where useful.
- Preserve `source`, `source_url`, `source_note`, `pulled_at`,
  `effective_date`, `data_mode`, and `missing_data_flags`.
- Never call live APIs inside Streamlit page loads.

## 2. Entity Resolution

Entity resolution owns canonical player and team identity.

Responsibilities:

- Normalize player names.
- Resolve `player_id` across NBA stats, contracts, transactions, manual rows,
  and generated artifacts.
- Normalize team abbreviations.
- Detect duplicate player rows.
- Apply source priority rules when multiple sources conflict.

No scoring layer should perform ad hoc name matching.

## 3. Data Lineage

Every generated artifact should have a sidecar metadata file:

```text
same_file_name.metadata.json
```

The metadata should include:

- `artifact_name`
- `created_at`
- `run_id`
- `source_files`
- `source_urls`
- `rows`
- `columns`
- `seasons`
- `data_mode`
- `upstream_artifacts`
- `known_limitations`

This makes the app explain where each number came from and whether a board was
rebuilt from current inputs.

## 4. Current Sixers Roster World

The roster world is the first basketball-context layer. It describes what is
actually true about the target team before any candidate is scored.

Responsibilities:

- Identify core players.
- Identify locked, open, and blocked roster slots.
- Model Embiid, Maxey, George, and current rotation constraints.
- Represent strategic assumptions from `data/manual/team_context/phi.yml`.
- Explain which assumptions are sourced, manual, or uncertain.

Important rule:

> A general NBA starter is not automatically a starter on Philadelphia.

For example, Embiid blocks the normal starting center slot. Traditional centers
should usually be evaluated for backup center, non-Embiid minutes, matchup big,
regular-season depth, or insurance unless a two-big scenario is proven.

## 5. Contract And Status State

Contract/status state should unify contracts, transaction freshness, manual
overrides, and candidate status.

Responsibilities:

- Separate cap hit, base salary, and AAV.
- Preserve missing salary fields instead of estimating them.
- Track transaction freshness.
- Track manual review requirements.
- Feed acquisition feasibility.

Rules:

- Unknown status cannot become a Priority Target.
- Stale status cannot become a Priority Target.
- Free-agent and trade boards must be backed by status-compatible evidence.

## 6. Contender Blueprint

The blueprint layer should build structural reference cohorts, not only average
team stats.

Cohorts include:

- champions
- finalists
- conference finalists
- top-5 net rating teams
- top-10 net rating teams
- star-center-anchor teams
- heliocentric-guard teams
- wing-depth-switchable teams
- balanced-two-way teams
- defense-first teams
- shooting-pressure teams
- depth-heavy teams
- dual-big teams
- creator-committee teams

Each blueprint should explain:

- what the team type usually has;
- which roles are essential;
- which roles are redundant;
- which weaknesses show up in the playoffs;
- how close PHI is to the blueprint;
- what kinds of players move PHI closer.

## 7. Sixers Gap Model

The gap model converts roster world plus blueprint deltas into role-specific
needs.

Each gap should define:

- severity;
- confidence;
- roster slot needed;
- required skill dimensions;
- lineup contexts;
- why it matters;
- playoff failure mode;
- what fixes it;
- what does not fix it;
- evidence and assumptions.

Critical rule:

> A player can only receive Need Match credit for a gap if his skill profile
> permits that claim.

## 8. Player Skill Profiles

Skill profiles convert raw stats and role features into evidence-backed skill
dimensions.

Responsibilities:

- Score shooting, creation, defense, rebounding, portability, sample reliability,
  and role stability.
- Store evidence columns for each claim.
- Set `claim_allowed` booleans.

Example claim gates:

- Spacing requires three-point volume/rate/sample and non-terrible accuracy.
- Rim protection requires size/position plus block, rebounding, or role evidence.
- Defense cannot be claimed from steals alone.
- Creation requires usage, assist/self-creation proxy, and turnover context.

## 9. Compatibility Matrix

Compatibility is candidate-to-current-roster, not generic player quality.

Evaluate each candidate against:

- Joel Embiid
- Tyrese Maxey
- Paul George
- young/current core players where present
- bench and rotation groups

Compatibility should generate positives, negatives, conflict flags, lineup
contexts, evidence, and confidence.

## 10. Roster Slot And Minutes Simulation

The roster simulation decides what role is actually open.

Responsibilities:

- Map each candidate to possible slots.
- Identify blocked slots.
- Decide primary and secondary slots.
- Decide starter, closing, playoff rotation, regular-season-depth, matchup, and
  no-clear-role states.

Rules:

- A center cannot be `starter_possible` unless the simulation proves it.
- A candidate cannot be Priority Target without a clear primary slot.
- General player quality cannot override a blocked role.

## 11. Acquisition Feasibility

This layer is transparent and approximate. It should not pretend to be a full
CBA engine.

Responsibilities:

- Assign acquisition path.
- Score feasibility.
- Explain salary matching complexity and uncertainty.
- Flag manual review.

Low feasibility can appear on a board, but the recommendation must be explicit
about acquisition reality.

## 12. Scenario Engine

Every candidate should have scenarios:

- best case;
- realistic case;
- conservative/downside case;
- playoff case;
- regular-season-only case;
- overpay case;
- missing-data case;
- bad-fit case.

Recommendations should be scenario-aware. A useful backup center is not the same
thing as a starter. A cheap flier is not the same thing as a clean solution.

## 13. Recommendation Engine V2

The recommendation engine consumes all previous layers.

Inputs:

- candidate universe;
- roster world;
- contender blueprints;
- gap model;
- skill profiles;
- compatibility matrix;
- roster simulation;
- acquisition feasibility;
- scenarios;
- contracts/status;
- validation flags.

Outputs:

- v2 rankings;
- split boards;
- score components;
- scenario labels;
- contradiction flags;
- confidence;
- source summary.

## 14. Evidence-Based Explanation Engine

Explanations are generated from structured evidence objects.

No claim should be emitted unless the evidence rules allow it.

Examples:

- "spaces the floor" requires shooting evidence;
- "rim protection" requires rim-protection evidence;
- "starter" requires an open/simulated starter slot;
- "Priority Target" requires scenario robustness, feasibility, and no fatal
  contradiction.

If evidence is missing, the explanation must say the claim cannot be verified.

## 15. Player Profiles

The player profile is the product's central artifact.

Each board row must link to a profile. The profile should contain identity,
scores, role, fit with core, salary/acquisition, scenarios, help areas, concerns,
evidence, missing data, and why the model could be wrong.

Profiles are generated from structured artifacts, not by parsing final CSV text.

## 16. Validation

Validation should fail on unsupported claims and product contradictions.

Examples:

- unsupported spacing claim;
- unsupported defense claim;
- unsupported starter claim;
- center-starter conflict with Embiid;
- Priority Target without scenario robustness;
- low-feasibility Priority Target;
- no-clear-role player with high recommendation;
- profile missing salary card or help areas;
- board row without profile ID.

## 17. Streamlit Product UI

The app becomes player-profile-first.

Primary workflows:

- read the product summary and data freshness;
- inspect the current Sixers roster world;
- explore contender blueprints and gaps;
- search/click any player;
- inspect full player profile;
- compare players side by side;
- rank players by specific need;
- inspect validation and reasoning diagnostics.

The app reads cached artifacts only. If an artifact is missing, it shows the
exact script needed to rebuild it.
