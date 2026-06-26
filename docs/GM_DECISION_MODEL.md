# GM Decision Model

MoreyMachine's GM layer ranks actions, not just players. A strong player can be
a bad action if the role is blocked, the cost is high, the path is unknown, or a
more important gap remains unsolved.

## Executive Summary Contract

The first page must show:

- selected team;
- current level;
- closest build type;
- closest benchmark;
- top gap;
- best route;
- top three actions;
- what not to do;
- manual review queue;
- confidence and why.

The executive summary is built from `team_level`, `team_comparison`,
`gap_model`, `move_recommendations`, `action_cards`, and narrative packets. It
does not use raw player score rank alone.

## Action Ranking Formula

The move score is:

```text
0.25 * gap_priority_impact
+ 0.20 * roster_slot_fit
+ 0.15 * core_compatibility
+ 0.15 * acquisition_feasibility
+ 0.10 * benchmark_impact
+ 0.10 * scenario_robustness
+ 0.05 * confidence
- opportunity_cost_penalty
- contradiction_penalty
- stale_data_penalty
```

No move can be a top recommendation if the underlying player has unknown/stale
status, low feasibility, no clear role, a fatal contradiction, low explanation
confidence, or theoretical/unavailable status.

## Action Categories

Required categories:

- `best_overall_action`
- `best_realistic_free_agent`
- `best_realistic_trade`
- `best_low_cost_depth`
- `best_backup_center_route`
- `best_wing_defense_route`
- `best_shooting_route`
- `best_internal_or_stay_put`
- `top_avoid_move`
- `manual_review_action`

These categories let the app answer route-level questions. The best free agent
may not be the best overall action. The best cheap/depth action may be useful
even when it does not change the team's ceiling.

## Opportunity Cost

Opportunity cost asks what the team gives up by chasing a move:

- salary or exception flexibility;
- trade-resource bucket;
- blocked roster slot;
- cheaper alternatives;
- future flexibility;
- mismatch between the player's role and the team's highest-priority gaps.

For PHI, expensive traditional centers are penalized unless the role is clearly
non-Embiid/matchup value and the acquisition cost is reasonable. High-usage
guards are penalized when Maxey overlap is unresolved.

## Stay-Put / Internal Actions

The product should include internal or stay-put routes when public data does not
support a clean move. A stay-put action is not filler. It should explain which
gap remains, why external options are weak, and what data could change the
answer.
