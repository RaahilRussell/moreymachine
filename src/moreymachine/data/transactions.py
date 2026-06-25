"""Refresh and parse recent NBA transactions from a real public source.

Spotrac's NBA transactions page exposes a recent transaction list with dates,
players, teams, and source descriptions. This module caches the HTML response
and writes a normalized Parquet table. It never fabricates missing contract
fields; downstream candidate-status checks use the transaction text only to flag
stale status or manual review needs.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from moreymachine.utils.paths import (
    PLAYER_SEASONS_PATH,
    RAW_DATA_DIR,
    TRANSACTIONS_PATH,
)

SPOTRAC_TRANSACTIONS_URL = "https://www.spotrac.com/nba/transactions"
TRANSACTION_SOURCE = "Spotrac NBA Transactions"
TRANSACTION_DATA_MODE = "real_scraped"

TRANSACTION_COLUMNS = (
    "transaction_date",
    "player_name",
    "position",
    "spotrac_player_id",
    "player_id",
    "team_abbr",
    "from_team_abbr",
    "transaction_type",
    "description",
    "source",
    "source_url",
    "pulled_at",
    "data_mode",
)

STATUS_CHANGING_TYPES = frozenset(
    {
        "signing",
        "extension",
        "trade",
        "option_exercised",
        "option_declined",
        "free_agent_status_change",
        "waived",
        "released",
    }
)


@dataclass(frozen=True)
class TransactionsRefreshResult:
    """Summary of a transaction refresh."""

    rows: int
    start_date: date
    end_date: date
    output_path: Path
    source_url: str


def refresh_transactions(
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    output_path: str | Path = TRANSACTIONS_PATH,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    raw_dir: str | Path = RAW_DATA_DIR / "spotrac_transactions",
    refresh: bool = True,
    timeout: int = 25,
) -> TransactionsRefreshResult:
    """Fetch recent transactions, normalize them, and write Parquet output."""
    end = _coerce_date(end_date) or datetime.now(UTC).date()
    start = _coerce_date(start_date) or (end - timedelta(days=31))
    source_url = _source_url(start, end)
    html = _load_html(
        source_url,
        cache_path=_cache_path(raw_dir, start, end),
        refresh=refresh,
        timeout=timeout,
    )
    frame = parse_transactions_html(html, source_url=source_url)
    frame = _attach_nba_player_ids(frame, player_seasons_path)
    frame = frame.loc[:, list(TRANSACTION_COLUMNS)].sort_values(
        ["transaction_date", "player_name"],
        ascending=[False, True],
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)

    return TransactionsRefreshResult(
        rows=len(frame),
        start_date=start,
        end_date=end,
        output_path=output,
        source_url=source_url,
    )


def parse_transactions_html(html: str, *, source_url: str) -> pd.DataFrame:
    """Parse Spotrac transaction HTML into the canonical transaction schema."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select("#table-wrapper li.list-group-item"):
        player_link = item.find("a", href=lambda href: href and "/nba/player/" in href)
        detail = item.find("small")
        if player_link is None or detail is None:
            continue
        raw_name = player_link.get_text(" ", strip=True)
        name, position = _split_name_position(raw_name)
        text = detail.get_text(" ", strip=True)
        transaction_date, description = _split_date_description(text)
        if transaction_date is None or not name:
            continue
        rows.append(
            {
                "transaction_date": transaction_date.isoformat(),
                "player_name": name,
                "position": position,
                "spotrac_player_id": _spotrac_id(player_link.get("href", "")),
                "team_abbr": _team_to(description),
                "from_team_abbr": _team_from(description),
                "transaction_type": classify_transaction_type(description),
                "description": description,
                "source": TRANSACTION_SOURCE,
                "source_url": source_url,
                "pulled_at": datetime.now(UTC).isoformat(),
                "data_mode": TRANSACTION_DATA_MODE,
            }
        )
    if not rows:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)
    return pd.DataFrame(rows)


def classify_transaction_type(description: str) -> str:
    """Classify a source transaction description into a compact type."""
    text = str(description or "").lower()
    if "traded to" in text or " traded " in text:
        return "trade"
    if "declined" in text and "option" in text:
        return "option_declined"
    if "exercised" in text and "option" in text:
        return "option_exercised"
    if "extended" in text or "extension" in text:
        return "extension"
    if "agreed to" in text or "signed" in text or "re-signed" in text:
        return "signing"
    if "free agent" in text:
        return "free_agent_status_change"
    if "waived" in text:
        return "waived"
    if "released" in text:
        return "released"
    if "drafted" in text:
        return "draft"
    return "other"


def _load_html(
    source_url: str, *, cache_path: Path, refresh: bool, timeout: int
) -> str:
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    try:
        response = requests.get(
            source_url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; MoreyMachine/1.0; +local research)"
                )
            },
        )
        response.raise_for_status()
        html = response.text
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as exc:  # noqa: BLE001 - cached real HTML is acceptable
        if cache_path.exists():
            print(f"  [warn] transaction refresh failed ({exc}); using cached HTML.")
            return cache_path.read_text(encoding="utf-8")
        raise


def _attach_nba_player_ids(
    frame: pd.DataFrame, player_seasons_path: str | Path
) -> pd.DataFrame:
    result = frame.copy()
    result["player_id"] = pd.NA
    path = Path(player_seasons_path)
    if result.empty or not path.exists():
        return result
    players = pd.read_parquet(path)
    id_map = {
        _name_key(name): int(player_id)
        for name, player_id in zip(
            players["player_name"],
            players["player_id"],
            strict=False,
        )
        if pd.notna(player_id)
    }
    result["player_id"] = result["player_name"].map(
        lambda name: id_map.get(_name_key(name), pd.NA)
    )
    result["player_id"] = result["player_id"].astype("Int64")
    return result


def _source_url(start: date, end: date) -> str:
    return f"{SPOTRAC_TRANSACTIONS_URL}?start={start.isoformat()}&end={end.isoformat()}"


def _cache_path(raw_dir: str | Path, start: date, end: date) -> Path:
    return (
        Path(raw_dir) / f"nba_transactions_{start.isoformat()}_{end.isoformat()}.html"
    )


def _coerce_date(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return pd.to_datetime(value, errors="raise").date()


def _split_name_position(raw_name: str) -> tuple[str, str]:
    match = re.match(r"^(?P<name>.*?)\s*\((?P<position>[^)]*)\)\s*$", raw_name)
    if not match:
        return raw_name.strip(), ""
    return match.group("name").strip(), match.group("position").strip()


def _split_date_description(text: str) -> tuple[date | None, str]:
    match = re.match(
        r"^(?P<date>[A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+-\s+(?P<desc>.*)$", text
    )
    if not match:
        return None, text
    parsed = datetime.strptime(match.group("date"), "%b %d, %Y").date()
    return parsed, match.group("desc").strip()


def _team_to(description: str) -> str:
    patterns = (
        r"\bto\s+[^(]+\(([A-Z]{2,4})\)",
        r"\bwith\s+[^(]+\(([A-Z]{2,4})\)",
        r"\bby\s+[^(]+\(([A-Z]{2,4})\)",
        r"\bfrom\s+[^(]+\(([A-Z]{2,4})\)",
        r"\(([A-Z]{2,4})\)",
    )
    return _first_match(description, patterns)


def _team_from(description: str) -> str:
    return _first_match(description, (r"\bfrom\s+[^(]+\(([A-Z]{2,4})\)",))


def _first_match(description: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(1)
    return ""


def _spotrac_id(href: str) -> str:
    match = re.search(r"/id/(\d+)", href)
    return match.group(1) if match else ""


def _name_key(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_name.lower() if ch.isalnum())
