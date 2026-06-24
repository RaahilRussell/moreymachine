"""Real NBA playoff results, encoded as auditable bracket data.

Each completed season lists the 16 playoff teams by the round they were
eliminated in; every other franchise that season is tier 0 (missed playoffs).
These are public, verifiable historical results (NBA.com / Basketball
Reference) — not invented. The current season (whose playoffs have not yet
resolved at the project's knowledge cutoff) is intentionally absent: MoreyMachine
treats it as the unlabeled evaluation season rather than fabricating an outcome.

Tier definitions (matching ``playoff_tiers.PLAYOFF_TIER_DEFINITIONS``):
    0 missed playoffs | 1 lost first round | 2 lost second round
    3 lost conference finals | 4 lost finals | 5 champion
"""

from __future__ import annotations

import pandas as pd

from moreymachine.data.team_lookup import TEAM_ID_TO_ABBR

ALL_TEAMS: tuple[str, ...] = tuple(sorted(set(TEAM_ID_TO_ABBR.values())))

TIER_RESULT_TEXT = {
    0: "Missed playoffs",
    1: "Lost first round",
    2: "Lost second round (conference semifinals)",
    3: "Lost conference finals",
    4: "Lost NBA Finals",
    5: "NBA champion",
}

# season -> {champion, runner_up, conf_finals(2), conf_semis(4), first_round(8)}
PLAYOFF_BRACKETS: dict[str, dict[str, object]] = {
    "2015-16": {
        "champion": "CLE",
        "runner_up": "GSW",
        "conf_finals": ("TOR", "OKC"),
        "conf_semis": ("ATL", "MIA", "POR", "SAS"),
        "first_round": ("DET", "IND", "CHA", "BOS", "HOU", "MEM", "DAL", "LAC"),
    },
    "2016-17": {
        "champion": "GSW",
        "runner_up": "CLE",
        "conf_finals": ("BOS", "SAS"),
        "conf_semis": ("WAS", "TOR", "HOU", "UTA"),
        "first_round": ("IND", "MIL", "ATL", "CHI", "POR", "MEM", "OKC", "LAC"),
    },
    "2017-18": {
        "champion": "GSW",
        "runner_up": "CLE",
        "conf_finals": ("BOS", "HOU"),
        "conf_semis": ("PHI", "TOR", "UTA", "NOP"),
        "first_round": ("IND", "MIL", "MIA", "WAS", "SAS", "MIN", "OKC", "POR"),
    },
    "2018-19": {
        "champion": "TOR",
        "runner_up": "GSW",
        "conf_finals": ("MIL", "POR"),
        "conf_semis": ("BOS", "PHI", "HOU", "DEN"),
        "first_round": ("DET", "ORL", "BKN", "IND", "LAC", "OKC", "SAS", "UTA"),
    },
    "2019-20": {
        "champion": "LAL",
        "runner_up": "MIA",
        "conf_finals": ("DEN", "BOS"),
        "conf_semis": ("LAC", "HOU", "TOR", "MIL"),
        "first_round": ("POR", "UTA", "DAL", "OKC", "ORL", "IND", "PHI", "BKN"),
    },
    "2020-21": {
        "champion": "MIL",
        "runner_up": "PHX",
        "conf_finals": ("ATL", "LAC"),
        "conf_semis": ("BKN", "PHI", "UTA", "DEN"),
        "first_round": ("MIA", "BOS", "NYK", "WAS", "LAL", "DAL", "MEM", "POR"),
    },
    "2021-22": {
        "champion": "GSW",
        "runner_up": "BOS",
        "conf_finals": ("MIA", "DAL"),
        "conf_semis": ("MIL", "PHI", "PHX", "MEM"),
        "first_round": ("ATL", "BKN", "CHI", "TOR", "NOP", "UTA", "DEN", "MIN"),
    },
    "2022-23": {
        "champion": "DEN",
        "runner_up": "MIA",
        "conf_finals": ("BOS", "LAL"),
        "conf_semis": ("NYK", "PHI", "GSW", "PHX"),
        "first_round": ("MIL", "ATL", "BKN", "CLE", "MIN", "MEM", "SAC", "LAC"),
    },
    "2023-24": {
        "champion": "BOS",
        "runner_up": "DAL",
        "conf_finals": ("IND", "MIN"),
        "conf_semis": ("CLE", "NYK", "DEN", "OKC"),
        "first_round": ("MIA", "ORL", "MIL", "PHI", "LAC", "PHX", "LAL", "NOP"),
    },
    "2024-25": {
        "champion": "OKC",
        "runner_up": "IND",
        "conf_finals": ("MIN", "NYK"),
        "conf_semis": ("DEN", "GSW", "BOS", "CLE"),
        "first_round": ("MIA", "MIL", "DET", "ORL", "MEM", "LAL", "HOU", "LAC"),
    },
}

_BRACKET_TIERS = (
    ("champion", 5, 1),
    ("runner_up", 4, 1),
    ("conf_finals", 3, 2),
    ("conf_semis", 2, 4),
    ("first_round", 1, 8),
)


def completed_seasons() -> tuple[str, ...]:
    """Return the seasons with known, encoded playoff outcomes."""
    return tuple(PLAYOFF_BRACKETS.keys())


def build_playoff_tier_rows() -> pd.DataFrame:
    """Expand bracket data to one validated tier row per team-season."""
    records: list[dict[str, object]] = []
    for season, bracket in PLAYOFF_BRACKETS.items():
        tier_by_team = _season_tiers(season, bracket)
        for team in ALL_TEAMS:
            tier = tier_by_team.get(team, 0)
            records.append(
                {
                    "season": season,
                    "team_abbr": team,
                    "playoff_tier": tier,
                    "playoff_result": TIER_RESULT_TEXT[tier],
                    "source_note": (
                        f"NBA.com / Basketball-Reference {season} playoff results"
                    ),
                }
            )
    frame = pd.DataFrame.from_records(records)
    return frame.sort_values(["season", "team_abbr"]).reset_index(drop=True)


def _season_tiers(season: str, bracket: dict[str, object]) -> dict[str, int]:
    tier_by_team: dict[str, int] = {}
    for key, tier, expected_count in _BRACKET_TIERS:
        teams = bracket[key]
        teams = (teams,) if isinstance(teams, str) else tuple(teams)
        if len(teams) != expected_count:
            raise ValueError(
                f"{season} {key} expected {expected_count} teams, got {len(teams)}"
            )
        for team in teams:
            if team not in ALL_TEAMS:
                raise ValueError(f"{season} {key} has unknown team: {team}")
            if team in tier_by_team:
                raise ValueError(f"{season} lists {team} in two rounds")
            tier_by_team[team] = tier
    if len(tier_by_team) != 16:
        raise ValueError(f"{season} must have exactly 16 playoff teams")
    return tier_by_team
