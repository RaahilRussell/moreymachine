"""Build a real contracts table from Basketball-Reference (or a manual CSV).

Salaries and contract length come from Basketball-Reference's public player
contracts page (``data_mode = real_scraped``). When the live page cannot be
fetched, the cached HTML is reused; when even that is unavailable, the builder
falls back to ``data/manual/contracts.csv`` (``data_mode = manual_sourced``).

What is and isn't asserted:

* ``salary`` (first guaranteed year) and ``years_remaining`` (count of listed
  paid years) are read directly from the source - never invented.
* ``contract_status`` is set to ``under_contract`` only because the player
  appears on the contracts page with a salary; ``expiring`` when only the first
  year is listed. Free-agent status is *never* inferred from absence.
* ``option_status`` is not exposed by this source, so it is left blank and
  flagged. It is the kind of field meant to be filled in the manual CSV.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from moreymachine.data.fetch_candidates import (
    BBREF_CONTRACTS_URL,
    _read_contracts_html,
)
from moreymachine.utils.paths import (
    CONTRACTS_PATH,
    MANUAL_CONTRACTS_PATH,
    PLAYER_SEASONS_PATH,
)

CONTRACTS_OUTPUT_COLUMNS = (
    "player_name",
    "player_id",
    "team",
    "salary",
    "years_remaining",
    "contract_status",
    "option_status",
    "source",
    "pulled_at",
    "data_mode",
)

YEAR_STATS = ("y1", "y2", "y3", "y4", "y5", "y6")


@dataclass(frozen=True)
class ContractsBuildResult:
    """Summary of a contracts build."""

    rows: int
    data_mode: str
    matched_player_ids: int
    output_path: Path


def build_contracts(
    *,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    manual_path: str | Path = MANUAL_CONTRACTS_PATH,
    output_path: str | Path = CONTRACTS_PATH,
    refresh: bool = True,
    timeout: int = 25,
) -> ContractsBuildResult:
    """Build contracts.parquet from a real source, with manual CSV fallback."""
    pulled_at = datetime.now(UTC).date().isoformat()
    frame, data_mode = _scrape_contracts(refresh=refresh, timeout=timeout)

    if frame is None:
        frame = _load_manual(manual_path)
        data_mode = "manual_sourced"

    if frame is None or frame.empty:
        raise FileNotFoundError(
            "No real contracts available. Could not reach Basketball-Reference "
            f"and {manual_path} is missing. Add real rows to that CSV."
        )

    frame["source"] = (
        BBREF_CONTRACTS_URL if data_mode == "real_scraped" else str(manual_path)
    )
    frame["pulled_at"] = pulled_at
    frame["data_mode"] = data_mode

    frame = _attach_player_ids(frame, player_seasons_path)
    frame = frame.loc[:, list(CONTRACTS_OUTPUT_COLUMNS)].reset_index(drop=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)

    matched = int(frame["player_id"].notna().sum())
    return ContractsBuildResult(
        rows=len(frame),
        data_mode=data_mode,
        matched_player_ids=matched,
        output_path=output,
    )


def _scrape_contracts(
    *, refresh: bool, timeout: int
) -> tuple[pd.DataFrame | None, str]:
    html = _read_contracts_html(refresh=refresh, timeout=timeout)
    if html is None:
        return None, "manual_sourced"
    try:
        frame = _parse_contracts_table(html)
    except Exception:  # noqa: BLE001 - never fabricate on a parse failure
        return None, "manual_sourced"
    if frame is None or frame.empty:
        return None, "manual_sourced"
    return frame, "real_scraped"


def _parse_contracts_table(html: str) -> pd.DataFrame | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="player-contracts")
    if table is None or table.find("tbody") is None:
        return None

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        name_cell = tr.find(["th", "td"], attrs={"data-stat": "player"})
        if name_cell is None:
            continue
        name = name_cell.get_text(strip=True)
        if not name:
            continue
        team_cell = tr.find("td", attrs={"data-stat": "team_id"})
        team = team_cell.get_text(strip=True) if team_cell else ""
        years = {
            stat: _parse_salary(
                (tr.find("td", attrs={"data-stat": stat}) or _Empty()).get_text(
                    strip=True
                )
            )
            for stat in YEAR_STATS
        }
        salary = years["y1"]
        years_remaining = sum(1 for value in years.values() if value is not None)
        if salary is None and years_remaining == 0:
            continue
        rows.append(
            {
                "player_name": name,
                "team": team,
                "salary": salary,
                "years_remaining": years_remaining,
                "contract_status": (
                    "under_contract" if years_remaining > 1 else "expiring"
                ),
                "option_status": "",  # not exposed by source; fill in manual CSV
            }
        )
    if not rows:
        return None
    return pd.DataFrame(rows)


def _load_manual(manual_path: str | Path) -> pd.DataFrame | None:
    path = Path(manual_path)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    for column in ("player_name", "team", "salary", "years_remaining",
                   "contract_status", "option_status"):
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame


def _attach_player_ids(
    frame: pd.DataFrame, player_seasons_path: str | Path
) -> pd.DataFrame:
    frame = frame.copy()
    if "player_id" not in frame.columns:
        frame["player_id"] = pd.NA
    path = Path(player_seasons_path)
    if not path.exists():
        return frame
    players = pd.read_parquet(path)
    latest = sorted(players["season"].astype(str).unique())[-1]
    players = players[players["season"].astype(str).eq(latest)]
    id_by_name = {
        _normalize_name(str(name)): int(pid)
        for name, pid in zip(players["player_name"], players["player_id"])
    }
    frame["player_id"] = frame.apply(
        lambda row: row["player_id"]
        if pd.notna(row.get("player_id"))
        else id_by_name.get(_normalize_name(str(row["player_name"])), pd.NA),
        axis=1,
    )
    frame["player_id"] = frame["player_id"].astype("Int64")
    return frame


class _Empty:
    @staticmethod
    def get_text(*_args, **_kwargs) -> str:
        return ""


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
