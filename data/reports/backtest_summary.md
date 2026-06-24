# Offseason Backtest Summary

Target team: PHI
Offseasons tested: after_2015-16, after_2016-17, after_2017-18, after_2018-19, after_2019-20, after_2020-21, after_2021-22, after_2022-23, after_2023-24, after_2024-25
Rows evaluated: 5198

## Overall Metrics

| Method | Spearman | Top Quartile Gap | Hit Rate Top K | Avg Top Target Value |
| --- | ---: | ---: | ---: | ---: |
| moreymachine_fit | 0.436 | 29.402 | 0.370 | 50.642 |
| previous_points | 0.588 | 39.003 | 0.850 | 72.233 |
| previous_impact | N/A | N/A | N/A | N/A |
| salary | N/A | N/A | N/A | N/A |
| random | -0.012 | -0.173 | 0.210 | 35.460 |

## Baseline Comparison

| Baseline | Avg Top Value | Delta vs MoreyMachine |
| --- | ---: | ---: |
| previous_points | 72.233 | -21.591 |
| previous_impact | N/A | N/A |
| salary | N/A | N/A |
| random | 35.460 | 15.182 |
