# Offseason Backtest Summary

Target team: PHI
Offseasons tested: after_2015-16, after_2016-17, after_2017-18, after_2018-19, after_2019-20, after_2020-21, after_2021-22, after_2022-23, after_2023-24, after_2024-25
Rows evaluated: 5198

## Method

For each historical offseason, MoreyMachine builds PHI roster gaps using only data through the previous season, creates that offseason's non-PHI candidate universe from previous-season player rows, ranks the candidates, then joins the same players to next-season outcomes.

The primary `next_season_value` is basketball-only: minutes, games, true shooting, role stability, available impact proxy, availability, win-share signal when present, and playoff-rotation usefulness. Contract surplus is reported separately and only when salary data exists.

## Overall Metrics

| Method | Spearman | Top Quartile Gap | Hit Rate Top K | Avg Top Target Value |
| --- | ---: | ---: | ---: | ---: |
| moreymachine_fit | 0.465 | 21.362 | 0.360 | 67.304 |
| previous_points | 0.569 | 25.519 | 0.750 | 77.504 |
| previous_minutes | 0.631 | 28.159 | 0.710 | 77.106 |
| previous_true_shooting | 0.338 | 15.559 | 0.190 | 58.070 |
| previous_usage | 0.245 | 11.419 | 0.610 | 71.342 |
| previous_impact | 0.333 | 15.387 | 0.580 | 70.514 |
| random | -0.005 | 0.034 | 0.190 | 57.045 |

## What The Model Appears To Do Well

- It identifies candidates with durable basketball value when its Spearman correlation is positive (0.465) and top-target value clears the random baseline.
- Its strongest evidence is on basketball-fit outcomes that are present in the cached stat tables: minutes, games, true shooting, role stability, and box-score impact proxy.

## Where It Fails Or Is Limited

- Simple star-power baselines, especially previous-season scoring or minutes, can beat a fit model when the outcome rewards raw next-season volume more than acquisition realism.
- Historical injury context, transaction intent, trade availability, and candidate status are not invented; if those sources are absent, they remain missing rather than inferred.

## Metric Reliability

- More reliable: next-season minutes, games, true shooting, availability, and role stability because they come directly from season stat rows.
- More limited: impact proxy where advanced impact columns are absent; it falls back to an explicit box-score production proxy from available stats.
- Contract-value backtesting is separated from basketball fit, but no historical salary table was available for this run, so contract surplus metrics are not reliable yet.

## Baseline Comparison

| Baseline | Avg Top Value | Delta vs MoreyMachine |
| --- | ---: | ---: |
| previous_points | 77.504 | -10.199 |
| previous_minutes | 77.106 | -9.802 |
| previous_true_shooting | 58.070 | 9.234 |
| previous_usage | 71.342 | -4.038 |
| previous_impact | 70.514 | -3.210 |
| random | 57.045 | 10.260 |
