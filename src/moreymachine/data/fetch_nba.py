"""Fetch and clean NBA API season-level team and player stats."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
from nba_api.stats.endpoints.leaguedashplayerstats import LeagueDashPlayerStats
from nba_api.stats.endpoints.leaguedashteamstats import LeagueDashTeamStats

from moreymachine.data.cache import JsonFileCache
from moreymachine.utils.paths import NBA_API_RAW_DIR, PROCESSED_DATA_DIR

START_SEASON = "2015-16"
TEAM_ENDPOINT_NAME = "leaguedashteamstats"
PLAYER_ENDPOINT_NAME = "leaguedashplayerstats"
TEAM_DATASET_NAME = "LeagueDashTeamStats"
PLAYER_DATASET_NAME = "LeagueDashPlayerStats"

BASE_STAT_COLUMNS = (
    "GP",
    "W",
    "L",
    "W_PCT",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "TOV",
    "STL",
    "BLK",
    "BLKA",
    "PF",
    "PFD",
    "PTS",
    "PLUS_MINUS",
)
TEAM_BASIC_COLUMNS = ("TEAM_ID", "TEAM_NAME", *BASE_STAT_COLUMNS)
PLAYER_BASIC_COLUMNS = (
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "AGE",
    *BASE_STAT_COLUMNS,
)
TEAM_REQUIRED_PROCESSED_COLUMNS = tuple(column.lower() for column in TEAM_BASIC_COLUMNS)
PLAYER_REQUIRED_PROCESSED_COLUMNS = tuple(
    column.lower() for column in PLAYER_BASIC_COLUMNS
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


def fetch_nba_basic_data(
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
    """Fetch team/player season stats and write cleaned Parquet outputs."""
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

    team_path = processed_path / "team_seasons_basic.parquet"
    player_path = processed_path / "player_seasons_basic.parquet"
    team_frame.to_parquet(team_path, index=False)
    player_frame.to_parquet(player_path, index=False)

    return FetchResult(
        seasons=seasons,
        team_rows=len(team_frame),
        player_rows=len(player_frame),
        team_path=team_path,
        player_path=player_path,
    )


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
    """Fetch and clean team stats for each requested season."""
    frames = []
    for season in seasons:
        payload = fetch_cached_endpoint(
            endpoint_cls=endpoint_cls,
            endpoint_name=TEAM_ENDPOINT_NAME,
            params=_endpoint_params(season),
            cache=cache,
            max_retries=max_retries,
            request_sleep_seconds=request_sleep_seconds,
            retry_sleep_seconds=retry_sleep_seconds,
            timeout=timeout,
        )
        frame = _payload_to_frame(payload, TEAM_DATASET_NAME)
        _validate_raw_schema(frame, TEAM_BASIC_COLUMNS, TEAM_DATASET_NAME, season)
        frames.append(_clean_basic_frame(frame, season, TEAM_BASIC_COLUMNS))

    result = pd.concat(frames, ignore_index=True)
    _validate_processed_schema(
        result,
        ("season", *TEAM_REQUIRED_PROCESSED_COLUMNS),
        required_non_null=("season", "team_id", "team_name"),
    )
    return result


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
    """Fetch and clean player stats for each requested season."""
    frames = []
    for season in seasons:
        payload = fetch_cached_endpoint(
            endpoint_cls=endpoint_cls,
            endpoint_name=PLAYER_ENDPOINT_NAME,
            params=_endpoint_params(season),
            cache=cache,
            max_retries=max_retries,
            request_sleep_seconds=request_sleep_seconds,
            retry_sleep_seconds=retry_sleep_seconds,
            timeout=timeout,
        )
        frame = _payload_to_frame(payload, PLAYER_DATASET_NAME)
        _validate_raw_schema(frame, PLAYER_BASIC_COLUMNS, PLAYER_DATASET_NAME, season)
        frames.append(_clean_basic_frame(frame, season, PLAYER_BASIC_COLUMNS))

    result = pd.concat(frames, ignore_index=True)
    _validate_processed_schema(
        result,
        ("season", *PLAYER_REQUIRED_PROCESSED_COLUMNS),
        required_non_null=("season", "player_id", "player_name", "team_id"),
    )
    return result


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
        except Exception as exc:
            last_error = exc
            if attempt == max_retries:
                break
            if retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds * attempt)

    raise RuntimeError(
        f"Failed to fetch {endpoint_name} after {max_retries} attempts"
    ) from last_error


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


def _endpoint_params(season: str) -> dict[str, Any]:
    return {
        "season": season,
        "season_type_all_star": "Regular Season",
        "per_mode_detailed": "Totals",
        "measure_type_detailed_defense": "Base",
    }


def _payload_to_frame(payload: Mapping[str, Any], dataset_name: str) -> pd.DataFrame:
    if dataset_name not in payload:
        raise ValueError(f"Response is missing dataset {dataset_name}")
    rows = payload[dataset_name]
    if not isinstance(rows, list):
        raise TypeError(f"Dataset {dataset_name} must be a list of row dictionaries")
    return pd.DataFrame(rows)


def _clean_basic_frame(
    frame: pd.DataFrame,
    season: str,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    clean = frame.loc[:, columns].copy()
    clean.insert(0, "SEASON", season)
    clean.columns = [_to_snake_case(column) for column in clean.columns]

    string_columns = {
        "season",
        "team_name",
        "player_name",
        "team_abbreviation",
    }
    for column in clean.columns:
        if column not in string_columns:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")
    return clean


def _validate_raw_schema(
    frame: pd.DataFrame,
    required_columns: tuple[str, ...],
    dataset_name: str,
    season: str,
) -> None:
    if frame.empty:
        raise ValueError(f"{dataset_name} returned no rows for {season}")

    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(
            f"{dataset_name} for {season} is missing required columns: {missing}"
        )


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


def _to_snake_case(value: str) -> str:
    return value.lower()
