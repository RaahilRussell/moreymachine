"""Fetch real player bio and player-tracking data from NBA.com (nba_api).

Two canonical tables are produced here, both from *real* NBA.com Stats endpoints
and both carrying ``source`` / ``pulled_at`` provenance:

* ``player_bio`` from the ``playerindex`` endpoint - position, height, weight,
  draft year. These are real attributes the season-stats endpoints never expose
  (which is why archetypes were previously guessed without position data).
* ``player_tracking`` from ``leaguedashptstats`` - catch-and-shoot, pull-up,
  drives, passing, touches/time-of-possession and rebounding chances. Each
  tracking *measure* is fetched independently; if one fails, the others are
  still written and the missing measure is recorded in ``missing_data_flags``.

Nothing here is invented. Missing attributes are left null and flagged. Raw
responses are cached as JSON under ``data/raw/nba_api`` and reused offline so a
later run (or the app) never needs the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.fetch_nba import fetch_cached_endpoint, infer_latest_season
from moreymachine.utils.paths import (
    NBA_API_RAW_DIR,
    PLAYER_BIO_PATH,
    PLAYER_TRACKING_PATH,
)

BIO_SOURCE = "nba_api:playerindex (NBA.com Stats)"
TRACKING_SOURCE = "nba_api:leaguedashptstats (NBA.com Stats)"

BIO_OUTPUT_COLUMNS = (
    "player_id",
    "player_name",
    "position",
    "height",
    "height_inches",
    "weight",
    "draft_year",
    "draft_number",
    "team_abbr",
    "source",
    "pulled_at",
    "missing_data_flags",
)

# Tracking measures we pull. Each maps the endpoint's raw columns to the tidy
# output names. A measure that errors is skipped and flagged, never faked.
TRACKING_MEASURES: dict[str, dict[str, str]] = {
    "CatchShoot": {
        "CATCH_SHOOT_FGA": "catch_shoot_fga",
        "CATCH_SHOOT_FG3A": "catch_shoot_fg3a",
        "CATCH_SHOOT_FG3_PCT": "catch_shoot_fg3_pct",
    },
    "PullUpShot": {
        "PULL_UP_FGA": "pull_up_fga",
        "PULL_UP_FG3A": "pull_up_fg3a",
        "PULL_UP_FG_PCT": "pull_up_fg_pct",
    },
    "Drives": {
        "DRIVES": "drives",
        "DRIVE_PTS": "drive_pts",
    },
    "Passing": {
        "PASSES_MADE": "passes_made",
        "POTENTIAL_AST": "potential_ast",
    },
    "Possessions": {
        "TOUCHES": "touches",
        "FRONT_CT_TOUCHES": "front_ct_touches",
        "TIME_OF_POSS": "time_of_poss",
        "AVG_SEC_PER_TOUCH": "avg_sec_per_touch",
    },
    "Rebounding": {
        "REB_CHANCES": "reb_chances",
        "OREB_CHANCES": "oreb_chances",
        "DREB_CHANCES": "dreb_chances",
        "REB_CONTEST_PCT": "reb_contest_pct",
    },
    "Defense": {
        "DEF_RIM_FGA": "def_rim_fga",
        "DEF_RIM_FG_PCT": "def_rim_fg_pct",
    },
}


@dataclass(frozen=True)
class BioTrackingResult:
    """Summary of a player bio + tracking fetch."""

    season: str
    bio_rows: int
    tracking_rows: int
    tracking_measures_ok: tuple[str, ...]
    tracking_measures_failed: tuple[str, ...]
    bio_path: Path
    tracking_path: Path


def fetch_player_bio(
    *,
    season: str | None = None,
    cache_dir: str | Path = NBA_API_RAW_DIR,
    output_path: str | Path = PLAYER_BIO_PATH,
    max_retries: int = 3,
    timeout: int = 30,
    write: bool = True,
) -> pd.DataFrame:
    """Fetch real player bio attributes (position/height/weight/draft)."""
    season = season or infer_latest_season()
    cache = JsonFileCache(cache_dir)
    payload = fetch_cached_endpoint(
        endpoint_cls=_player_index_cls(),
        endpoint_name="playerindex",
        params={"season": season},
        cache=cache,
        max_retries=max_retries,
        timeout=timeout,
    )
    rows = _first_dataset(payload)
    raw = pd.DataFrame(rows)
    pulled_at = _today()

    out = pd.DataFrame()
    out["player_id"] = pd.to_numeric(raw["PERSON_ID"], errors="coerce").astype("Int64")
    out["player_name"] = (
        raw["PLAYER_FIRST_NAME"].astype(str).str.strip()
        + " "
        + raw["PLAYER_LAST_NAME"].astype(str).str.strip()
    ).str.strip()
    out["position"] = raw["POSITION"].replace("", pd.NA)
    out["height"] = raw["HEIGHT"].replace("", pd.NA)
    out["height_inches"] = out["height"].map(_height_to_inches)
    out["weight"] = pd.to_numeric(raw["WEIGHT"], errors="coerce")
    out["draft_year"] = (
        pd.to_numeric(raw["DRAFT_YEAR"], errors="coerce").astype("Int64")
    )
    out["draft_number"] = pd.to_numeric(
        raw["DRAFT_NUMBER"], errors="coerce"
    ).astype("Int64")
    out["team_abbr"] = raw["TEAM_ABBREVIATION"].replace("", pd.NA)
    out["source"] = BIO_SOURCE
    out["pulled_at"] = pulled_at
    out["missing_data_flags"] = out.apply(_bio_missing_flags, axis=1)

    out = out.loc[:, list(BIO_OUTPUT_COLUMNS)].reset_index(drop=True)
    if write:
        _write(out, output_path)
    return out


def fetch_player_tracking(
    *,
    season: str | None = None,
    cache_dir: str | Path = NBA_API_RAW_DIR,
    output_path: str | Path = PLAYER_TRACKING_PATH,
    max_retries: int = 3,
    timeout: int = 30,
    write: bool = True,
) -> tuple[pd.DataFrame, tuple[str, ...], tuple[str, ...]]:
    """Fetch real player-tracking measures, tolerating partial endpoint failure.

    Returns ``(frame, ok_measures, failed_measures)``. A measure that fails to
    fetch is omitted and recorded so downstream code (and the freshness report)
    can flag it as missing rather than silently filling zeros.
    """
    season = season or infer_latest_season()
    cache = JsonFileCache(cache_dir)
    pulled_at = _today()

    base: pd.DataFrame | None = None
    ok: list[str] = []
    failed: list[str] = []

    for measure, column_map in TRACKING_MEASURES.items():
        try:
            payload = fetch_cached_endpoint(
                endpoint_cls=_pt_stats_cls(),
                endpoint_name="leaguedashptstats",
                params={
                    "season": season,
                    "pt_measure_type": measure,
                    "player_or_team": "Player",
                    "per_mode_simple": "PerGame",
                },
                cache=cache,
                max_retries=max_retries,
                timeout=timeout,
            )
            rows = _first_dataset(payload)
        except Exception:  # noqa: BLE001 - partial data is acceptable, faking is not
            failed.append(measure)
            continue

        raw = pd.DataFrame(rows)
        keep = {"PLAYER_ID": "player_id"}
        if base is None:
            keep.update(
                {
                    "PLAYER_NAME": "player_name",
                    "TEAM_ABBREVIATION": "team_abbr",
                    "MIN": "min",
                }
            )
        keep.update(column_map)
        present = {src: dst for src, dst in keep.items() if src in raw.columns}
        frame = raw.loc[:, list(present)].rename(columns=present)
        frame["player_id"] = pd.to_numeric(frame["player_id"], errors="coerce").astype(
            "Int64"
        )
        for dst in column_map.values():
            if dst in frame.columns:
                frame[dst] = pd.to_numeric(frame[dst], errors="coerce")
        ok.append(measure)
        base = frame if base is None else base.merge(frame, on="player_id", how="outer")

    if base is None:
        out = pd.DataFrame(columns=["player_id", "player_name", "team_abbr", "min"])
    else:
        out = base

    out["source"] = TRACKING_SOURCE
    out["pulled_at"] = pulled_at
    measures_missing = ", ".join(failed) if failed else "none"
    out["missing_data_flags"] = (
        f"tracking measures missing: {measures_missing}" if failed else "none"
    )
    out = out.reset_index(drop=True)
    if write:
        _write(out, output_path)
    return out, tuple(ok), tuple(failed)


def fetch_bio_and_tracking(
    *,
    season: str | None = None,
    cache_dir: str | Path = NBA_API_RAW_DIR,
    bio_output_path: str | Path = PLAYER_BIO_PATH,
    tracking_output_path: str | Path = PLAYER_TRACKING_PATH,
    max_retries: int = 3,
    timeout: int = 30,
) -> BioTrackingResult:
    """Fetch both bio and tracking tables and return a combined summary."""
    season = season or infer_latest_season()
    bio = fetch_player_bio(
        season=season,
        cache_dir=cache_dir,
        output_path=bio_output_path,
        max_retries=max_retries,
        timeout=timeout,
    )
    tracking, ok, failed = fetch_player_tracking(
        season=season,
        cache_dir=cache_dir,
        output_path=tracking_output_path,
        max_retries=max_retries,
        timeout=timeout,
    )
    return BioTrackingResult(
        season=season,
        bio_rows=len(bio),
        tracking_rows=len(tracking),
        tracking_measures_ok=ok,
        tracking_measures_failed=failed,
        bio_path=Path(bio_output_path),
        tracking_path=Path(tracking_output_path),
    )


def _bio_missing_flags(row: pd.Series) -> str:
    flags = []
    if pd.isna(row.get("position")):
        flags.append("position missing")
    if pd.isna(row.get("height_inches")):
        flags.append("height missing")
    if pd.isna(row.get("weight")):
        flags.append("weight missing")
    if pd.isna(row.get("draft_year")):
        flags.append("draft year missing")
    return "; ".join(flags) if flags else "none"


def _height_to_inches(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if "-" not in text:
        return None
    feet_text, _, inch_text = text.partition("-")
    try:
        return float(int(feet_text) * 12 + int(inch_text))
    except ValueError:
        return None


def _first_dataset(payload: dict) -> list:
    for value in payload.values():
        if isinstance(value, list):
            return value
    raise ValueError("Endpoint payload contained no row dataset")


def _player_index_cls():
    from nba_api.stats.endpoints.playerindex import PlayerIndex

    return PlayerIndex


def _pt_stats_cls():
    from nba_api.stats.endpoints.leaguedashptstats import LeagueDashPtStats

    return LeagueDashPtStats


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _write(frame: pd.DataFrame, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
