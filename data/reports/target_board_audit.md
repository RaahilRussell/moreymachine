# Target Board Audit — why the current recommendations are bad

- **Audited file:** `data/reports/candidate_fit_rankings.parquet`
- **Pulled:** 2026-06-24 (contracts via Basketball-Reference, stats via nba_api `leaguedashplayerstats`)
- **Audited:** 2026-06-24
- **Target team:** PHI

This audit is read-only. No scoring code was changed to produce it. It documents the
defects that justify the rebuild.

---

## 1. Headline numbers

| Metric | Value | Verdict |
|---|---|---|
| Candidates | 270 | — |
| `candidate_type` values present | only `trade_target` (261) + `manual_watchlist` (9) | **Broken** — no free agents, minimums, MLE, rookie-scale, stars, or unavailable cores |
| Priority targets | **76** | **Broken** — spec caps this at 10 |
| "Buy" recommendations (Priority + Strong) | 155 / 270 (57%) | **Broken** — over half the league is a "fit" |
| `contract_value == 100` | **113 / 270 (41.9%)** | **Saturated** — gate allows ≤10% |
| `portability == 100` | **91 / 270 (33.7%)** | **Saturated** — gate allows ≤10% |
| `risk_score == 15` (the floor) | **195 / 270 (72.2%)** | **Collapsed** — gate fails if >50% identical |
| `position` populated | **0 / 270** | **Broken** — archetypes assigned with no position/bio data |

---

## 2. Recommendation counts

```
Strong fit if affordable    79
Priority target             76
Role-player target          68
Only if cheap               34
Avoid                       13
```

There is no "Unrealistic / unavailable" tier and no "Missing data / cannot evaluate"
tier. Every player is treated as acquirable. 76 Priority Targets is ~7.6× the spec cap.

## 3. candidate_type counts

```
trade_target        261
manual_watchlist      9
```

Every contracted player in the league is bucketed as `trade_target`. There is no
distinction between:
- a free agent you can simply sign,
- a minimum/MLE signing,
- a realistic trade chip vs. an untouchable franchise cornerstone,
- a rookie-scale player (acquisition cost is *draft/trade capital*, not salary),
- a current Sixer (should never be on an acquisition board at all).

## 4. Score saturation

- **contract_value:** 113 players (41.9%) sit at exactly 100. A 0.6M end-of-bench player
  and a genuinely cheap rotation player get the identical max score. Value is not
  role-relative or minutes-relative.
- **portability:** 91 players (33.7%) sit at exactly 100. Spacing/portability is being
  awarded on thin shooting samples and to players who will never see playoff minutes.
- **need_match:** range 33.9–90.3 (less saturated, but compresses around 53–69).
- **contender_gain:** range 47.3–92.4, mean 73.3 — bench and fringe players routinely
  score 80+, which is the exact bug called out in the spec (low-minute players producing
  large contender gains).

## 5. Risk distribution is collapsed

```
risk_score  count
15.0        195   <- floor, 72.2% of all candidates
25.0         40
30.0         14
23.0         10
40.0          7
33.0          3
45.0          1
```

mean 18.5, min 15, median 15. Risk is effectively a constant. Age risk, sample-size
risk, role uncertainty, acquisition risk, and missing-data risk are not expressed.
This **fails** the "no more than 50% identical" gate immediately.

## 6. Top 25 ranked players (current model)

| # | Player | Team | Archetype (current) | fit | contract_value | portability | risk | rec |
|---|---|---|---|---|---|---|---|---|
| 1 | Kel'el Ware | MIA | Rim Protector | 91.9 | 100 | 100 | 15 | Priority |
| 2 | Jalen Smith | CHI | Rim Protector | 91.3 | 100 | 100 | 15 | Priority |
| 3 | Jaylin Williams | OKC | Rim Protector | 89.7 | 100 | 100 | 15 | Priority |
| 4 | Luka Garza | BOS | Rim Protector | 88.4 | 100 | 100 | 15 | Priority |
| 5 | Baylor Scheierman | BOS | Low-Usage Spacer | 87.7 | 100 | 100 | 15 | Priority |
| 6 | Jordan Walsh | BOS | Rim Protector | 87.7 | 100 | 100 | 15 | Priority |
| 7 | Chet Holmgren | OKC | Rim Protector | 87.6 | 99.9 | 100 | 15 | Priority |
| 8 | Julian Champagnie | SAS | Low-Usage Spacer | 87.2 | 100 | 100 | 15 | Priority |
| 9 | Bobby Portis | MIL | Balanced Role Player | 86.8 | 100 | 100 | 15 | Priority |
| 10 | Donovan Clingan | POR | Rim Protector | 86.8 | 100 | 96 | 15 | Priority |
| 11 | Sandro Mamukelashvili | TOR | Balanced Role Player | 86.6 | 100 | 100 | 15 | Priority |
| 12 | Spencer Jones | DEN | Low-Usage Spacer | 86.3 | 100 | 100 | 15 | Priority |
| 13 | Jock Landale | ATL | Rim Protector | 86.1 | 100 | 100 | 15 | Priority |
| 14 | Josh Hart | NYK | Balanced Role Player | 85.5 | 88.8 | 100 | 15 | Priority |
| 15 | Onyeka Okongwu | ATL | Rim Protector | 85.5 | 96.2 | 100 | 15 | Priority |
| 16 | Ja'Kobe Walter | TOR | Low-Usage Spacer | 85.5 | 100 | 100 | 15 | Priority |
| 17 | Isaiah Joe | OKC | Low-Usage Spacer | 85.3 | 100 | 100 | 15 | Priority |
| 18 | Javonte Green | DET | Low-Usage Spacer | 85.2 | 100 | 100 | 15 | Priority |
| 19 | Luke Kennard | LAL | Low-Usage Spacer | 85.2 | 100 | 100 | 15 | Priority |
| 20 | Jaylon Tyson | CLE | Balanced Role Player | 85.1 | 100 | 100 | 15 | Priority |
| 21 | Royce O'Neale | PHX | Low-Usage Spacer | 85.0 | 100 | 100 | 23 | Priority |
| 22 | Sam Hauser | BOS | Low-Usage Spacer | 84.8 | 100 | 100 | 15 | Priority |
| 23 | Sam Merrill | CLE | Low-Usage Spacer | 84.5 | 100 | 100 | 15 | Priority |
| 24 | Moses Moody | GSW | Low-Usage Spacer | 84.4 | 100 | 100 | 15 | Priority |
| 25 | Dean Wade | CLE | Low-Usage Spacer | 84.3 | 100 | 100 | 15 | Priority |

The board is dominated by cheap young bigs and low-minute "spacers" because the model
rewards cheap salary + any 3P% + low usage, with risk pinned to the floor.

## 7. Obviously unrealistic players ranked as Priority Targets (top 50)

These are franchise cornerstones, recent high lottery picks, or entrenched core
rotation players that the listed team will not move for a PHI role-player package — yet
all are tagged `trade_target` + `Priority target`:

- **Chet Holmgren (OKC)** — All-NBA-track franchise center, untouchable. Ranked #7.
- **Donovan Clingan (POR)** — recent top-7 pick, rookie-scale building block.
- **Kel'el Ware (MIA)** — #1 overall on this board; ascending young center MIA won't dump.
- **Kon Knueppel (CHA)**, **Ja'Kobe Walter (TOR)**, **Jaylon Tyson (CLE)**,
  **Brandin Podziemski (GSW)** — rookie-scale players; acquisition cost is trade capital,
  not their salary.
- **Aaron Gordon (DEN)**, **Cameron Johnson (DEN)**, **Onyeka Okongwu (ATL)**,
  **Wendell Carter Jr. (ORL)** — entrenched starters/core; not realistically available
  for a PHI return and not "Priority target" cheap.

Separately, **Jimmy Butler III (GSW)** appears as `manual_watchlist` / **"Avoid"** — a
star slotted into the watchlist but graded like a fringe player, with no star handling.

## 8. Current PHI players

None of the 270 candidates have `current_team == 'PHI'`, so the board does not *leak*
Sixers into recommendations. **But** that is by accidental omission, not design: there is
no "Current Roster" reference table, and no `current_sixers_player` candidate_type. The
2025-26 PHI roster (for the reference table the rebuild must add) is:

`Adem Bona, Andre Drummond, Cameron Payne, Dalen Terry, Dominick Barlow, Eric Gordon,
Hunter Sallis, Jabari Walker, Joel Embiid, Johni Broome, Justin Edwards, Kelly Oubre Jr.,
Kyle Lowry, MarJon Beauchamp, Paul George, Quentin Grimes, Trendon Watford, Tyrese Martin,
Tyrese Maxey, VJ Edgecombe`

## 9. Archetype labels that are basketball-wrong

There are only **5** archetype labels total (`Low-Usage Spacer`, `Balanced Role Player`,
`High-Usage Creator`, `Rim Protector`, `Defensive Specialist`) — far too coarse to drive
front-office decisions. Worse, they are assigned **without any position or height data**
(`position` is empty for all 270 rows; `missing_data_flags` literally says "position not
provided by source"). Consequences:

- **Jordan Walsh (BOS)** — a 6'7" wing — labeled **Rim Protector**.
- **Peyton Watson (DEN)** — a wing — labeled **Rim Protector**.
- **Luka Garza (BOS)** — an offense-only stretch scorer — labeled **Rim Protector**.
- **Royce O'Neale, Nicolas Batum, Tim Hardaway Jr.** — veteran 3-and-D / connector wings
  — all flattened to **Low-Usage Spacer**.

Any archetype assigned off box-score stats alone, with no position/tracking input, is
unreliable; the rim-protection vs. wing confusion is the clearest symptom.

## 10. Explanation quality

Explanations are templated and shallow. Example (current #1, Kel'el Ware):

> **why_fit:** "Need match 90.3; contender gain 92.4; portability 100.0; answers defense;
> answers shooting pressure; Usable playoff spacing volume."
> **concerns:** "No major rule-based concerns."
> **missing_data_flags:** "position not provided by source"

There is no acquisition feasibility, no "why it might fail," no salary context, no
expected role, and "No major rule-based concerns" appears for nearly every Priority
Target — which is exactly the over-confidence the rebuild must remove.

---

## 11. Root causes (what the rebuild must fix)

1. **No candidate universe model.** Everyone contracted is a `trade_target`; no free
   agents, minimums, MLE, rookie-scale, star/unavailable, or current-roster handling.
2. **Saturated, non-relative scores.** contract_value and portability hit 100 for ~35–42%
   of players because they are not percentile-based, winsorized, or role/minutes-relative.
3. **Collapsed risk.** 72% sit at the floor of 15; risk has no real components.
4. **Contender gain ignores minutes.** Fringe/bench players score 80+.
5. **No bio/tracking data.** `position` is empty; archetypes are guessed from box stats,
   producing wing-as-rim-protector errors and only 5 coarse labels.
6. **No tiers/caps.** 76 Priority Targets; over half the league is a "buy."
7. **Thin explanations.** No feasibility, no failure mode, no salary/role context.

These findings map directly to the rebuild: real bio/tracking tables, a categorized
candidate universe, percentile/winsorized role-aware scores, an expanded risk model,
strict tier caps, a richer role/archetype engine, explanation-first outputs, and
validation gates that fail on the exact saturation/collapse thresholds above.
