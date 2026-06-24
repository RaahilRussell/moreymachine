"""Rank player acquisition candidates by transparent fit scoring."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from moreymachine.features.player_archetypes import (
    PLAYER_ARCHETYPES_PATH,
    PLAYER_SEASONS_BASIC_PATH,
)
from moreymachine.features.playoff_portability import (
    score_player_playoff_portability,
)
from moreymachine.features.roster_gaps import ROSTER_GAPS_PATH
from moreymachine.models.contender_model import CONTENDER_MODEL_PATH
from moreymachine.utils.paths import REPORTS_DATA_DIR

CANDIDATE_FIT_RANKINGS_PATH = REPORTS_DATA_DIR / "candidate_fit_rankings.parquet"
DEFAULT_RISK_PENALTY_WEIGHT = 0.20

REQUIRED_OUTPUT_COLUMNS = (
    "player_name",
    "current_team",
    "position",
    "archetype",
    "fit_score",
    "need_match",
    "contender_gain",
    "portability",
    "contract_value",
    "risk_score",
    "recommendation",
    "why_fit",
    "concerns",
)

# Full output schema = the required scoring columns plus provenance and
# missing-data transparency columns the app surfaces per candidate.
OUTPUT_COLUMNS = (
    *REQUIRED_OUTPUT_COLUMNS,
    "season",
    "player_id",
    "candidate_type",
    "salary_millions",
    "salary_source",
    "data_sources",
    "missing_data_flags",
)

DEFAULT_NEED_WEIGHTS = {
    "shooting_pressure": 0.18,
    "role_player_shooting": 0.18,
    "defense": 0.14,
    "rebounding": 0.10,
    "turnover_control": 0.10,
    "pace_transition": 0.07,
    "bench_rotation_depth": 0.10,
    "usage_concentration": 0.05,
    "playoff_portability_proxy": 0.08,
}


@dataclass(frozen=True)
class CandidateFitBuildResult:
    """Summary of a completed candidate fit ranking run."""

    rows: int
    output_path: Path
    top_candidate: str | None


def build_candidate_rankings(
    *,
    player_stats_path: str | Path = PLAYER_SEASONS_BASIC_PATH,
    roster_gaps_path: str | Path = ROSTER_GAPS_PATH,
    player_archetypes_path: str | Path | None = PLAYER_ARCHETYPES_PATH,
    contracts_path: str | Path | None = None,
    candidates_path: str | Path | None = None,
    contender_model_path: str | Path | None = CONTENDER_MODEL_PATH,
    output_path: str | Path = CANDIDATE_FIT_RANKINGS_PATH,
    season: str | None = None,
    top_n: int | None = None,
) -> CandidateFitBuildResult:
    """Load candidate inputs, rank players, and save the ranking as Parquet."""
    player_stats = _read_table(player_stats_path)
    roster_gaps = _read_table(roster_gaps_path)
    player_archetypes = _read_optional_table(player_archetypes_path)
    contracts = _read_optional_table(contracts_path)
    candidates = _read_optional_table(candidates_path)
    contender_context = _read_optional_contender_model(contender_model_path)

    rankings = rank_candidates(
        player_stats,
        roster_gaps=roster_gaps,
        player_archetypes=player_archetypes,
        contracts=contracts,
        candidates=candidates,
        contender_model_context=contender_context,
        season=season,
    )
    if top_n is not None:
        rankings = rankings.head(top_n).copy()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rankings.to_parquet(output, index=False)

    top_candidate = None
    if not rankings.empty:
        top_candidate = str(rankings["player_name"].iloc[0])
    return CandidateFitBuildResult(
        rows=len(rankings),
        output_path=output,
        top_candidate=top_candidate,
    )


def rank_candidates(
    player_stats: pd.DataFrame,
    *,
    roster_gaps: pd.DataFrame,
    player_archetypes: pd.DataFrame | None = None,
    contracts: pd.DataFrame | None = None,
    candidates: pd.DataFrame | None = None,
    contender_model_context: Mapping[str, Any] | None = None,
    season: str | None = None,
) -> pd.DataFrame:
    """Rank candidate players by need, contender fit, portability, value, and risk."""
    pool = _candidate_pool(player_stats, season=season)
    pool = _restrict_to_watchlist(pool, candidates)
    pool = _merge_player_context(pool, player_archetypes)
    pool = _merge_player_context(pool, contracts)
    candidates = pool
    need_weights = need_category_weights(roster_gaps)

    rows = []
    for candidate in candidates.to_dict(orient="records"):
        portability = _portability_score(candidate)
        need_match = candidate_need_match_score(candidate, need_weights, portability)
        contender_gain = contender_similarity_gain_score(
            candidate,
            need_match=need_match,
            portability=portability,
            contender_model_context=contender_model_context,
        )
        contract_value = contract_value_score(
            candidate,
            need_match=need_match,
            contender_gain=contender_gain,
            portability=portability,
        )
        risk_score = candidate_risk_score(candidate)
        fit_score = calculate_gm_fit_score(
            contender_similarity_gain_normalized=contender_gain,
            need_match=need_match,
            playoff_portability=portability,
            contract_value=contract_value,
            risk_score=risk_score,
        )
        recommendation = recommendation_label(
            fit_score=fit_score,
            risk_score=risk_score,
            contract_value=contract_value,
        )
        why_fit, concerns = candidate_fit_explanation(
            candidate,
            need_weights=need_weights,
            need_match=need_match,
            contender_gain=contender_gain,
            portability=portability,
            contract_value=contract_value,
            risk_score=risk_score,
        )
        rows.append(
            {
                "player_name": _text(
                    candidate,
                    ("player_name", "name", "player"),
                    default="Unknown Player",
                ),
                "current_team": _text(
                    candidate,
                    ("current_team", "team_abbreviation", "team_abbr", "team"),
                    default="",
                ),
                "position": _text(
                    candidate,
                    ("position", "player_position", "pos"),
                    default="",
                ),
                "archetype": _text(
                    candidate,
                    ("archetype", "archetype_name", "cluster_name"),
                    default="Unknown",
                ),
                "fit_score": fit_score,
                "need_match": need_match,
                "contender_gain": contender_gain,
                "portability": portability,
                "contract_value": contract_value,
                "risk_score": risk_score,
                "recommendation": recommendation,
                "why_fit": why_fit,
                "concerns": concerns,
                "season": _text(candidate, ("season",), default=""),
                "player_id": _text(candidate, ("player_id",), default=""),
                "candidate_type": _text(
                    candidate, ("candidate_type",), default="manual_watchlist"
                ),
                "salary_millions": _salary_millions(candidate),
                "salary_source": _text(candidate, ("salary_source",), default=""),
                "data_sources": _candidate_data_sources(candidate),
                "missing_data_flags": _candidate_missing_data_flags(candidate),
            }
        )

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return (
        pd.DataFrame(rows)
        .sort_values(["fit_score", "need_match", "portability"], ascending=False)
        .reset_index(drop=True)
        .loc[:, OUTPUT_COLUMNS]
    )


def calculate_gm_fit_score(
    *,
    contender_similarity_gain_normalized: float,
    need_match: float,
    playoff_portability: float,
    contract_value: float,
    risk_score: float,
    risk_penalty_weight: float = DEFAULT_RISK_PENALTY_WEIGHT,
) -> float:
    """Calculate the final GM Fit Score from the requested component formula."""
    score = (
        0.35 * _clip(contender_similarity_gain_normalized)
        + 0.25 * _clip(need_match)
        + 0.20 * _clip(playoff_portability)
        + 0.20 * _clip(contract_value)
        - risk_penalty_weight * _clip(risk_score)
    )
    return round(_clip(score), 1)


def need_category_weights(roster_gaps: pd.DataFrame) -> dict[str, float]:
    """Return normalized target need weights from roster gap severities."""
    if roster_gaps.empty or "category_key" not in roster_gaps:
        return DEFAULT_NEED_WEIGHTS.copy()

    gaps = roster_gaps.copy()
    if "gap_size" in gaps:
        gaps = gaps[pd.to_numeric(gaps["gap_size"], errors="coerce").fillna(0) > 0]
    if gaps.empty or "severity_score" not in gaps:
        return DEFAULT_NEED_WEIGHTS.copy()

    severity = (
        gaps.assign(
            severity_score=pd.to_numeric(gaps["severity_score"], errors="coerce")
        )
        .dropna(subset=["severity_score"])
        .groupby("category_key")["severity_score"]
        .max()
    )
    severity = severity[severity > 0]
    if severity.empty:
        return DEFAULT_NEED_WEIGHTS.copy()

    weights = {key: 0.0 for key in DEFAULT_NEED_WEIGHTS}
    total = float(severity.sum())
    for category_key, value in severity.items():
        weights[str(category_key)] = float(value / total)
    return weights


def candidate_need_match_score(
    candidate: Mapping[str, Any],
    need_weights: Mapping[str, float],
    portability: float | None = None,
) -> float:
    """Score how directly a player answers the target team's roster gaps."""
    contributions = {
        "shooting_pressure": _shooting_pressure_score(candidate),
        "role_player_shooting": _role_player_shooting_score(candidate),
        "defense": _defense_score(candidate),
        "rebounding": _rebounding_score(candidate),
        "turnover_control": _turnover_control_score(candidate),
        "pace_transition": _pace_transition_score(candidate),
        "bench_rotation_depth": _rotation_depth_score(candidate),
        "usage_concentration": _usage_fit_score(candidate),
        "playoff_portability_proxy": _clip(
            portability if portability is not None else _portability_score(candidate)
        ),
    }
    total_weight = sum(max(0.0, float(value)) for value in need_weights.values())
    if total_weight <= 0:
        need_weights = DEFAULT_NEED_WEIGHTS
        total_weight = sum(need_weights.values())

    score = 0.0
    for category_key, contribution in contributions.items():
        weight = max(0.0, float(need_weights.get(category_key, 0.0)))
        score += contribution * weight
    return round(_clip(score / total_weight), 1)


def contender_similarity_gain_score(
    candidate: Mapping[str, Any],
    *,
    need_match: float,
    portability: float,
    contender_model_context: Mapping[str, Any] | None = None,
) -> float:
    """Estimate contender similarity gain from transparent candidate traits."""
    archetype_prior = _archetype_contender_prior(candidate)
    score = (0.45 * need_match) + (0.35 * portability) + (0.20 * archetype_prior)
    if contender_model_context:
        score = (0.95 * score) + (0.05 * max(need_match, portability))
    return round(_clip(score), 1)


def contract_value_score(
    candidate: Mapping[str, Any],
    *,
    need_match: float,
    contender_gain: float,
    portability: float,
) -> float:
    """Score whether the candidate's value profile is attractive for the price."""
    salary = _salary_millions(candidate)
    if salary is None:
        return 55.0

    value_score = (need_match + contender_gain + portability) / 3
    contract_value = 100 - (2.0 * salary) + (0.70 * (value_score - 50))
    return round(_clip(contract_value), 1)


def candidate_risk_score(candidate: Mapping[str, Any]) -> float:
    """Score candidate downside risk on a 0-100 scale."""
    risk = 15.0
    minutes = _number(candidate, ("minutes", "min", "mp"))
    age = _number(candidate, ("age",))
    usage = _ratio(candidate, ("usage_rate", "usage_percentage", "usg_pct", "usg"))
    efficiency = _shooting_efficiency(candidate)
    turnover = _turnover_rate(candidate)
    three_point_rate = _three_point_attempt_rate(candidate)
    three_point_percentage = _ratio(
        candidate,
        ("three_point_percentage", "three_point_pct", "three_p_pct", "fg3_pct"),
    )
    defensive_metric = _number(
        candidate,
        ("defensive_box_plus_minus", "dbpm", "defensive_estimated_plus_minus"),
    )
    defensive_rating = _number(
        candidate,
        ("defensive_rating", "def_rating", "def_rtg", "drtg"),
    )
    salary = _salary_millions(candidate)

    if _is_known(minutes):
        if minutes < 500:
            risk += 25
        elif minutes < 1000:
            risk += 12
    if _is_known(age):
        if age < 21:
            risk += 10
        elif age > 34:
            risk += 15
        elif age > 32:
            risk += 8
    if _is_known(usage) and _is_known(efficiency):
        if usage >= 0.30 and efficiency < 0.53:
            risk += 25
        elif usage >= 0.26 and efficiency < 0.55:
            risk += 15
    if _is_known(turnover):
        if turnover >= 0.18:
            risk += 18
        elif turnover >= 0.15:
            risk += 10
    if (
        _is_known(three_point_percentage)
        and three_point_percentage >= 0.36
        and (not _is_known(three_point_rate) or three_point_rate < 0.20)
    ):
        risk += 15
    if _is_known(defensive_metric) and defensive_metric <= -1.0:
        risk += 12
    if _is_known(defensive_rating) and defensive_rating >= 118:
        risk += 10
    if _is_known(salary) and salary >= 35:
        risk += 10

    return round(_clip(risk), 1)


def recommendation_label(
    *,
    fit_score: float,
    risk_score: float,
    contract_value: float,
) -> str:
    """Assign a front-office recommendation label."""
    if fit_score >= 80 and risk_score <= 35:
        return "Priority target"
    if fit_score >= 70 and contract_value >= 45:
        return "Strong fit if affordable"
    if fit_score >= 60:
        return "Role-player target"
    if fit_score >= 50:
        return "Only if cheap"
    return "Avoid"


def candidate_fit_explanation(
    candidate: Mapping[str, Any],
    *,
    need_weights: Mapping[str, float],
    need_match: float,
    contender_gain: float,
    portability: float,
    contract_value: float,
    risk_score: float,
) -> tuple[str, str]:
    """Return concise why-fit and concern text for a candidate."""
    strengths = _top_need_strengths(candidate, need_weights)
    portability_result = score_player_playoff_portability(candidate)
    positive_bullets = [
        bullet for bullet in portability_result.bullets if not _negative_bullet(bullet)
    ][:2]
    why_parts = [
        f"Need match {need_match:.1f}",
        f"contender gain {contender_gain:.1f}",
        f"portability {portability:.1f}",
        *strengths,
        *positive_bullets,
    ]

    concern_parts = []
    if risk_score >= 45:
        concern_parts.append(f"Risk score {risk_score:.1f}")
    if contract_value < 45:
        concern_parts.append(f"Contract value {contract_value:.1f}")
    concern_parts.extend(
        bullet for bullet in portability_result.bullets if _negative_bullet(bullet)
    )
    if not concern_parts:
        concern_parts.append("No major rule-based concerns.")

    return "; ".join(why_parts[:6]), "; ".join(concern_parts[:5])


def _candidate_pool(player_stats: pd.DataFrame, *, season: str | None) -> pd.DataFrame:
    if player_stats.empty:
        return player_stats.copy()

    candidates = player_stats.copy()
    if season is not None and "season" in candidates.columns:
        candidates = candidates[candidates["season"].astype(str).eq(str(season))].copy()
    elif "season" in candidates.columns:
        candidates = _latest_player_rows(candidates)
    return candidates.reset_index(drop=True)


def _latest_player_rows(frame: pd.DataFrame) -> pd.DataFrame:
    sort_frame = frame.assign(_season_sort=frame["season"].map(_season_sort_key))
    player_keys = [column for column in ("player_id", "player_name") if column in frame]
    if not player_keys:
        return sort_frame.sort_values("_season_sort").drop(columns="_season_sort")
    return (
        sort_frame.sort_values("_season_sort")
        .drop_duplicates(subset=player_keys[:1], keep="last")
        .drop(columns="_season_sort")
    )


def _restrict_to_watchlist(
    pool: pd.DataFrame,
    candidates: pd.DataFrame | None,
) -> pd.DataFrame:
    """Restrict the candidate pool to a real watchlist and attach its columns.

    When a candidates table is supplied (e.g. from fetch_candidates.py or a
    manual import), only those players are ranked, and their candidate_type /
    salary / source columns are joined on. Without it, the whole season pool is
    ranked. Either way, only real player rows from nba_api are scored.
    """
    if candidates is None or candidates.empty or pool.empty:
        return pool

    keys = _merge_keys(pool, candidates)
    if not keys:
        return pool

    extra_columns = [
        column
        for column in candidates.columns
        if column in keys or column not in pool.columns
    ]
    watchlist = candidates.loc[:, extra_columns].drop_duplicates(subset=keys)
    return pool.merge(watchlist, on=keys, how="inner")


def _merge_player_context(
    players: pd.DataFrame,
    context: pd.DataFrame | None,
) -> pd.DataFrame:
    if context is None or context.empty or players.empty:
        return players

    keys = _merge_keys(players, context)
    if not keys:
        return players

    context_columns = [
        column
        for column in context.columns
        if column in keys or column not in players.columns
    ]
    right = context.loc[:, context_columns].drop_duplicates(subset=keys)
    return players.merge(right, on=keys, how="left")


def _merge_keys(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    candidates = (
        ["player_id", "season"],
        ["player_id"],
        ["player_name", "season"],
        ["player_name"],
    )
    for keys in candidates:
        if all(key in left.columns and key in right.columns for key in keys):
            return list(keys)
    return []


def _portability_score(candidate: Mapping[str, Any]) -> float:
    direct = _number(
        candidate,
        (
            "playoff_portability_score",
            "portability",
            "portability_score",
        ),
    )
    if _is_known(direct):
        return round(_clip(direct), 1)
    return score_player_playoff_portability(candidate).score


def _shooting_pressure_score(candidate: Mapping[str, Any]) -> float:
    return _mean_scores(
        (
            _scale(
                _three_point_attempt_rate(candidate),
                low=0.18,
                high=0.55,
            ),
            _scale(
                _ratio(
                    candidate,
                    (
                        "three_point_percentage",
                        "three_point_pct",
                        "three_p_pct",
                        "fg3_pct",
                    ),
                ),
                low=0.32,
                high=0.41,
            ),
            _scale(_shooting_efficiency(candidate), low=0.52, high=0.62),
        )
    )


def _role_player_shooting_score(candidate: Mapping[str, Any]) -> float:
    usage = _ratio(candidate, ("usage_rate", "usage_percentage", "usg_pct", "usg"))
    return _mean_scores(
        (
            _scale(_three_point_attempt_rate(candidate), low=0.18, high=0.55),
            _scale(
                _ratio(
                    candidate,
                    (
                        "three_point_percentage",
                        "three_point_pct",
                        "three_p_pct",
                        "fg3_pct",
                    ),
                ),
                low=0.32,
                high=0.41,
            ),
            _scale(usage, low=0.12, high=0.30, higher_is_better=False),
        )
    )


def _defense_score(candidate: Mapping[str, Any]) -> float:
    defensive_metric = _number(
        candidate,
        ("defensive_box_plus_minus", "dbpm", "defensive_estimated_plus_minus"),
    )
    defensive_rating = _number(
        candidate,
        ("defensive_rating", "def_rating", "def_rtg", "drtg"),
    )
    stock_rate = _combined_rate(
        candidate,
        ("steal_rate", "stl_rate"),
        ("block_rate", "blk_rate"),
        ("stl",),
        ("blk",),
    )
    return _mean_scores(
        (
            _scale(defensive_metric, low=-2.0, high=2.0),
            _scale(
                defensive_rating,
                low=108.0,
                high=120.0,
                higher_is_better=False,
            ),
            _scale(stock_rate, low=0.005, high=0.030),
            _scale(
                _ratio(
                    candidate,
                    (
                        "rebound_rate",
                        "rebound_percentage",
                        "rebound_pct",
                        "reb_pct",
                        "trb_pct",
                    ),
                ),
                low=0.05,
                high=0.16,
            ),
        )
    )


def _rebounding_score(candidate: Mapping[str, Any]) -> float:
    return _scale(
        _ratio(
            candidate,
            ("rebound_rate", "rebound_percentage", "rebound_pct", "reb_pct", "trb_pct"),
        ),
        low=0.05,
        high=0.18,
    )


def _turnover_control_score(candidate: Mapping[str, Any]) -> float:
    return _scale(
        _turnover_rate(candidate),
        low=0.08,
        high=0.20,
        higher_is_better=False,
    )


def _pace_transition_score(candidate: Mapping[str, Any]) -> float:
    steal_rate = _event_rate(candidate, ("steal_rate", "stl_rate"), ("stl",))
    age = _number(candidate, ("age",))
    age_score = None
    if _is_known(age):
        age_score = 80.0 if 22 <= age <= 30 else 55.0 if 20 <= age <= 33 else 40.0
    return _mean_scores(
        (
            _scale(steal_rate, low=0.005, high=0.025),
            age_score,
        )
    )


def _rotation_depth_score(candidate: Mapping[str, Any]) -> float:
    minutes = _number(candidate, ("minutes", "min", "mp"))
    games = _number(candidate, ("games_played", "gp", "games"))
    return _mean_scores(
        (
            _scale(minutes, low=500.0, high=2200.0),
            _scale(games, low=30.0, high=75.0),
        )
    )


def _usage_fit_score(candidate: Mapping[str, Any]) -> float:
    usage = _ratio(candidate, ("usage_rate", "usage_percentage", "usg_pct", "usg"))
    return _mean_scores(
        (
            _scale(usage, low=0.12, high=0.32, higher_is_better=False),
            _scale(_assist_rate(candidate), low=0.05, high=0.22),
            _scale(_shooting_efficiency(candidate), low=0.52, high=0.62),
        )
    )


def _archetype_contender_prior(candidate: Mapping[str, Any]) -> float:
    archetype = _text(
        candidate,
        ("archetype", "archetype_name", "cluster_name"),
        default="",
    ).lower()
    if any(
        label in archetype
        for label in (
            "3-and-d",
            "low-usage spacer",
            "connector",
            "rim protector",
            "stretch big",
        )
    ):
        return 82.0
    if "defensive specialist" in archetype or "rebounding big" in archetype:
        return 72.0
    if "high-usage creator" in archetype or "scoring guard" in archetype:
        return 58.0
    if archetype:
        return 62.0
    return 55.0


def _top_need_strengths(
    candidate: Mapping[str, Any],
    need_weights: Mapping[str, float],
) -> list[str]:
    category_scores = {
        "shooting pressure": _shooting_pressure_score(candidate),
        "role shooting": _role_player_shooting_score(candidate),
        "defense": _defense_score(candidate),
        "rebounding": _rebounding_score(candidate),
        "turnover control": _turnover_control_score(candidate),
        "rotation depth": _rotation_depth_score(candidate),
    }
    weighted = []
    for label, score in category_scores.items():
        key = label.replace(" ", "_")
        if label == "role shooting":
            key = "role_player_shooting"
        if label == "rotation depth":
            key = "bench_rotation_depth"
        weight = float(need_weights.get(key, 0))
        weighted.append((label, score * weight, score))

    strengths = []
    for label, _, score in sorted(weighted, key=lambda item: item[1], reverse=True):
        if score >= 70:
            strengths.append(f"answers {label}")
        if len(strengths) == 2:
            break
    return strengths


def _negative_bullet(bullet: str) -> bool:
    text = bullet.lower()
    negative_terms = (
        "risk",
        "poor",
        "weak",
        "limited",
        "vulnerable",
        "tiny",
        "inefficient",
        "concern",
        "fragility",
        "one-dimensional",
        "fake shooting",
    )
    return any(term in text for term in negative_terms)


def _read_table(path: str | Path) -> pd.DataFrame:
    table_path = Path(path)
    if table_path.suffix.lower() == ".csv":
        return pd.read_csv(table_path)
    return pd.read_parquet(table_path)


def _read_optional_table(path: str | Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    table_path = Path(path)
    if not table_path.exists():
        return None
    return _read_table(table_path)


def _read_optional_contender_model(path: str | Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    model_path = Path(path)
    if not model_path.exists():
        return None
    payload = joblib.load(model_path)
    if isinstance(payload, Mapping):
        return payload
    return {"model": payload}


def _salary_millions(candidate: Mapping[str, Any]) -> float | None:
    salary = _number(
        candidate,
        (
            "salary_millions",
            "estimated_salary_millions",
            "annual_salary_millions",
            "salary",
            "expected_salary",
            "estimated_salary",
            "contract_estimate",
            "annual_salary",
            "aav",
        ),
    )
    if not _is_known(salary):
        return None
    if salary > 1000:
        salary = salary / 1_000_000
    return salary


def _candidate_data_sources(candidate: Mapping[str, Any]) -> str:
    """Describe the real provenance backing a candidate's scores."""
    sources = ["Player stats: nba_api LeagueDash (NBA.com Stats)"]
    salary_source = _text(candidate, ("salary_source",), default="")
    if salary_source:
        sources.append(f"Salary: {salary_source}")
    archetype = _text(candidate, ("archetype", "archetype_name"), default="")
    if archetype:
        sources.append("Archetype: KMeans player clustering")
    return "; ".join(sources)


def _candidate_missing_data_flags(candidate: Mapping[str, Any]) -> str:
    """List exactly which real inputs are missing for this candidate."""
    flags: list[str] = []
    if _salary_millions(candidate) is None:
        flags.append("salary missing (contract value falls back to fit proxy)")
    if not _is_known(_ratio(candidate, ("usage_rate", "usg_pct"))):
        flags.append("usage rate missing")
    if not _is_known(
        _ratio(candidate, ("three_point_percentage", "three_p_pct", "fg3_pct"))
    ):
        flags.append("3-point percentage missing")
    if not _text(candidate, ("position", "pos"), default=""):
        flags.append("position not provided by source")
    minutes = _number(candidate, ("minutes", "min", "mp"))
    if _is_known(minutes) and minutes < 500:
        flags.append("small minutes sample")
    return "; ".join(flags) if flags else "none"


def _shooting_efficiency(candidate: Mapping[str, Any]) -> float | None:
    direct = _ratio(
        candidate,
        ("true_shooting_percentage", "true_shooting", "ts_pct", "ts"),
    )
    if _is_known(direct):
        return direct

    points = _number(candidate, ("pts", "points"))
    fga = _number(candidate, ("fga", "field_goals_attempted"))
    fta = _number(candidate, ("fta", "free_throws_attempted"))
    if _is_known(points) and _is_known(fga) and _is_known(fta):
        denominator = 2 * (fga + (0.44 * fta))
        if denominator > 0:
            return points / denominator
    return _ratio(candidate, ("efg_percentage", "efg_pct", "fg_pct"))


def _three_point_attempt_rate(candidate: Mapping[str, Any]) -> float | None:
    direct = _ratio(
        candidate,
        (
            "three_point_attempt_rate",
            "three_pa_rate",
            "three_point_rate",
            "fg3a_rate",
            "threepar",
        ),
    )
    if _is_known(direct):
        return direct
    fg3a = _number(candidate, ("fg3a", "three_pointers_attempted"))
    fga = _number(candidate, ("fga", "field_goals_attempted"))
    if _is_known(fg3a) and _is_known(fga) and fga > 0:
        return fg3a / fga
    return None


def _turnover_rate(candidate: Mapping[str, Any]) -> float | None:
    direct = _ratio(
        candidate, ("turnover_rate", "turnover_percentage", "turnover_pct", "tov_pct")
    )
    if _is_known(direct):
        return direct
    turnovers = _number(candidate, ("tov", "turnovers"))
    fga = _number(candidate, ("fga", "field_goals_attempted"))
    fta = _number(candidate, ("fta", "free_throws_attempted"))
    if _is_known(turnovers) and _is_known(fga) and _is_known(fta):
        denominator = fga + (0.44 * fta) + turnovers
        if denominator > 0:
            return turnovers / denominator
    return _event_rate(candidate, (), ("tov", "turnovers"))


def _assist_rate(candidate: Mapping[str, Any]) -> float | None:
    direct = _ratio(
        candidate, ("assist_rate", "assist_percentage", "assist_pct", "ast_pct")
    )
    if _is_known(direct):
        return direct
    return _event_rate(candidate, (), ("ast", "assists"))


def _combined_rate(
    candidate: Mapping[str, Any],
    first_direct_aliases: tuple[str, ...],
    second_direct_aliases: tuple[str, ...],
    first_count_aliases: tuple[str, ...],
    second_count_aliases: tuple[str, ...],
) -> float | None:
    first = _event_rate(candidate, first_direct_aliases, first_count_aliases)
    second = _event_rate(candidate, second_direct_aliases, second_count_aliases)
    if _is_known(first) and _is_known(second):
        return first + second
    if _is_known(first):
        return first
    if _is_known(second):
        return second
    return None


def _event_rate(
    candidate: Mapping[str, Any],
    direct_aliases: tuple[str, ...],
    count_aliases: tuple[str, ...],
) -> float | None:
    direct = _ratio(candidate, direct_aliases)
    if _is_known(direct):
        return direct
    count = _number(candidate, count_aliases)
    minutes = _number(candidate, ("minutes", "min", "mp"))
    if _is_known(count) and _is_known(minutes) and minutes > 0:
        return count / minutes
    return None


def _scale(
    value: float | None,
    *,
    low: float,
    high: float,
    higher_is_better: bool = True,
) -> float | None:
    if not _is_known(value):
        return None
    if high == low:
        return 50.0
    score = (float(value) - low) / (high - low) * 100
    if not higher_is_better:
        score = 100 - score
    return _clip(score)


def _mean_scores(scores: tuple[float | None, ...]) -> float:
    valid_scores = [score for score in scores if _is_known(score)]
    if not valid_scores:
        return 50.0
    return round(_clip(sum(valid_scores) / len(valid_scores)), 1)


def _number(candidate: Mapping[str, Any], aliases: tuple[str, ...]) -> float | None:
    value = _raw_value(candidate, aliases)
    if value is None:
        return None
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _ratio(candidate: Mapping[str, Any], aliases: tuple[str, ...]) -> float | None:
    value = _number(candidate, aliases)
    if value is None:
        return None
    if abs(value) > 1.5:
        return value / 100
    return value


def _text(
    candidate: Mapping[str, Any],
    aliases: tuple[str, ...],
    *,
    default: str,
) -> str:
    value = _raw_value(candidate, aliases)
    if value is None or pd.isna(value):
        return default
    return str(value)


def _raw_value(candidate: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).lower(): key for key in candidate.keys()}
    for alias in aliases:
        key = normalized.get(alias.lower())
        if key is not None:
            return candidate[key]
    return None


def _season_sort_key(value: Any) -> int:
    match = re.search(r"\d{4}", str(value))
    if match is None:
        return -1
    return int(match.group(0))


def _clip(value: float | None, low: float = 0.0, high: float = 100.0) -> float:
    if not _is_known(value):
        return 50.0
    return max(low, min(high, float(value)))


def _is_known(value: float | None) -> bool:
    return value is not None and not pd.isna(value)
