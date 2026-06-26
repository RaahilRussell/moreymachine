# Industry Rebuild Audit

Generated from the current MoreyMachine artifacts before the industry-grade
reasoning rebuild.

Baseline commit: `38e5979 make docs clone-friendly`

## Current Pipeline Shape

Current conceptual flow:

```text
cached NBA/contract/transaction data
-> candidate universe
-> player roles/archetypes
-> roster gaps
-> score_candidates
-> target_board explanations
-> Streamlit pages
```

This is a useful analytics pipeline, but it is not yet a front-office reasoning
product. The current board ranks candidates before it has built a full Sixers
roster world, simulated roster slots, checked core compatibility, or generated
scenario-specific recommendations.

## Audit Counts

| Failure pattern | Count |
| --- | ---: |
| Center/big rows described as starter-type fits despite Embiid context | 24 |
| Rows with `No major rule-based concerns` language | 137 |
| Rows with duplicate concern phrases | 119 |
| Repeated `role_on_sixers` templates used more than five times | 29 |
| Priority Targets with acquisition feasibility below 50 | 8 |
| Rows with transaction/status conflicts requiring manual review | 15 |

## Product Failure Examples

### Nikola Vucevic / Vučević

**Current output**

- `recommendation`: `Strong Fit If Affordable`
- `candidate_type`: `likely_free_agent`
- `role_on_sixers`: `Projected Starter as a Rim Protector; spaces the floor for Embiid post-ups and Maxey drives; helps the glass.`
- `why_fit`: `Answers top PHI gaps: shooting pressure, playoff portability proxy, rebounding, role player shooting.; elite playoff portability; a bargain on salary; projects to starter minutes.`
- `concerns`: `No major rule-based concerns.`

**Why it is wrong**

The explanation treats a center role label as a Sixers starter projection even
though Joel Embiid blocks the normal starting center slot. It also claims floor
spacing from a player whose current board evidence does not separately gate
volume, accuracy, lineup context, and Embiid compatibility. The current system is
using general player quality and role labels before it understands the roster
slot.

**What a smarter product should say**

Vučević should be evaluated as non-Embiid center minutes, backup center,
matchup big, regular-season center insurance, or expensive depth. He should not
be described as a starter next to Embiid unless a two-big scenario passes
specific shooting, defensive mobility, lineup, and acquisition-cost tests.

**Missing infrastructure**

- Current Sixers roster world
- Embiid-specific slot constraints
- Player-to-core compatibility
- Roster-slot and minutes simulation
- Scenario engine
- Evidence-gated spacing and starter claims
- Contradiction validation

### Sandro Mamukelashvili

**Current output**

- `recommendation`: `Priority Target`
- `candidate_type`: `rookie_scale_trade_target`
- `acquisition_feasibility`: `49.4`
- `role_on_sixers`: `Projected Starter as a Stretch Big; spaces the floor for Embiid post-ups and Maxey drives; adds the perimeter/rim defense PHI lacks; helps the glass.`
- `concerns`: `No major rule-based concerns.`

**Why it is wrong**

The current product lets a low-feasibility trade candidate become a Priority
Target and calls him a starter without proving an open slot. It also bundles
spacing, defense, and rebounding into one generic sentence rather than showing
which claims are actually supported.

**What a smarter product should say**

The profile should first decide whether the useful role is backup/stretch big,
double-big partner, matchup big, stretch-forward option, or no clear playoff
role. If he is difficult to acquire, the recommendation should explain the
opportunity cost instead of letting the fit score override feasibility.

**Missing infrastructure**

- Acquisition feasibility layer that affects tiering
- Scenario robustness score
- Roster slot simulation
- Evidence object per claim
- Priority-target contradiction gates

### Tim Hardaway Jr.

**Current output**

- `recommendation`: `Priority Target`
- `candidate_type`: `minimum_candidate`
- `role_on_sixers`: `Projected Starter as a Movement Shooter; spaces the floor for Embiid post-ups and Maxey drives.`
- `concerns`: `weak defensive proxies; weak defensive proxies`

**Why it is wrong**

The board correctly identifies a possible shooting use case, but it projects a
starter role before checking the current PHI wing/guard slots, lineup defense,
and playoff role. It also repeats the same concern phrase.

**What a smarter product should say**

He should be evaluated as a low-cost shooting/regular-season-depth scenario
unless the roster simulation finds a real playoff rotation slot. The defensive
concern should be deduplicated and tied to evidence.

**Missing infrastructure**

- Role-slot availability
- Playoff rotation scenario
- Deduplicated evidence-based concerns
- Help-impact engine distinguishing shooting help from defensive limitations

### Donte DiVincenzo

**Current output**

- `recommendation`: `Priority Target`
- `role_on_sixers`: `Projected Starter as a Secondary Creator; spaces the floor for Embiid post-ups and Maxey drives.`
- Current shooting evidence in artifact: `three_p_pct = 0.265`

**Why it is wrong**

The current explanation can use spacing language even when the available
accuracy evidence is weak. It does not separate shooting volume from successful
spacing gravity.

**What a smarter product should say**

The model can say he offers movement/volume shooting if volume evidence passes,
but it should also flag current efficiency risk and avoid an unqualified
`spaces the floor` claim unless both volume and accuracy gates pass.

**Missing infrastructure**

- Skill profile dimensions with `claim_allowed`
- Spacing claim gate using 3PA volume, rate, sample, and accuracy
- Explanation engine that refuses unsupported claims

### Onyeka Okongwu

**Current output**

- `candidate_type`: `core_unavailable`
- `role_on_sixers`: `Projected Starter as a Stretch Big; spaces the floor for Embiid post-ups and Maxey drives; adds the perimeter/rim defense PHI lacks; helps the glass.`
- Current shooting evidence in artifact: `three_pa = 3`, `three_p_pct = 0.000`

**Why it is wrong**

The explanation claims stretch/spacing value without supported shooting volume
or accuracy. It also uses starter language for a core/unavailable player and
does not clearly separate theoretical basketball fit from acquisition reality.

**What a smarter product should say**

He may be an unavailable/theoretical frontcourt fit whose best supported claims
are defense, rebounding, or non-Embiid big minutes, if the evidence passes. The
product should not call him a spacer.

**Missing infrastructure**

- Theoretical-only acquisition path
- Evidence-gated shooting claims
- Watchlist-specific recommendation language
- Claim-to-evidence validation

### Keldon Johnson / Defensive Wing Claim

**Current output**

- `role_on_sixers`: `Projected Starter as a Defensive Wing; helps the glass.`
- Defensive proxies in artifact: `wing_defense_proxy = 30.6`, `point_of_attack_defense_proxy = 35.2`, `rim_protection_proxy = 23.5`

**Why it is wrong**

The role label can call someone a defensive wing even when the defensive proxy
evidence is weak. The current system does not validate the claim against the
underlying defensive dimensions.

**What a smarter product should say**

The product should say the defensive-wing claim is not verified by current
proxies and should either classify him differently or flag defense as uncertain.

**Missing infrastructure**

- Defensive claim gate
- Role classification confidence tied to evidence
- Explanation validation for unsupported defense language

### Reed Sheppard / Rim Defense Claim

**Current output**

- `recommendation`: `Priority Target`
- `role_on_sixers`: `Projected High-Level Starter as a Primary Creator; spaces the floor for Embiid post-ups and Maxey drives; adds the perimeter/rim defense PHI lacks.`
- `rim_protection_proxy = 38.6`

**Why it is wrong**

A guard can be a useful target without being credited for rim defense. The
current gap-to-role text collapses perimeter defense and rim defense into one
claim and can attach it to players whose rim-protection evidence is weak.

**What a smarter product should say**

The product should separate point-of-attack defense, wing defense, and rim
protection. If he helps any defensive gap, it must identify which one and show
the supporting evidence.

**Missing infrastructure**

- More granular Sixers gap model
- Skill-specific gap permissions
- Rim-protection claim gate
- Help-impact engine with `does_not_help`

## Systemic Current-State Problems

### General player role is being treated as Sixers role

`expected_role` comes from general role/impact logic. It is not the same as
`expected_role_on_phi`. The current board can call a candidate a starter because
he profiles as a starter in general, even when Philadelphia has no open slot.

### Core context is shallow

Current explanations mention Embiid and Maxey by template, but do not compute
candidate fit with Embiid, Maxey, George, current bench units, or actual lineup
contexts.

### Gap claims are not permissioned by skill evidence

The board can say a player helps spacing, defense, rim protection, or rebounding
without a claim-specific evidence object. This creates plausible but false
basketball explanations.

### Acquisition feasibility is secondary to fit score

Eight current Priority Targets have acquisition feasibility below 50. A real
front-office product can show low-feasibility players, but should not let them
be clean Priority Targets without scenario and opportunity-cost justification.

### Explanations are too template-driven

The current board contains 29 repeated `role_on_sixers` templates used more than
five times, 137 `No major rule-based concerns` rows, and 119 rows with duplicate
concern phrases. This is a sign that the product is generating text before it
has enough structured reasoning.

### Streamlit app can crash on schema mismatch

While stopping the app from the previous run, the Sixers diagnosis page crashed
with:

```text
KeyError: 'comparison_group_label'
```

The page expected a gap column that the generated artifact does not contain.
This is a product contract failure between the artifact layer and UI layer.

## What The Industry Rebuild Must Add

The next architecture needs to move in this order:

```text
raw/cached data
-> entity resolution
-> data lineage
-> current Sixers roster world
-> contract/status state
-> contender/championship blueprint
-> Sixers gap model
-> player skill profiles
-> player-to-player compatibility
-> roster slot + minutes simulation
-> acquisition feasibility
-> scenario engine
-> recommendation engine v2
-> evidence-based explanation engine
-> player profile builder
-> player profile validation
-> Streamlit product UI
```

Specific missing layers:

- typed schemas and artifact validation contracts;
- canonical entity resolution and duplicate detection;
- artifact lineage sidecars;
- `RosterWorld` for PHI with locked/open/blocked slots;
- structural contender blueprint engine;
- gap model where each gap declares required skills;
- player skill profiles with evidence and `claim_allowed`;
- compatibility matrix against Embiid, Maxey, George, and bench groups;
- roster slot/minutes simulation;
- acquisition path and contract feasibility layer;
- scenario engine for best/realistic/downside/playoff/overpay cases;
- scenario-aware recommendation engine;
- explanation engine that generates claims only from structured evidence;
- player profiles as first-class artifacts;
- reasoning validation that fails unsupported basketball claims;
- Streamlit UI centered on searchable player profiles and comparisons.

