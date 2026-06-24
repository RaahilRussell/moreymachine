"""Build a real candidate watchlist with real salaries from online sources.

The candidate *pool* is sourced from the real nba_api player-seasons table
(rotation players in the latest season who are not already on the target team).
Salaries are pulled live from Basketball-Reference's player contracts page - a
real, public source - and matched to players by accent-insensitive name.

Hard rules honoured here:

* Contracts are never invented. A player with no matched salary gets a blank
  ``expected_salary`` and ``salary_source = "missing"`` plus a missing-data note.
* If the online salary fetch fails entirely, every salary is left missing and
  the candidate list still contains only real players, with guidance to fill
  ``expected_salary`` manually in ``data/manual/candidates.csv``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.utils.paths import CANDIDATES_PATH, PLAYER_SEASONS_PATH, RAW_DATA_DIR

BBREF_CONTRACTS_URL = "https://www.basketball-reference.com/contracts/players.html"
BBREF_CACHE_PATH = RAW_DATA_DIR / "basketball_reference" / "player_contracts.html"
DEFAULT_MIN_MINUTES = 1000.0

CANDIDATE_COLUMNS = (
    "player_name",
    "player_id",
    "current_team",
    "position",
    "candidate_type",
    "expected_salary",
    "salary_source",
    "source_note",
)


@dataclass(frozen=True)
class CandidateBuildResult:
    """Summary of a completed candidate watchlist build."""

    rows: int
    salaries_matched: int
    salary_source: str
    output_path: Path


def build_candidates_csv(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    output_path: str | Path = CANDIDATES_PATH,
    target_team: str = "PHI",
    min_minutes: float = DEFAULT_MIN_MINUTES,
    refresh_salaries: bool = True,
    timeout: int = 25,
) -> CandidateBuildResult:
    """Build data/manual/candidates.csv from real players and real salaries."""
    players = pd.read_parquet(player_seasons_path)
    pool = _candidate_pool(players, target_team=target_team, min_minutes=min_minutes)

    salary_by_key, salary_source = _load_salaries(
        refresh=refresh_salaries, timeout=timeout
    )

    rows = []
    matched = 0
    pulled_at = datetime.now(UTC).date().isoformat()
    for record in pool.to_dict(orient="records"):
        name = str(record["player_name"])
        salary = salary_by_key.get(_normalize_name(name))
        has_salary = salary is not None
        matched += int(has_salary)
        rows.append(
            {
                "player_name": name,
                "player_id": int(record["player_id"]),
                "current_team": str(record.get("team_abbr", "")),
                "position": "",  # not provided by nba_api LeagueDash endpoints
                "candidate_type": (
                    "trade_target" if has_salary else "manual_watchlist"
                ),
                "expected_salary": salary if has_salary else "",
                "salary_source": (
                    f"{salary_source} (pulled {pulled_at})" if has_salary else "missing"
                ),
                "source_note": (
                    "Pool: real nba_api rotation players (latest season, "
                    f">= {min_minutes:.0f} min, excluding {target_team}). "
                    + (
                        "Salary matched from Basketball-Reference contracts."
                        if has_salary
                        else "No salary matched online - add a real value manually."
                    )
                ),
            }
        )

    frame = pd.DataFrame(rows, columns=list(CANDIDATE_COLUMNS))
    frame = frame.sort_values("player_name").reset_index(drop=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)

    return CandidateBuildResult(
        rows=len(frame),
        salaries_matched=matched,
        salary_source=salary_source if matched else "missing",
        output_path=output,
    )


def _candidate_pool(
    players: pd.DataFrame,
    *,
    target_team: str,
    min_minutes: float,
) -> pd.DataFrame:
    if "season" not in players.columns:
        raise ValueError("player_seasons is missing the season column")
    latest_season = sorted(players["season"].astype(str).unique())[-1]
    pool = players[players["season"].astype(str).eq(latest_season)].copy()
    minutes = pd.to_numeric(pool.get("minutes"), errors="coerce")
    pool = pool[minutes >= min_minutes]
    if "team_abbr" in pool.columns:
        pool = pool[pool["team_abbr"].astype(str).str.upper() != target_team.upper()]
    return pool.reset_index(drop=True)


def _load_salaries(*, refresh: bool, timeout: int) -> tuple[dict[str, float], str]:
    """Return {normalized_name: salary_dollars} and a human-readable source."""
    html = _read_contracts_html(refresh=refresh, timeout=timeout)
    if html is None:
        return {}, "missing"
    try:
        salaries = _parse_bbref_contracts(html)
    except Exception:  # noqa: BLE001 - parsing is best-effort; never fabricate
        return {}, "missing"
    if not salaries:
        return {}, "missing"
    return salaries, f"Basketball-Reference contracts ({BBREF_CONTRACTS_URL})"


def _read_contracts_html(*, refresh: bool, timeout: int) -> str | None:
    cache = BBREF_CACHE_PATH
    if refresh:
        html = _download_contracts_html(timeout=timeout)
        if html is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(html, encoding="utf-8")
            return html
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    return None


def _download_contracts_html(*, timeout: int) -> str | None:
    try:
        import certifi
        import requests
    except ImportError:
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        )
    }
    try:
        response = requests.get(
            BBREF_CONTRACTS_URL,
            headers=headers,
            timeout=timeout,
            verify=certifi.where(),
        )
    except Exception:  # noqa: BLE001 - offline/blocked is handled by the caller
        return None
    if response.status_code != 200:
        return None
    response.encoding = "utf-8"
    return response.text


def _parse_bbref_contracts(html: str) -> dict[str, float]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="player-contracts")
    if table is None or table.find("tbody") is None:
        return {}

    salaries: dict[str, float] = {}
    for row in table.find("tbody").find_all("tr"):
        name_cell = row.find(["th", "td"], attrs={"data-stat": "player"})
        salary_cell = row.find("td", attrs={"data-stat": "y1"})
        if name_cell is None or salary_cell is None:
            continue
        name = name_cell.get_text(strip=True)
        salary_text = salary_cell.get_text(strip=True)
        salary = _parse_salary(salary_text)
        if name and salary is not None:
            salaries[_normalize_name(name)] = salary
    return salaries


def _parse_salary(text: str) -> float | None:
    cleaned = text.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_name.lower() if ch.isalnum())
