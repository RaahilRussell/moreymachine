# Demo data — NOT real, never used in rankings

The Parquet/JSON/Markdown files in this directory are **tiny, fabricated toy
samples** kept only for offline UI experiments and screenshots.

- They are **not** derived from real NBA data and have no provenance columns.
- They are **never** loaded by the app in `REAL_DATA_MODE` (the default).
- They are **not** part of the dataset registry (`moreymachine/app/data_sources.py`),
  so they can never enter a real ranking, gap report, or backtest.

Real artifacts live under `data/processed`, `data/features`, `data/models`,
`data/reports`, and `data/manual`. Build them with the pipeline in `DEPLOYMENT.md`.
