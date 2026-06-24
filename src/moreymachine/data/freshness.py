"""Summarise how fresh each canonical data table is (shared by app + CLI).

This reads the already-written Parquet/CSV tables and reports rows, season
coverage, source, ``pulled_at`` and data mode for each. It never triggers a
network fetch, so it is safe to call inside a Streamlit page load - the heavy
refresh lives in ``scripts/refresh_current_data.py`` and only updates the cached
files this module reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from moreymachine.utils.paths import (
    CONTRACTS_PATH,
    LINEUP_ON_OFF_PATH,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    PLAYER_TRACKING_PATH,
    TEAM_SEASONS_PATH,
)

REFRESH_COMMAND = "python scripts/refresh_current_data.py --season latest"


@dataclass
class TableFreshness:
    """Freshness facts for one data table."""

    name: str
    path: Path
    exists: bool
    rows: int = 0
    seasons: str = ""
    source: str = ""
    pulled_at: str = ""
    data_mode: str = "real"
    missing_fields: str = ""
    refresh_command: str = REFRESH_COMMAND
    note: str = ""
    extra: dict = field(default_factory=dict)


# (logical name, path, expected data_mode, whether it is optional)
_TABLE_SPECS = (
    ("team_seasons", TEAM_SEASONS_PATH, "real_api", False),
    ("player_seasons", PLAYER_SEASONS_PATH, "real_api", False),
    ("player_bio", PLAYER_BIO_PATH, "real_api", False),
    ("player_tracking", PLAYER_TRACKING_PATH, "real_api", False),
    ("contracts", CONTRACTS_PATH, "real_scraped", False),
    ("lineup_on_off", LINEUP_ON_OFF_PATH, "real_api", True),
)


def summarize_freshness() -> list[TableFreshness]:
    """Return freshness facts for every canonical table."""
    summaries = []
    for name, path, default_mode, optional in _TABLE_SPECS:
        summaries.append(_summarize_table(name, Path(path), default_mode, optional))
    return summaries


def _summarize_table(
    name: str, path: Path, default_mode: str, optional: bool
) -> TableFreshness:
    if not path.exists():
        note = (
            "Optional table not collected (lineup/on-off marked missing, not faked)."
            if optional
            else "MISSING - run the refresh command."
        )
        return TableFreshness(
            name=name,
            path=path,
            exists=False,
            data_mode="missing",
            note=note,
        )

    frame = pd.read_parquet(path)
    seasons = ""
    if "season" in frame.columns:
        unique = sorted(frame["season"].astype(str).unique())
        seasons = f"{unique[0]}..{unique[-1]}" if len(unique) > 1 else unique[0]
    source = _first_str(frame, "source")
    pulled_at = _first_str(frame, "pulled_at")
    data_mode = _first_str(frame, "data_mode") or default_mode
    missing_fields = _missing_field_summary(frame)
    return TableFreshness(
        name=name,
        path=path,
        exists=True,
        rows=len(frame),
        seasons=seasons,
        source=source,
        pulled_at=pulled_at,
        data_mode=data_mode,
        missing_fields=missing_fields,
    )


def _first_str(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns or frame.empty:
        return ""
    values = frame[column].dropna()
    if values.empty:
        return ""
    return str(values.iloc[0])


def _missing_field_summary(frame: pd.DataFrame) -> str:
    if "missing_data_flags" in frame.columns:
        flagged = frame["missing_data_flags"].fillna("none")
        n_flagged = int((flagged.astype(str).str.lower() != "none").sum())
        if n_flagged:
            return f"{n_flagged} rows carry missing_data_flags"
    fully_null = [c for c in frame.columns if frame[c].isna().all()]
    return f"all-null columns: {', '.join(fully_null)}" if fully_null else "none"


def render_freshness_markdown(summaries: list[TableFreshness]) -> str:
    """Render a freshness report as Markdown."""
    lines = [
        "# Data Freshness Report",
        "",
        f"_Refresh locally with:_ `{REFRESH_COMMAND}`",
        "",
        "| Table | Rows | Seasons | Source | Pulled at | Data mode | Missing |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in summaries:
        lines.append(
            "| {name} | {rows} | {seasons} | {source} | {pulled_at} | "
            "{data_mode} | {missing} |".format(
                name=item.name,
                rows=item.rows if item.exists else "—",
                seasons=item.seasons or "—",
                source=(item.source or item.note or "—")[:60],
                pulled_at=item.pulled_at or "—",
                data_mode=item.data_mode,
                missing=item.missing_fields or item.note or "—",
            )
        )
    lines.append("")
    return "\n".join(lines)
