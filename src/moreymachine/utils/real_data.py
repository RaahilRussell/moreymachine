"""Guards that keep demo/fake data out of REAL_DATA_MODE.

REAL_DATA_MODE is the project's central safety switch. When it is enabled
(the default), the app and pipeline must:

* fail loudly when a required real Parquet/CSV file is missing, and
* never read anything from ``data/demo``.

These helpers centralise that behaviour so every page and script enforces the
same rule. See ``data/reports/real_data_audit.md`` for the motivating audit.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from moreymachine.utils.config import Settings, load_settings
from moreymachine.utils.paths import DEMO_DATA_DIR


class MissingRealDataError(RuntimeError):
    """Raised when a required real-data file is missing in REAL_DATA_MODE."""

    def __init__(self, *, table: str, path: Path, how_to_fix: str) -> None:
        self.table = table
        self.path = Path(path)
        self.how_to_fix = how_to_fix
        super().__init__(
            f"Missing real data for '{table}': {self.path} does not exist. "
            f"REAL_DATA_MODE is on, so MoreyMachine will not invent or fall back "
            f"to demo data. To fix: {how_to_fix}"
        )


class DemoDataInRealModeError(RuntimeError):
    """Raised when a demo-data path is requested while REAL_DATA_MODE is on."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        super().__init__(
            f"Refusing to read demo data in REAL_DATA_MODE: {self.path}. "
            "Demo data may never enter real rankings."
        )


def is_demo_path(path: str | Path) -> bool:
    """Return ``True`` when ``path`` lives under the demo data directory."""
    candidate = Path(path).resolve()
    demo_root = DEMO_DATA_DIR.resolve()
    return candidate == demo_root or demo_root in candidate.parents


def guard_against_demo(path: str | Path, *, settings: Settings | None = None) -> Path:
    """Raise if ``path`` is a demo path while REAL_DATA_MODE is enabled."""
    settings = settings or load_settings()
    resolved = Path(path)
    if settings.real_data_mode and is_demo_path(resolved):
        raise DemoDataInRealModeError(resolved)
    return resolved


def require_real_file(
    path: str | Path,
    *,
    table: str,
    how_to_fix: str,
    settings: Settings | None = None,
) -> Path:
    """Return ``path`` if it exists; otherwise fail loudly in REAL_DATA_MODE.

    Outside REAL_DATA_MODE the missing path is returned unchanged so callers can
    decide how to degrade. Inside REAL_DATA_MODE a missing required file raises
    :class:`MissingRealDataError` describing exactly what to fetch.
    """
    settings = settings or load_settings()
    resolved = guard_against_demo(path, settings=settings)
    if not resolved.exists() and settings.real_data_mode:
        raise MissingRealDataError(table=table, path=resolved, how_to_fix=how_to_fix)
    return resolved


# Human-readable "how to fix" hints, keyed by logical table name. Used by both
# the loud pipeline failures and the Streamlit "missing data" warnings.
FIX_HINTS: Mapping[str, str] = {
    "team_seasons": "run `python scripts/fetch_nba_data.py`",
    "player_seasons": "run `python scripts/fetch_nba_data.py`",
    "playoff_tiers": ("add real results to data/manual/playoff_tiers.csv (tiers 0-5)"),
    "team_seasons_with_tiers": "run `python scripts/build_playoff_tiers.py`",
    "team_fingerprints": "run `python scripts/build_team_fingerprints.py`",
    "player_archetypes": "run `python scripts/build_player_archetypes.py`",
    "team_roster_archetypes": "run `python scripts/build_roster_archetypes.py`",
    "contender_model": "run `python scripts/train_contender_model.py`",
    "outcome_tier_model": "run `python scripts/train_outcome_tier_model.py`",
    "roster_gaps": "run `python scripts/analyze_roster_gaps.py --team PHI`",
    "candidates": (
        "add real free agents/salaries to data/manual/candidates.csv, then run "
        "`python scripts/fetch_candidates.py`"
    ),
    "candidate_rankings": "run `python scripts/rank_candidates.py --team PHI`",
    "backtest": "run `python scripts/run_backtest.py`",
    "transactions": "run `python scripts/refresh_transactions.py`",
}


def fix_hint(table: str) -> str:
    """Return a how-to-fix hint for a logical table name."""
    return FIX_HINTS.get(table, f"rebuild the data for '{table}'")
