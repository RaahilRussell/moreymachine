"""Fetch and clean real NBA.com season-level team and player stats.

This module pulls the *real* advanced metrics MoreyMachine needs (ratings,
pace, four-factor percentages, usage, true shooting) by combining several
``measure_type`` views of the same NBA.com endpoints:

* Teams: ``Base`` (wins/losses, shot volume) + ``Advanced`` (ratings, pace,
  rebounding/turnover %) + ``Four Factors`` (FTA rate).
* Players: ``Base`` (totals, age, shot volume) + ``Advanced`` (usage, true
  shooting, assist/turnover/rebound %).

Every output row carries provenance (``source`` and ``pulled_at``) so the app
can display where each number came from. Raw responses are cached as JSON under
``data/raw/nba_api`` and reused on later runs.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
from nba_api.stats.endpoints.leaguedashplayerstats import LeagueDashPlayerStats
from nba_api.stats.endpoints.leaguedashteamstats import LeagueDashTeamStats

from moreymachine.data.cache import JsonFileCache
from moreymachine.data.team_lookup import team_abbr_from_id
from moreymachine.utils.paths import (
    NBA_API_RAW_DIR,
    PLAYER_SEASONS_PATH,
    PROCESSED_DATA_DIR,
    TEAM_SEASONS_PATH,
)

START_SEASON = "2015-16"
TEAM_ENDPOINT_NAME = "leaguedashteamstats"
PLAYER_ENDPOINT_NAME = "leaguedashplayerstats"
TEAM_DATASET_NAME = "LeagueDashTeamStats"
PLAYER_DATASET_NAME = "LeagueDashPlayerStats"

TEAM_SOURCE = "nba_api:leaguedashteamstats (NBA.com Stats)"
PLAYER_SOURCE = "nba_api:leaguedashplayerstats (NBA.com Stats)"

# Measure types to request per endpoint. Each is cached and merged on the
# entity id. Keeping them explicit keeps provenance auditable.
TEAM_MEASURE_TYPES = ("Base", "Advanced", "Four Factors")
PLAYER_MEASURE_TYPES = ("Base", "Advanced")

# Required output columns (the contract other modules and tests rely on).
TEAM_OUTPUT_COLUMNS = (
    "season",
    "team_id",
    "team_abbr",
    "team_name",
    "wins",
    "losses",
    "off_rating",
    "def_rating",
    "net_rating",
    "pace",
    "efg_pct",
    "tov_pct",
    "oreb_pct",
    "dreb_pct",
    "fta_rate",
    "three_pa_rate",
    "three_p_pct",
    "source",
    "pulled_at",
)
PLAYER_OUTPUT_COLUMNS = (
    "season",
    "player_id",
    "player_name",
    "team_abbr",
    "age",
    "position",
    "minutes",
    "games",
    "pts",
    "reb",
    "ast",
    "usage_rate",
    "true_shooting",
    "three_pa",
    "three_pa_rate",
    "three_p_pct",
    "assist_pct",
    "turnover_pct",
    "rebound_pct",
    "steal_pct",
    "block_pct",
    "stl",
    "blk",
    "tov",
    "source",
    "pulled_at",
)

EndpointFactory = Callable[..., "EndpointResponse"]


class EndpointResponse(Protocol):
    """Protocol for the subset of nba_api endpoint objects used here."""

    def get_normalized_dict(self) -> dict[str, Any]:
        """Return the endpoint response as normalized JSON-compatible data."""


@dataclass(frozen=True)
class FetchResult:
    """Summary of a completed NBA data fetch."""

    seasons: tuple[str, ...]
    team_rows: int
    player_rows: int
    team_path: Path
    player_path: Path


def fetch_nba_data(
    *,
    start_season: str = START_SEASON,
    latest_season: str | None = None,
    cache_dir: str | Path = NBA_API_RAW_DIR,
    processed_dir: str | Path = PROCESSED_DATA_DIR,
    max_retries: int = 3,
    request_sleep_seconds: float = 0.6,
    retry_sleep_seconds: float = 2.0,
    timeout: int = 30,
    team_endpoint_cls: EndpointFactory = LeagueDashTeamStats,
    player_endpoint_cls: EndpointFactory = LeagueDashPlayerStats,
) -> FetchResult:
    """Fetch real team/player season stats and write cleaned Parquet outputs."""
    seasons = season_range(start_season, latest_season or infer_latest_season())
    cache = JsonFileCache(cache_dir)
    processed_path = Path(processed_dir)
    processed_path.mkdir(parents=True, exist_ok=True)

    team_frame = fetch_team_season_stats(
        seasons=seasons,
        cache=cache,
        endpoint_cls=team_endpoint_cls,
        max_retries=max_retries,
        request_sleep_seconds=request_sleep_seconds,
        retry_sleep_seconds=retry_sleep_seconds,
        timeout=timeout,
    )
    player_frame = fetch_player_season_stats(
        seasons=seasons,
        cache=cache,
        endpoint_cls=player_endpoint_cls,
        max_retries=max_retries,
        request_sleep_seconds=request_sleep_seconds,
        retry_sleep_seconds=retry_sleep_seconds,
        timeout=timeout,
    )

    team_path = processed_path / TEAM_SEASONS_PATH.name
    player_path = processed_path / PLAYER_SEASONS_PATH.name
    team_frame.to_parquet(team_path, index=False)
    player_frame.to_parquet(player_path, index=False)

    return FetchResult(
        seasons=seasons,
        team_rows=len(team_frame),
        player_rows=len(player_frame),
        team_path=team_path,
        player_path=player_path,
    )


# Backwards-compatible alias for the previous public name.
fetch_nba_basic_data = fetch_nba_data


def fetch_team_season_stats(
    *,
    seasons: Iterable[str],
    cache: JsonFileCache,
    endpoint_cls: EndpointFactory = LeagueDashTeamStats,
    max_retries: int = 3,
    request_sleep_seconds: float = 0.6,
    retry_sleep_seconds: float = 2.0,
    timeout: int = 30,
) -> pd.DataFrame:
    """Fetch and clean multi-measure team stats for each requested season."""
    frames = []
    for season in seasons:
        measures = _fetch_measures(
            measure_types=TEAM_MEASURE_TYPES,
            endpoint_cls=endpoint_cls,
            endpoint_name=TEAM_ENDPOINT_NAME,
            dataset_name=TEAM_DATASET_NAME,
            season=season,
            cache=cache,
            max_retries=max_retries,
            request_sleep_seconds=request_sleep_seconds,
            retry_sleep_seconds=retry_sleep_seconds,
            timeout=timeout,
        )
        frames.append(_build_team_frame(measures, season))

    result = pd.concat(frames, ignore_index=True)
    _validate_processed_schema(
        result,
        TEAM_OUTPUT_COLUMNS,
        required_non_null=(
            "season",
            "team_id",
            "team_abbr",
            "off_rating",
            "def_rating",
        ),
    )
    return result.loc[:, list(TEAM_OUTPUT_COLUMNS)]


def fetch_player_season_stats(
    *,
    seasons: Iterable[str],
    cache: JsonFileCache,
    endpoint_cls: EndpointFactory = LeagueDashPlayerStats,
    max_retries: int = 3,
    request_sleep_seconds: float = 0.6,
    retry_sleep_seconds: float = 2.0,
    timeout: int = 30,
) -> pd.DataFrame:
    """Fetch and clean multi-measure player stats for each requested season."""
    frames = []
    for season in seasons:
        measures = _fetch_measures(
            measure_types=PLAYER_MEASURE_TYPES,
            endpoint_cls=endpoint_cls,
            endpoint_name=PLAYER_ENDPOINT_NAME,
            dataset_name=PLAYER_DATASET_NAME,
            season=season,
            cache=cache,
            max_retries=max_retries,
            request_sleep_seconds=request_sleep_seconds,
            retry_sleep_seconds=retry_sleep_seconds,
            timeout=timeout,
        )
        frames.append(_build_player_frame(measures, season))

    result = pd.concat(frames, ignore_index=True)
    _validate_processed_schema(
        result,
        PLAYER_OUTPUT_COLUMNS,
        required_non_null=("season", "player_id", "player_name", "minutes"),
    )
    return result.loc[:, list(PLAYER_OUTPUT_COLUMNS)]


def _fetch_measures(
    *,
    measure_types: tuple[str, ...],
    endpoint_cls: EndpointFactory,
    endpoint_name: str,
    dataset_name: str,
    season: str,
    cache: JsonFileCache,
    max_retries: int,
    request_sleep_seconds: float,
    retry_sleep_seconds: float,
    timeout: int,
) -> dict[str, pd.DataFrame]:
    """Fetch each measure type for a season and return raw frames by measure."""
    measures: dict[str, pd.DataFrame] = {}
    for measure_type in measure_types:
        payload = fetch_cached_endpoint(
            endpoint_cls=endpoint_cls,
            endpoint_name=endpoint_name,
            params=_endpoint_params(season, measure_type),
            cache=cache,
            max_retries=max_retries,
            request_sleep_seconds=request_sleep_seconds,
            retry_sleep_seconds=retry_sleep_seconds,
            timeout=timeout,
        )
        frame = _payload_to_frame(payload, dataset_name)
        if frame.empty:
            raise ValueError(
                f"{dataset_name} ({measure_type}) returned no rows for {season}"
            )
        frame.columns = [str(column).lower() for column in frame.columns]
        measures[measure_type] = frame
    return measures


def fetch_cached_endpoint(
    *,
    endpoint_cls: EndpointFactory,
    endpoint_name: str,
    params: Mapping[str, Any],
    cache: JsonFileCache,
    max_retries: int = 3,
    request_sleep_seconds: float = 0.6,
    retry_sleep_seconds: float = 2.0,
    timeout: int = 30,
) -> dict[str, Any]:
    """Fetch an endpoint payload, using cache first and retrying live calls."""
    cached_payload = cache.get(endpoint_name, params)
    if cached_payload is not None:
        return cached_payload

    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            endpoint = endpoint_cls(**params, timeout=timeout)
            payload = endpoint.get_normalized_dict()
            if not isinstance(payload, dict):
                raise TypeError(f"{endpoint_name} returned {type(payload).__name__}")
            cache.set(endpoint_name, params, payload)
            if request_sleep_seconds > 0:
                time.sleep(request_sleep_seconds)
            return payload
        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last_error = exc
            if attempt == max_retries:
                break
            if retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds * attempt)

    raise RuntimeError(
        f"Failed to fetch {endpoint_name} after {max_retries} attempts"
    ) from last_error


def _build_team_frame(measures: dict[str, pd.DataFrame], season: str) -> pd.DataFrame:
    base = measures["Base"].set_index("team_id")
    advanced = measures["Advanced"].set_index("team_id")
    four = measures["Four Factors"].set_index("team_id")

    pulled_at = _utc_now_iso()
    out = pd.DataFrame(index=base.index)
    out["season"] = season
    out["team_id"] = base.index.astype("int64")
    out["team_name"] = base["team_name"]
    out["team_abbr"] = [team_abbr_from_id(int(tid)) for tid in base.index]
    out["wins"] = _num(base["w"])
    out["losses"] = _num(base["l"])
    out["off_rating"] = _num(advanced["off_rating"])
    out["def_rating"] = _num(advanced["def_rating"])
    out["net_rating"] = _num(advanced["net_rating"])
    out["pace"] = _num(advanced["pace"])
    out["efg_pct"] = _num(advanced["efg_pct"])
    out["tov_pct"] = _num(advanced["tm_tov_pct"])
    out["oreb_pct"] = _num(advanced["oreb_pct"])
    out["dreb_pct"] = _num(advanced["dreb_pct"])
    out["fta_rate"] = _num(four["fta_rate"])
    out["three_pa_rate"] = _safe_divide(_num(base["fg3a"]), _num(base["fga"]))
    out["three_p_pct"] = _num(base["fg3_pct"])
    out["source"] = TEAM_SOURCE
    out["pulled_at"] = pulled_at
    return out.reset_index(drop=True)


def _build_player_frame(measures: dict[str, pd.DataFrame], season: str) -> pd.DataFrame:
    base = measures["Base"].set_index("player_id")
    advanced = measures["Advanced"].set_index("player_id")

    pulled_at = _utc_now_iso()
    minutes = _num(base["min"])
    out = pd.DataFrame(index=base.index)
    out["season"] = season
    out["player_id"] = base.index.astype("int64")
    out["player_name"] = base["player_name"]
    out["team_abbr"] = base["team_abbreviation"]
    out["age"] = _num(base["age"])
    # Position is not exposed by this endpoint; flagged as missing, not invented.
    out["position"] = pd.NA
    out["minutes"] = minutes
    out["games"] = _num(base["gp"])
    out["pts"] = _num(base["pts"])
    out["reb"] = _num(base["reb"])
    out["ast"] = _num(base["ast"])
    out["usage_rate"] = _num(advanced["usg_pct"])
    out["true_shooting"] = _num(advanced["ts_pct"])
    out["three_pa"] = _num(base["fg3a"])
    out["three_pa_rate"] = _safe_divide(_num(base["fg3a"]), _num(base["fga"]))
    out["three_p_pct"] = _num(base["fg3_pct"])
    out["assist_pct"] = _num(advanced["ast_pct"])
    out["turnover_pct"] = _num(advanced["tm_tov_pct"])
    out["rebound_pct"] = _num(advanced["reb_pct"])
    # STL%/BLK% require opponent possessions and are not in this endpoint, so we
    # do not invent them; the true-rate columns stay null (missing-data flagged).
    # Raw steal/block/turnover totals are real and let downstream code derive
    # per-minute defensive proxies.
    out["steal_pct"] = pd.NA
    out["block_pct"] = pd.NA
    out["stl"] = _num(base["stl"])
    out["blk"] = _num(base["blk"])
    out["tov"] = _num(base["tov"])
    out["source"] = PLAYER_SOURCE
    out["pulled_at"] = pulled_at
    return out.reset_index(drop=True)


def season_range(start_season: str, end_season: str) -> tuple[str, ...]:
    """Return NBA season labels from start through end, inclusive."""
    start_year = _season_start_year(start_season)
    end_year = _season_start_year(end_season)
    if end_year < start_year:
        raise ValueError(
            f"end season {end_season} is before start season {start_season}"
        )

    return tuple(_season_label(year) for year in range(start_year, end_year + 1))


def infer_latest_season(today: date | None = None) -> str:
    """Infer the current NBA season label from a date."""
    current_date = date.today() if today is None else today
    start_year = current_date.year if current_date.month >= 7 else current_date.year - 1
    return _season_label(start_year)


def _endpoint_params(season: str, measure_type: str) -> dict[str, Any]:
    return {
        "season": season,
        "season_type_all_star": "Regular Season",
        "per_mode_detailed": "Totals",
        "measure_type_detailed_defense": measure_type,
    }


def _payload_to_frame(payload: Mapping[str, Any], dataset_name: str) -> pd.DataFrame:
    if dataset_name not in payload:
        raise ValueError(f"Response is missing dataset {dataset_name}")
    rows = payload[dataset_name]
    if not isinstance(rows, list):
        raise TypeError(f"Dataset {dataset_name} must be a list of row dictionaries")
    return pd.DataFrame(rows)


def _validate_processed_schema(
    frame: pd.DataFrame,
    required_columns: tuple[str, ...],
    *,
    required_non_null: tuple[str, ...],
) -> None:
    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Processed data is missing required columns: {missing}")

    null_columns = [
        column for column in required_non_null if frame[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"Processed data has null values in: {null_columns}")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.replace(0, pd.NA)
    return pd.to_numeric(numerator / denom, errors="coerce").astype("float64")


def _utc_now_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def _season_start_year(season: str) -> int:
    if not re.fullmatch(r"\d{4}-\d{2}", season):
        raise ValueError(f"Invalid NBA season label: {season}")

    start_text, end_text = season.split("-")
    start_year = int(start_text)
    expected_end = (start_year + 1) % 100
    if int(end_text) != expected_end:
        raise ValueError(f"Invalid NBA season label: {season}")
    return start_year


def _season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"
