# MoreyMachine — Real Data Audit

- **Audit date:** 2026-06-24
- **Auditor:** automated repo audit (pre-rebuild checkpoint)
- **Branch / commit:** `main` @ `5120fdf` ("checkpoint before real data rebuild")
- **Verdict:** The repo has a **real NBA data foundation**, but **every ranking the app currently displays comes from fabricated demo Parquet files**, and the real analytical pipeline is **broken at the playoff-tier step** so it produces no real downstream outputs. Multiple hard rules from the spec are currently violated.

---

## 1. What is REAL (verified)

| Artifact | Rows | Seasons | Evidence it is real |
|---|---|---|---|
| `data/raw/nba_api/leaguedashteamstats/*.json` | 30 teams × 11 files | 2015-16 → 2025-26 | Wrapped with `endpoint`, `params`, `fetched_at_utc` (e.g. `2026-06-24T06:13:39Z`). Spot-check: 2023-24 Atlanta Hawks = 82 GP, 36-46 — matches reality. |
| `data/raw/nba_api/leaguedashplayerstats/*.json` | 11 files | 2015-16 → 2025-26 | Same NBA.com endpoint, cached with timestamps. |
| `data/processed/team_seasons_basic.parquet` | 330 (30×11) | 2015-16 → 2025-26 | Direct clean of the real raw team JSON. |
| `data/processed/player_seasons_basic.parquet` | 5,968 | 2015-16 → 2025-26 | Direct clean of the real raw player JSON. |
| `data/features/player_archetypes.parquet` | 3,975 | 2015-16 → 2025-26 | Derived from real player_seasons_basic. (Only real feature output that exists.) |

The fetch path (`scripts/fetch_nba_data.py` → `src/moreymachine/data/fetch_nba.py`) is genuine: it calls `nba_api` `LeagueDashTeamStats` / `LeagueDashPlayerStats`, caches raw JSON, validates schema, and writes processed Parquet. **This is the trustworthy core.**

## 2. What is FAKE / DEMO (must never enter real rankings)

All files in `data/demo/` are **hand-fabricated, 3-row toy datasets** — not derived from the real data:

| Demo file | Rows | What it fakes | `source` col? |
|---|---|---|---|
| `data/demo/candidate_fit_rankings.parquet` | 3 | Final ranked free-agent board | ❌ none |
| `data/demo/phi_roster_gaps.parquet` | 4 | Sixers roster gap report | ❌ none |
| `data/demo/team_fingerprints.parquet` | 3 | Team advanced profiles + tiers | ❌ none |
| `data/demo/team_roster_archetypes.parquet` | 3 | Team archetype clusters | ❌ none |
| `data/demo/player_archetypes.parquet` | 3 | Player archetypes | ❌ none |
| `data/demo/player_seasons_basic.parquet` | 3 | Player stats | ❌ none |
| `data/demo/backtest_rankings.parquet` | 3 | Backtest rankings | ❌ none |
| `data/demo/backtest_results.json` / `backtest_summary.md` | — | Backtest proof | — |

These are all single-season (`2025-26`), 3-row stubs. They have **no provenance columns** (no `source`, no `pulled_at`).

## 3. Where fake output reaches the user

`src/moreymachine/app/streamlit_app.py` is the violation hotspot:

- **Silent fallback (violates hard rule "Do NOT silently fall back to toy/demo data").** `resolve_dataset_path()` in `"Auto"` mode returns the demo file whenever the real file is missing (lines 167-170). Default mode is `"Auto"`, and it flips to `"Demo data"` automatically when no full data exists (lines 522-529).
- **No provenance shown.** No "Data Sources" panel; the UI never displays source/season/pulled_at/row-count/real-vs-demo status.
- **No loud failure in real mode.** Missing real files render an `st.info("No data…")` placeholder, not a hard error.
- **Net effect today:** because the real downstream pipeline has not produced its outputs (see §4), the app currently serves the **3-row fabricated demo rankings** as if they were the product.

## 4. Why the real pipeline produces no real rankings

The real chain breaks immediately after fetch:

1. **`data/manual/playoff_tiers_template.csv` is EMPTY (0 rows).** It is also only a *template* — `playoff_tiers.PLAYOFF_TIERS_PATH` points at the template, and there is no real `playoff_tiers.csv`.
2. `build_team_seasons_with_tiers()` requires every team-season to have a tier and **fails loudly** (correct behavior) → `data/processed/team_seasons_with_tiers.parquet` **does not exist**.
3. Therefore none of the downstream real outputs exist: no real `team_fingerprints`, `quality_tiers`, `roster_archetypes`, `contender_model`, `outcome_tier_model`, `roster_gaps`, `candidate_fit_rankings`, or `backtest` results. `data/models/` and most of `data/reports/` are empty.

So the real pipeline is not *lying* — it simply hasn't run past the tier gate, and the app papers over the gap with demo data.

## 5. Schema gaps vs the target spec

The current real processed data is **box-score totals only** — it lacks the advanced fields the models need:

- `team_seasons_basic.parquet` has `pts, fgm, fga, oreb, dreb, tov…` but **no** `off_rating, def_rating, net_rating, pace, efg_pct, tov_pct, oreb_pct, dreb_pct, fta_rate, three_pa_rate`, and **no `source` / `pulled_at`** provenance columns.
- `player_seasons_basic.parquet` similarly lacks `usage_rate, true_shooting, assist_pct, turnover_pct, rebound_pct, steal_pct, block_pct, position`, and provenance columns.
- **Root cause:** the fetch only requests the `Base` measure type. It must also pull `Advanced` (and ideally `Four Factors`) measure types from the same endpoints, which supply `OFF_RATING, DEF_RATING, NET_RATING, PACE, EFG_PCT, TS_PCT, *_PCT, USG_PCT` directly from NBA.com.
- `team_fingerprints.py` *does* estimate some metrics from box score (off_rating from pts/possessions, eFG from fgm/fg3m/fga), but **`defensive_rating` has no fallback** (needs opponent data) → `net_rating` would be NaN. Estimated ratings are also less trustworthy than NBA.com's official advanced numbers.

## 6. Provenance status

- **No `source` or `pulled_at` columns** exist on any processed/feature/demo Parquet. The raw JSON does carry `fetched_at_utc` and `params`, but that provenance is dropped during cleaning.
- Target file names from the spec do not yet exist: `team_seasons.parquet`, `player_seasons.parquet`, `team_seasons_with_tiers.parquet`, `team_fingerprints.parquet` (in features), `player_archetypes.parquet` matches, `phi_roster_gaps.*`, `candidates.csv`, `playoff_tiers.csv`.

## 7. Hard-rule compliance scorecard

| Rule | Status |
|---|---|
| No fake rankings | ❌ App serves fabricated 3-row demo rankings today |
| No silent fallback to demo | ❌ `"Auto"` mode silently substitutes demo |
| No ranking unless source is real **and displayed** | ❌ No source displayed anywhere |
| Show "missing data" + what to fetch | ⚠️ Partial (`st.info` placeholders, no fetch guidance) |
| Demo only in `data/demo`, clearly labeled, never mixed | ⚠️ Located correctly, but mixed into real flow via Auto fallback |
| Provenance on every output | ❌ No `source`/`pulled_at`/season/path shown |
| Every score has an explanation | ✅ Largely present (`why_fit`, `concerns`, gap explanations, portability bullets) |
| Tests prevent demo entering real mode | ❌ No such test exists |
| `REAL_DATA_MODE` flag | ❌ Does not exist |

---

## 8. TODO (ordered, maps to milestone plan)

1. **Add `REAL_DATA_MODE` (default true).** Config flag; in real mode the app/pipeline must fail loudly on missing real Parquet and must **never** read `data/demo`. Add a test that asserts no demo path is reachable in real mode.
2. **Upgrade fetch to real advanced metrics.** Pull `Advanced` (+ `Four Factors`) measure types for teams and players; write `team_seasons.parquet` / `player_seasons.parquet` with all required fields **plus `source` and `pulled_at`**.
3. **Create real `data/manual/playoff_tiers.csv`** with verified results for all team-seasons used in modeling (tiers 0-5). Keep the validation gate.
4. **Build tier systems** → `team_seasons_with_tiers.parquet`, within-season `quality_tier`.
5. **Build fingerprints + explanation engine** with per-score explanation functions and provenance.
6. **Train contender + outcome-tier models** (chronological validation) and write metrics/predictions.
7. **Roster + player archetypes** from real data with z-score-derived cluster names.
8. **Sixers gap engine** → `phi_roster_gaps.parquet/.md`.
9. **Candidate fit model** with real/manual `candidates.csv` import (clearly labeled) and salary CSV workflow.
10. **Rebuild Streamlit** as explanation-first pages incl. the **Data Sources** panel; remove silent demo fallback.
11. **Real backtest** vs baselines; label basketball-fit separately from contract value when salary is incomplete.
12. **Deployment**: precomputed Parquet load only (no live fetch on page load), `requirements.txt`, `DEPLOYMENT.md`.
