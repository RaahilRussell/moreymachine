# Reasoning System

MoreyMachine should not generate persuasive basketball text first and then hope
the numbers support it. The reasoning system works in the opposite direction:
structured evidence first, claims second, recommendations last.

## Recommendation Formation

The v2 recommendation engine should form an opinion in this order:

1. Resolve candidate identity.
2. Check data status and missing fields.
3. Build the current PHI roster world.
4. Identify relevant Sixers gaps.
5. Build the player's skill profile.
6. Check whether the skill profile permits gap claims.
7. Evaluate compatibility with Embiid, Maxey, George, and roster groups.
8. Simulate available roster slots and minutes contexts.
9. Evaluate acquisition path and feasibility.
10. Generate scenarios.
11. Score the player under those scenarios.
12. Apply contradiction penalties.
13. Assign recommendation and confidence.
14. Generate explanations from evidence objects.
15. Validate the profile and board row.

The GM operating-system layer then forms a strategic action:

1. Classify the selected team's current level.
2. Compare the team to contender benchmarks.
3. Rank gaps by severity, playoff importance, and fixability.
4. Compute player-level opportunity cost.
5. Convert candidate recommendations into move recommendations.
6. Rank actions by gap priority, roster-slot fit, compatibility, feasibility,
   benchmark impact, scenario robustness, confidence, and opportunity cost.
7. Render action cards before raw tables.

The product should not open by asking "who has the highest fit score?" It should
open by asking "what does this team need to do next, why, and what could be
wrong?"

## Allowed Claims

Every visible explanation claim must have a type, evidence, and confidence.

| Claim | Required evidence |
| --- | --- |
| `spaces the floor` | three-point volume, three-point rate, sample, and non-terrible accuracy |
| `movement shooter` | movement shooting proxy or catch-and-shoot volume plus role support |
| `rim protection` | size/position plus blocks, block rate, rim-protection proxy, or role evidence |
| `defense` | defensive proxy evidence beyond steals alone |
| `rebounding` | rebound percentage/score plus minutes/sample context |
| `creation` | usage, assist/self-creation proxy, and turnover context |
| `connector` | assist/turnover, low-usage fit, and role evidence |
| `starter` | roster simulation says `starter_possible = true` and slot is not blocked |
| `playoff rotation` | playoff scenario support and no fatal role contradiction |
| `Priority Target` | clear slot, scenario robustness, feasibility, status freshness, and no fatal contradiction |

## Disallowed Claim Patterns

The explanation engine must refuse:

- generic spacing claims for low-volume or inefficient shooters;
- generic defense claims from a role label alone;
- rim-protection claims for guards or low-block bigs without evidence;
- starter language for centers blocked by Embiid unless a two-big scenario is
  proven;
- Priority Target recommendations for stale, unknown, no-clear-role, or
  low-feasibility candidates;
- "No major concerns" filler;
- duplicate concern phrases;
- repeated templates that are not evidence-specific.

## Contradictions

Contradictions should be structured flags, not buried in prose.

Blocking contradictions:

- no clear roster slot;
- blocked starter slot;
- stale or unknown candidate status;
- missing contract status for a recommendation requiring salary certainty;
- theoretical-only acquisition path on a realistic board;
- unsupported primary claim;
- no scenario assigned before recommendation.

Non-blocking contradictions:

- useful role but high price;
- strong fit but difficult acquisition;
- good regular-season fit but weak playoff scenario;
- helps one gap while worsening another;
- high talent but redundant with core.

## Uncertainty Handling

Uncertainty affects both score and confidence.

Rules:

- Missing stays missing.
- Unknown status triggers manual review.
- Missing salary reduces contract confidence.
- Missing defensive evidence blocks defensive claims.
- Missing shooting evidence blocks spacing claims.
- High missing-data load prevents `High` explanation confidence.

## EvidenceObject Contract

Each evidence object should include:

- `claim`
- `evidence_type`
- `supporting_columns`
- `supporting_values`
- `source`
- `confidence`
- `missing_data_flags`

The app can show the evidence table directly in the player profile.

## Why The Model Could Be Wrong

Every player profile needs a section explaining failure modes:

- data may be stale;
- public data may miss injury or availability context;
- role may not translate to playoff matchups;
- acquisition cost may be higher than modeled;
- another team may not be willing to trade;
- salary/exception rules may be more restrictive than the approximation;
- a player may fit statistically but fail in actual lineup execution.

## Confidence

Recommendation confidence is not the same as fit score.

Confidence should reflect:

- completeness of data;
- freshness of status;
- strength of evidence;
- role-slot clarity;
- scenario robustness;
- acquisition feasibility;
- contradiction flags.

## Validation Philosophy

Validation should make false confidence difficult.

The product should fail validation if it:

- recommends before simulating role;
- explains before generating evidence;
- claims a gap before skill permission;
- omits salary/source/provenance;
- omits player profile links;
- hides uncertainty in generic language.

## Move Recommendation Rules

A move recommendation can only appear if it has:

- a player or stay-put/internal action object;
- a route (`free_agent_pickup`, `trade_target`, `stay_put`, `avoid_move`, etc.);
- at least one roster gap or strategic reason;
- an acquisition/feasibility context;
- an opportunity-cost estimate;
- a scenario;
- `why_do_this`;
- `why_not_do_this`;
- `what_could_go_wrong`;
- evidence and confidence.

Priority language is stricter for moves than for players. A move cannot be a
top action when the underlying player is stale/unknown, low-feasibility,
theoretical-only, blocked by roster-slot logic, or missing a scenario.

## Ollama Boundary

Ollama may turn a structured packet into readable prose. It may not create new
facts, player labels, salary claims, trade claims, injury claims, or basketball
evidence. Every prompt must say:

> You are summarizing structured basketball ops data. Use only the JSON. Do not
> invent facts. If evidence is missing, say it is missing.

If Ollama is disabled, unavailable, times out, or returns unusable text, the
deterministic fallback summary is the product output.
