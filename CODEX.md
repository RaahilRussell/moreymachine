# MoreyMachine

MoreyMachine is an unofficial NBA front-office analytics engine.

It learns what contender rosters look like, diagnoses team-specific roster gaps, and ranks free agents/trade targets by fit, playoff portability, contract value, and contender-similarity gain.

Target team for MVP:
Philadelphia 76ers.

Important:
This project is not affiliated with Daryl Morey, the Philadelphia 76ers, or the NBA.

Engineering rules:
- Use Python 3.11+.
- Keep reusable code in src/moreymachine.
- Keep notebooks exploratory only.
- Use Parquet for saved data.
- Cache all NBA API requests.
- Never hardcode giant datasets inside code.
- Add type hints and docstrings.
- Add tests for scoring functions and schemas.
- Commit after every working milestone.
- Push to GitHub after major phases.
- Build explainable models first before complicated models.
- Prefer transparent feature engineering over black-box deep learning.

Core model:
1. Build team-season fingerprints.
2. Build playoff outcome tiers.
3. Build regular-season quality tiers.
4. Build roster archetype clusters.
5. Build current Sixers roster gap report.
6. Build player archetype classifier.
7. Build candidate fit scoring.
8. Build backtesting system.
9. Build Streamlit dashboard.

Scoring:
Final GM Fit Score =
35% Contender Similarity Gain
25% Roster Need Match
20% Playoff Portability
20% Contract Value

Dashboard pages:
1. Sixers diagnosis
2. Contender blueprint
3. Free-agent board
4. Player detail
5. Backtest proof
