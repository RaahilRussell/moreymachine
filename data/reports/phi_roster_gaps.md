# PHI Roster Diagnosis (2025-26)

_Built 2026-06-25. Statistical gaps from real team fingerprints vs contenders; composition gaps from the real PHI role engine vs documented contender roster-construction targets._

19 gaps, ranked by severity.

## Shooting Pressure - Critical (severity 46.5)
- PHI: 0.342 | contender target/avg: 0.677 | kind: statistical
- **What it means:** Shooting Pressure trails top-5 net rating teams by 0.335; target is in the 13th percentile using estimated_shooting_pressure for spacing, efficiency, three-point volume, and rim-pressure signals.
- **Why it matters in the playoffs:** Playoff defenses load up on stars; without floor-spacing pressure the paint clogs and star efficiency collapses.
- **What fixes it:** a high-volume movement/catch-and-shoot shooter
- Stats: estimated_shooting_pressure. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Defense - Critical (severity 42.1)
- PHI: 114.4 | contender target/avg: 107.664 | kind: statistical
- **What it means:** Defense trails top-5 net rating teams by 6.736; target is in the 48th percentile using defensive_rating for points allowed per 100 possessions.
- **Why it matters in the playoffs:** Series are won on stops in the half court; a weak defense gets hunted in late-game possessions.
- **What fixes it:** a switchable wing stopper or rim-protecting anchor
- Stats: defensive_rating. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Playoff Portability Proxy - Significant (severity 33.9)
- PHI: 0.6 | contender target/avg: 0.857 | kind: statistical
- **What it means:** Playoff Portability Proxy trails top-5 net rating teams by 0.257; target is in the 53th percentile using estimated_two_way_balance for two-way balance and possession resilience.
- **Why it matters in the playoffs:** Two-way, low-variance contributors hold up when series tighten and matchups get targeted.
- **What fixes it:** a low-usage, two-way role player who fits any lineup
- Stats: estimated_two_way_balance. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Rebounding - Significant (severity 21.0)
- PHI: 0.492 | contender target/avg: 0.504 | kind: statistical
- **What it means:** Rebounding trails top-5 net rating teams by 0.012; target is in the 33th percentile using offensive_rebounding_percentage, defensive_rebounding_percentage for combined offensive and defensive rebounding strength.
- **Why it matters in the playoffs:** Second-chance points swing tight playoff games and compound over a seven-game series.
- **What fixes it:** a rebounding big or crash-the-glass forward
- Stats: offensive_rebounding_percentage, defensive_rebounding_percentage. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Role-Player Shooting - Moderate (severity 11.5)
- PHI: 0.37 | contender target/avg: 0.385 | kind: statistical
- **What it means:** Role-Player Shooting trails same archetype successful teams by 0.015; target is in the 27th percentile using three_point_percentage, three_point_attempt_rate for role-player shooting when available, with team shooting as fallback.
- **Why it matters in the playoffs:** Role-player shooting is the first thing playoff scouting tests; non-shooters get ignored and turn the floor 4-on-5.
- **What fixes it:** a low-usage 3-and-D wing who spaces the floor
- Stats: three_point_percentage, three_point_attempt_rate. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Real spacing (not fake spacing) - Minor (severity 7.6)
- PHI: 45.14 | contender target/avg: 55.0 | kind: composition
- **What it means:** Rotation spacing on real 3-point volume, discounting low-volume shooters.
- **Why it matters in the playoffs:** Defenses ignore non-shooters in the playoffs, turning the floor 4-on-5; real spacing keeps help defenders honest.
- **What fixes it:** shooters with real 3-point volume, not just a respectable percentage
- Stats: spacing_score (rotation mean). Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Playoff-playable size - Strength (severity 0.0)
- PHI: 79.0 | contender target/avg: 79.0 | kind: composition
- **What it means:** Average height (inches) of the projected playoff rotation.
- **Why it matters in the playoffs:** Playoff series punish small lineups on the glass and at the rim; baseline size keeps lineups viable.
- **What fixes it:** size on the wing or in the frontcourt without sacrificing skill
- Stats: height_inches (rotation mean). Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Bench shot creation - Strength (severity 0.0)
- PHI: 66.0 | contender target/avg: 55.0 | kind: composition
- **What it means:** The best secondary shot-creator outside the top two creators.
- **Why it matters in the playoffs:** When the starters rest or a star is contained, bench units need someone who can generate a good shot.
- **What fixes it:** a secondary creator who can run a bench unit
- Stats: secondary_creation_score (3rd best). Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Offensive rebounding - Strength (severity 0.0)
- PHI: 93.8 | contender target/avg: 50.0 | kind: composition
- **What it means:** The best offensive rebounder on the roster.
- **Why it matters in the playoffs:** Extra possessions are scarce against a set playoff defense; crashing the glass manufactures easy points.
- **What fixes it:** an energy big or forward who crashes the offensive glass
- Stats: offensive_rebounding_score. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Defensive rebounding - Strength (severity 0.0)
- PHI: 94.6 | contender target/avg: 55.0 | kind: composition
- **What it means:** The best defensive rebounder on the roster.
- **Why it matters in the playoffs:** Closing possessions on the defensive glass denies second-chance points that swing tight playoff games.
- **What fixes it:** a forward or big who secures the defensive glass
- Stats: defensive_rebounding_score. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Low-usage connector passing - Strength (severity 0.0)
- PHI: 93.8 | contender target/avg: 60.0 | kind: composition
- **What it means:** The best low-usage connector passer on the roster.
- **Why it matters in the playoffs:** When stars are blitzed, someone has to make the next read; connectors keep the offense flowing 4-on-3.
- **What fixes it:** a low-usage connector guard or forward who moves the ball
- Stats: connector_score. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Wing defensive depth - Strength (severity 0.0)
- PHI: 6.0 | contender target/avg: 3.0 | kind: composition
- **What it means:** Count of rotation wings with a plus wing-defense proxy.
- **Why it matters in the playoffs:** Playoff offenses hunt weak perimeter defenders; you need multiple switchable wing stoppers to throw at opposing scorers.
- **What fixes it:** switchable wing defenders who can guard 2-4
- Stats: wing_defense_proxy >= 58. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Role-player shooting volume - Strength (severity 0.0)
- PHI: 4.0 | contender target/avg: 4.0 | kind: composition
- **What it means:** Count of rotation players who are real catch-and-shoot threats.
- **Why it matters in the playoffs:** Stars get doubled in the playoffs; you need four floor-spacers around them or the paint clogs and efficiency collapses.
- **What fixes it:** high-volume catch-and-shoot wings and bigs
- Stats: catch_and_shoot_score >= 60. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Point-of-attack defense - Strength (severity 0.0)
- PHI: 76.6 | contender target/avg: 65.0 | kind: composition
- **What it means:** The best on-ball perimeter defender on the roster.
- **Why it matters in the playoffs:** Containing the primary ball-handler without help keeps the defense intact; without it, playoff guards get downhill at will.
- **What fixes it:** a point-of-attack guard who pressures the ball
- Stats: point_of_attack_defense_proxy. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Pace/Transition - Strength (severity 0.0)
- PHI: 100.39 | contender target/avg: 98.722 | kind: statistical
- **What it means:** Pace/Transition exceeds conference finals or better by 1.668; target is in the 53th percentile using pace for pace as a transition pressure proxy.
- **Why it matters in the playoffs:** Easy transition points are scarce in the playoffs; teams that cannot generate them must grind in the half court.
- **What fixes it:** an athletic transition finisher and outlet runner
- Stats: pace. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Backup center stability - Strength (severity 0.0)
- PHI: 81.6 | contender target/avg: 52.0 | kind: composition
- **What it means:** The second-best rim-protecting big on the roster.
- **Why it matters in the playoffs:** Playoff rotations need a trustworthy backup five to survive non-Embiid minutes without bleeding points in the paint.
- **What fixes it:** a reliable backup center who rebounds and protects the rim
- Stats: rim_protection_proxy (2nd best). Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Non-Embiid rim protection - Strength (severity 0.0)
- PHI: 81.6 | contender target/avg: 60.0 | kind: composition
- **What it means:** The best rim protector on the roster other than Embiid.
- **Why it matters in the playoffs:** Embiid misses playoff games and minutes; without a second rim deterrent the paint collapses when he sits or is in foul trouble.
- **What fixes it:** a switchable or drop-coverage backup center with real rim protection
- Stats: rim_protection_proxy (blocks/36, rim FG% defended, height). Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.

## Turnover Control - Strength (severity 0.0)
- PHI: 0.134 | contender target/avg: 0.139 | kind: statistical
- **What it means:** Turnover Control exceeds conference finals or better by 0.005; target is in the 83th percentile using turnover_percentage for turnover avoidance.
- **Why it matters in the playoffs:** Half-court playoff offense magnifies turnovers into transition points against.
- **What fixes it:** a secure connector guard with a low turnover profile
- Stats: turnover_percentage. Sources: team_fingerprints (real nba_api) vs contender baselines.

## Lineup versatility - Strength (severity 0.0)
- PHI: 6.0 | contender target/avg: 6.0 | kind: composition
- **What it means:** Number of distinct role archetypes in the projected rotation.
- **Why it matters in the playoffs:** Versatile rosters can counter different playoff matchups; one-note rosters get schemed out of a series.
- **What fixes it:** multi-positional players who unlock different lineup looks
- Stats: distinct role_archetype count. Sources: PHI roster role engine (real bio+tracking) vs documented contender roster-construction targets.
