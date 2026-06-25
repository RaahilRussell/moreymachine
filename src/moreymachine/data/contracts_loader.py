"""Load real contracts into an explicit, unambiguous salary schema.

The old ``contracts.parquet`` carried a single ``salary`` column whose meaning
was ambiguous - cap hit, base salary, AAV, or minimum charge. This loader fixes
that by treating the Basketball-Reference scrape as what it actually is - a
**cap-hit** figure for the current season - and refusing to invent the rest.

Base salary, AAV, option details, free-agency type (UFA/RFA), and extensions are
NOT in the public scrape, so they are left missing and flagged, and can be filled
in from a real manual import at ``data/manual/contracts.csv`` (template written by
``scripts/build_contracts.py``). Contract status is mapped to an explicit category
set from only what is known: salary level, draft year, and years remaining.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from moreymachine.data.fetch_contracts import BBREF_CONTRACTS_URL, build_contracts
from moreymachine.utils.paths import (
    CONTRACTS_PATH,
    MANUAL_CONTRACTS_PATH,
    PLAYER_BIO_PATH,
    PLAYER_SEASONS_PATH,
    RAW_CONTRACTS_PATH,
)

# Explicit contract status categories. Only the categories derivable from the
# public scrape are assigned automatically; UFA/RFA, options, and extensions
# require a real manual import (we never guess free-agency type).
CONTRACT_STATUS_CATEGORIES = (
    "unrestricted_free_agent",
    "restricted_free_agent",
    "team_option",
    "player_option",
    "signed_short_term",
    "signed_long_term",
    "rookie_scale",
    "extension_signed",
    "max_or_near_max",
    "minimum_contract",
    "unknown",
)

MAX_NEAR_MAX_M = 40.0
MINIMUM_M = 2.6
ROOKIE_SCALE_MAX_M = 13.0
ROOKIE_RECENT_YEARS = 4

RICH_CONTRACT_COLUMNS = (
    "player_name",
    "player_id",
    "current_team",
    "contract_status",
    "base_salary_millions",
    "cap_hit_millions",
    "contract_aav_millions",
    "salary",
    "years_remaining",
    "option_status",
    "free_agent_year",
    "extension_status",
    "salary_source",
    "source_url",
    "pulled_at",
    "data_mode",
    "effective_date",
    "missing_data_flags",
    "salary_context",
)

# Columns a manual row may override (anything non-empty wins over the scrape).
MANUAL_OVERRIDE_COLUMNS = (
    "contract_status",
    "base_salary_millions",
    "cap_hit_millions",
    "contract_aav_millions",
    "years_remaining",
    "option_status",
    "free_agent_year",
    "extension_status",
    "salary_source",
    "source_url",
)


@dataclass(frozen=True)
class ContractsLoadResult:
    """Summary of a rich-contracts build."""

    rows: int
    matched_player_ids: int
    manual_overrides: int
    status_counts: dict[str, int]
    output_path: Path


def build_rich_contracts(
    *,
    refresh: bool = True,
    manual_path: str | Path = MANUAL_CONTRACTS_PATH,
    player_seasons_path: str | Path = PLAYER_SEASONS_PATH,
    player_bio_path: str | Path = PLAYER_BIO_PATH,
    output_path: str | Path = CONTRACTS_PATH,
) -> ContractsLoadResult:
    """Scrape real contracts, normalize to the rich schema, merge manual reals."""
    raw = _load_raw_contracts(refresh=refresh)
    bio = _optional(player_bio_path)
    season = _latest_season(player_seasons_path)

    rich = _normalize(raw, bio=bio, season=season)
    rich, overrides = _apply_manual(rich, manual_path)
    rich = rich.loc[:, list(RICH_CONTRACT_COLUMNS)].reset_index(drop=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rich.to_parquet(output, index=False)

    return ContractsLoadResult(
        rows=len(rich),
        matched_player_ids=int(rich["player_id"].notna().sum()),
        manual_overrides=overrides,
        status_counts=rich["contract_status"].value_counts().to_dict(),
        output_path=output,
    )


def _load_raw_contracts(*, refresh: bool) -> pd.DataFrame:
    """Scrape to the raw cache; degrade to the previous raw cache on failure."""
    try:
        build_contracts(output_path=RAW_CONTRACTS_PATH, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 - keep cached real data, never fake
        if not RAW_CONTRACTS_PATH.exists():
            raise
        print(f"  [warn] contracts scrape failed ({exc}); using cached raw contracts.")
    return pd.read_parquet(RAW_CONTRACTS_PATH)


def _normalize(
    raw: pd.DataFrame, *, bio: pd.DataFrame | None, season: str
) -> pd.DataFrame:
    frame = raw.copy()
    cap_hit = pd.to_numeric(frame.get("salary"), errors="coerce")
    frame["cap_hit_millions"] = (cap_hit / 1_000_000).round(3)
    frame["salary"] = cap_hit
    # Base salary and AAV are not in the public scrape - missing, not invented.
    frame["base_salary_millions"] = np.nan
    frame["contract_aav_millions"] = np.nan

    draft_year = _draft_year_map(bio)
    frame["_draft_year"] = frame["player_id"].map(draft_year)
    season_start = _season_start_year(season)
    years_remaining = pd.to_numeric(frame.get("years_remaining"), errors="coerce")
    frame["years_remaining"] = years_remaining
    frame["free_agent_year"] = (season_start + years_remaining.fillna(1)).astype(
        "Int64"
    )

    frame["contract_status"] = frame.apply(
        lambda r: _derive_status(
            cap_hit_m=r["cap_hit_millions"],
            old_status=str(r.get("contract_status", "")),
            years_remaining=r["years_remaining"],
            draft_year=r["_draft_year"],
            season_start=season_start,
        ),
        axis=1,
    )
    frame["option_status"] = (
        frame.get("option_status", "").replace("", "none").fillna("none")
    )
    frame["extension_status"] = "unknown"
    frame["current_team"] = frame.get("team", "")
    frame["salary_source"] = frame.get("source", BBREF_CONTRACTS_URL)
    frame["source_url"] = BBREF_CONTRACTS_URL
    frame["effective_date"] = season
    frame["missing_data_flags"] = frame.apply(_missing_flags, axis=1)
    frame["salary_context"] = frame.apply(_salary_context, axis=1)
    return frame


def _derive_status(
    *,
    cap_hit_m: float,
    old_status: str,
    years_remaining: float,
    draft_year: float,
    season_start: int,
) -> str:
    if pd.isna(cap_hit_m):
        return "unknown"
    recent_draft = (
        pd.notna(draft_year) and draft_year >= season_start - ROOKIE_RECENT_YEARS
    )
    if cap_hit_m >= MAX_NEAR_MAX_M:
        return "max_or_near_max"
    if recent_draft and cap_hit_m <= ROOKIE_SCALE_MAX_M:
        return "rookie_scale"
    if cap_hit_m <= MINIMUM_M:
        return "minimum_contract"
    if pd.notna(years_remaining) and years_remaining <= 1:
        return "signed_short_term"
    if pd.notna(years_remaining) and years_remaining >= 2:
        return "signed_long_term"
    if old_status == "expiring":
        return "signed_short_term"
    return "unknown"


def _apply_manual(
    rich: pd.DataFrame, manual_path: str | Path
) -> tuple[pd.DataFrame, int]:
    path = Path(manual_path)
    if not path.exists():
        return rich, 0
    manual = pd.read_csv(path)
    if manual.empty:
        return rich, 0

    overrides = 0
    rich = rich.copy()
    rich["_key"] = rich["player_id"].map(_safe_int)
    manual["_key"] = manual.get("player_id", pd.Series(dtype="object")).map(_safe_int)
    name_key = {
        _norm(n): i for i, n in zip(rich.index, rich["player_name"], strict=False)
    }

    for record in manual.to_dict(orient="records"):
        idx = _match_index(record, rich, name_key)
        if idx is None:
            continue
        changed = False
        for column in MANUAL_OVERRIDE_COLUMNS:
            value = record.get(column)
            if value is not None and str(value).strip() not in ("", "nan"):
                rich.at[idx, column] = value
                changed = True
        if changed:
            overrides += 1
            rich.at[idx, "data_mode"] = "real_manual"
            rich.at[idx, "salary_source"] = str(
                record.get("salary_source") or "manual contracts.csv"
            )
            rich.at[idx, "missing_data_flags"] = _missing_flags(rich.loc[idx])
            rich.at[idx, "salary_context"] = _salary_context(rich.loc[idx])
    return rich.drop(columns=["_key"]), overrides


def _missing_flags(row: pd.Series) -> str:
    flags = []
    if pd.isna(row.get("cap_hit_millions")):
        flags.append("cap hit missing")
    if pd.isna(row.get("base_salary_millions")):
        flags.append("base salary not in public source")
    if pd.isna(row.get("contract_aav_millions")):
        flags.append("AAV not in public source")
    if str(row.get("contract_status")) == "unknown":
        flags.append("contract status unknown")
    if str(row.get("option_status", "none")) == "none":
        flags.append("option status not in public source")
    return "; ".join(flags) if flags else "none"


def _salary_context(row: pd.Series) -> str:
    cap = row.get("cap_hit_millions")
    status = str(row.get("contract_status", "unknown")).replace("_", " ")
    if pd.isna(cap):
        return f"No cap figure matched; contract status {status}."
    fa = row.get("free_agent_year")
    fa_text = f" Reaches free agency ~{int(fa)}." if pd.notna(fa) else ""
    return (
        f"${float(cap):.1f}M cap hit ({status}); base salary and AAV are not in the "
        f"public source.{fa_text}"
    )


def _draft_year_map(bio: pd.DataFrame | None) -> dict:
    if bio is None or "draft_year" not in bio.columns:
        return {}
    valid = bio.dropna(subset=["player_id"])
    return dict(
        zip(
            valid["player_id"].map(_safe_int),
            pd.to_numeric(valid["draft_year"], errors="coerce"),
            strict=False,
        )
    )


def _match_index(record: dict, rich: pd.DataFrame, name_key: dict) -> int | None:
    key = _safe_int(record.get("player_id"))
    if key is not None:
        hits = rich.index[rich["_key"] == key]
        if len(hits):
            return int(hits[0])
    return name_key.get(_norm(str(record.get("player_name", ""))))


def _latest_season(player_seasons_path: str | Path) -> str:
    path = Path(player_seasons_path)
    if not path.exists():
        return f"{datetime.now(UTC).year}-{(datetime.now(UTC).year + 1) % 100:02d}"
    seasons = pd.read_parquet(path, columns=["season"])["season"].astype(str)
    return sorted(seasons.unique())[-1]


def _season_start_year(season: str) -> int:
    digits = "".join(ch for ch in season[:4] if ch.isdigit())
    return int(digits) if digits else datetime.now(UTC).year


def _safe_int(value: object) -> int | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(number) else int(number)


def _norm(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _optional(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None
