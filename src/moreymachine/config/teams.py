"""Team configuration and output-path helpers."""

from __future__ import annotations

from pathlib import Path

from moreymachine.utils.paths import DATA_DIR, MANUAL_DATA_DIR

TEAM_OUTPUTS_DIR = DATA_DIR / "team_outputs"
TEAM_CONTEXT_DIR = MANUAL_DATA_DIR / "team_context"

DEFAULT_TEAM = "PHI"
GENERIC_TEAM_CONTEXT = "GENERIC"

SUPPORTED_TEAM_ABBRS = (
    "ATL",
    "BOS",
    "BKN",
    "CHA",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHX",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
)

TEAM_NAMES = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}


def normalize_team(team: str | None) -> str:
    """Return a normalized NBA team abbreviation."""
    value = str(team or DEFAULT_TEAM).strip().upper()
    return value or DEFAULT_TEAM


def team_name(team: str) -> str:
    """Return a display name for a team abbreviation."""
    return TEAM_NAMES.get(normalize_team(team), normalize_team(team))


def team_output_dir(team: str) -> Path:
    """Return the root output directory for a team."""
    return TEAM_OUTPUTS_DIR / normalize_team(team)


def ensure_team_output_dirs(team: str) -> dict[str, Path]:
    """Create and return standard team output directories."""
    root = team_output_dir(team)
    dirs = {
        "root": root,
        "features": root / "features",
        "reports": root / "reports",
        "narratives": root / "narratives",
        "scouting_reports": root / "scouting_reports",
        "metadata": root / "metadata",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
