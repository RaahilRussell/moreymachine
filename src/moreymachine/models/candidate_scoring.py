"""Saturation-free candidate scoring built on the role engine + gap report.

The legacy ``fit_model`` scores saturated badly: ``contract_value`` hit 100 for
42% of players, ``portability`` hit 100 for 34%, and ``risk`` floored at 15 for
72%. The root causes were absolute linear formulas with no role context and a
risk model with a single constant base.

This engine rebuilds every score on percentile/role-relative footing:

* ``contract_value`` rewards *surplus* (quality percentile minus salary
  percentile), not cheapness alone, and never rewards a minimum-salary player
  who is not projected real rotation minutes.
* ``portability`` is percentile-scaled so a 100 is structurally rare.
* ``risk`` sums eight continuous, independent components (age, minutes,
  shooting sample, role uncertainty, contract, acquisition cost, missing data,
  playoff exposure) into a graded tier - no constant floor.
* ``contender_gain`` is minutes-aware: a bench player can no longer score 80.

It consumes the candidate universe joined with the role engine and emits one
scored row per player, including the per-gap breakdown the board explains.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from moreymachine.models.fit_model import DEFAULT_NEED_WEIGHTS, need_category_weights

# Projected rotation minutes share by role tier (fraction of available minutes).
MINUTES_SHARE_BY_TIER = {
    "Star": 0.70,
    "Starter": 0.55,
    "Rotation": 0.35,
    "Bench": 0.15,
    "Fringe": 0.05,
}

# How hard each candidate_type is to actually acquire (0-100, higher = easier).
ACQUISITION_FEASIBILITY = {
    "minimum_candidate": 90.0,
    "free_agent": 85.0,
    "mle_candidate": 80.0,
    "likely_free_agent": 70.0,
    "rookie_scale_trade_target": 62.0,
    "realistic_trade_target": 58.0,
    "manual_watchlist": 55.0,
    "expensive_trade_target": 38.0,
    "missing_contract_status": 25.0,
    "unavailable_core_player": 15.0,
    "star_unrealistic": 10.0,
}

# Acquisition-cost risk contribution by candidate_type (0-1).
ACQUISITION_COST_RISK = {
    "minimum_candidate": 0.12,
    "free_agent": 0.15,
    "mle_candidate": 0.22,
    "likely_free_agent": 0.30,
    "rookie_scale_trade_target": 0.30,
    "realistic_trade_target": 0.42,
    "manual_watchlist": 0.45,
    "expensive_trade_target": 0.62,
    "missing_contract_status": 0.70,
    "unavailable_core_player": 0.82,
    "star_unrealistic": 0.90,
}

SCORE_COLUMNS = (
    "need_match",
    "contender_gain",
    "portability",
    "portability_tier",
    "contract_value",
    "contract_value_tier",
    "acquisition_feasibility",
    "risk_score",
    "risk_tier",
    "final_fit",
    "expected_minutes_share",
    "expected_rotation_role",
    "surplus_score",
    "gaps_addressed",
    "gap_specific_scores",
    "why_need_match",
)


def score_candidates(
    candidates: pd.DataFrame,
    *,
    roster_gaps: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return ``candidates`` with all fit/risk/value scores and gap breakdowns."""
    if candidates.empty:
        empty = candidates.copy()
        for column in SCORE_COLUMNS:
            empty[column] = pd.Series(dtype="object")
        return empty

    frame = candidates.reset_index(drop=True).copy()
    weights = (
        need_category_weights(roster_gaps)
        if roster_gaps is not None and not roster_gaps.empty
        else DEFAULT_NEED_WEIGHTS.copy()
    )

    category_scores = _need_category_scores(frame)
    portability, portability_tier = _portability(frame)
    frame["portability"] = portability
    category_scores["playoff_portability_proxy"] = portability

    expected_share, expected_role = _expected_minutes(frame)
    feasibility = frame["candidate_type"].map(ACQUISITION_FEASIBILITY).fillna(45.0)
    contract_value, surplus = _contract_value(frame, expected_share)
    contender_gain = _contender_gain(frame, portability, expected_share, feasibility)
    need_match, gaps_addressed, gap_scores_json, why_need = _need_match(
        category_scores, weights
    )
    risk_score, risk_tier = _risk(
        frame, portability=portability, expected_share=expected_share
    )

    final_fit = _final_fit(
        need_match=need_match,
        contender_gain=contender_gain,
        portability=portability,
        contract_value=contract_value,
        feasibility=feasibility,
        risk_score=risk_score,
    )

    frame["need_match"] = need_match.round(1)
    frame["contender_gain"] = contender_gain.round(1)
    frame["portability"] = portability.round(1)
    frame["portability_tier"] = portability_tier
    frame["contract_value"] = contract_value.round(1)
    frame["contract_value_tier"] = _contract_value_tier(contract_value)
    frame["acquisition_feasibility"] = feasibility.round(1)
    frame["risk_score"] = risk_score.round(1)
    frame["risk_tier"] = risk_tier
    frame["final_fit"] = final_fit.round(1)
    frame["expected_minutes_share"] = expected_share.round(3)
    frame["expected_rotation_role"] = expected_role
    frame["surplus_score"] = surplus.round(1)
    frame["gaps_addressed"] = gaps_addressed
    frame["gap_specific_scores"] = gap_scores_json
    frame["why_need_match"] = why_need
    return frame


# --------------------------------------------------------------------------- #
# Component scores
# --------------------------------------------------------------------------- #
def _need_category_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Map role dimensions to a 0-100 score for each roster-gap category."""
    spacing = _dim(frame, "spacing_score")
    movement = _dim(frame, "movement_shooting_score")
    creation = _dim(frame, "creation_score")
    connector = _dim(frame, "connector_score")
    low_usage = _dim(frame, "low_usage_fit")
    rim_pressure = _dim(frame, "rim_pressure_score")
    wing_def = _dim(frame, "wing_defense_proxy")
    rim_protect = _dim(frame, "rim_protection_proxy")
    rebounding = _dim(frame, "rebounding_score")
    sample = _dim(frame, "sample_reliability")
    minutes_pct = _rank01(_num(frame, "minutes")) * 100

    defense = (wing_def + rim_protect) / 2.0
    scores = pd.DataFrame(index=frame.index)
    scores["shooting_pressure"] = 0.6 * spacing + 0.4 * movement
    scores["role_player_shooting"] = 0.5 * movement + 0.3 * low_usage + 0.2 * spacing
    scores["defense"] = defense
    scores["rebounding"] = rebounding
    scores["turnover_control"] = 0.6 * connector + 0.4 * low_usage
    scores["pace_transition"] = 0.6 * rim_pressure + 0.4 * wing_def
    scores["bench_rotation_depth"] = 0.5 * sample + 0.5 * minutes_pct
    scores["usage_concentration"] = 0.55 * creation + 0.45 * connector
    return scores.clip(0, 100)


def _portability(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Percentile-scaled portability so a perfect 100 is structurally rare."""
    spacing = _dim(frame, "spacing_score")
    movement = _dim(frame, "movement_shooting_score")
    low_usage = _dim(frame, "low_usage_fit")
    wing_def = _dim(frame, "wing_defense_proxy")
    rim_protect = _dim(frame, "rim_protection_proxy")
    rebounding = _dim(frame, "rebounding_score")
    sample = _dim(frame, "sample_reliability")
    cs_volume = _rank01(_num(frame, "catch_shoot_fg3a")) * 100
    low_tov = 100 - _scale_ratio(_num(frame, "turnover_pct"), low=0.07, high=0.18) * 100

    raw = (
        0.26 * np.maximum(movement, spacing)
        + 0.14 * cs_volume
        + 0.16 * low_usage
        + 0.14 * low_tov
        + 0.18 * ((wing_def + rim_protect + rebounding) / 3.0)
        + 0.12 * sample
    )
    # Percentile-rank the blend so only the top sliver reaches 95+.
    portability = (_rank01(raw) * 100).round(1)
    tier = pd.cut(
        portability,
        bins=[-0.1, 30, 50, 70, 88, 100.1],
        labels=["Low", "Questionable", "Playable", "Strong", "Elite"],
    ).astype(str)
    return portability, tier


def _expected_minutes(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Project a rotation tier and minutes share from quality + minutes played."""
    quality = _num(frame, "quality_percentile").fillna(0.0)
    minutes = _num(frame, "minutes").fillna(0.0)
    minutes_pct = _rank01(minutes)
    blended = (0.7 * quality + 0.3 * minutes_pct).clip(0, 1)

    role = pd.Series("Fringe", index=frame.index)
    role = role.mask(blended >= 0.35, "Bench")
    role = role.mask(blended >= 0.55, "Rotation")
    role = role.mask(blended >= 0.75, "Starter")
    role = role.mask(blended >= 0.90, "Star")
    share = role.map(MINUTES_SHARE_BY_TIER).astype(float)
    return share, role


def _contract_value(
    frame: pd.DataFrame, expected_share: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Reward surplus (role value above pay), not cheapness; mute idle minimums."""
    role_value_pct = _num(frame, "quality_percentile").fillna(0.0)
    salary = _num(frame, "salary_millions")
    salary_pct = _rank01(salary.fillna(salary.median()))
    surplus = (role_value_pct - salary_pct).clip(-1, 1)

    cost_penalty = (
        frame["candidate_type"]
        .map(
            {
                "expensive_trade_target": 8.0,
                "star_unrealistic": 12.0,
                "unavailable_core_player": 10.0,
                "realistic_trade_target": 4.0,
                "rookie_scale_trade_target": 2.0,
            }
        )
        .fillna(0.0)
    )

    contract_value = 50 + 45 * surplus - cost_penalty
    # A minimum-salary player not projected real rotation minutes is not a
    # "great value" - pull their score back toward neutral instead of 100.
    idle_minimum = (expected_share <= MINUTES_SHARE_BY_TIER["Fringe"]) & (
        salary.fillna(99) <= 2.6
    )
    contract_value = contract_value.where(
        ~idle_minimum, 50 + 0.5 * (contract_value - 50)
    )
    # No contract row -> value cannot be judged; sit at a neutral, honest 50.
    contract_value = contract_value.where(salary.notna(), 50.0)
    surplus_score = (50 + 50 * surplus).clip(0, 100)
    return contract_value.clip(0, 100), surplus_score


def _contract_value_tier(contract_value: pd.Series) -> pd.Series:
    return pd.cut(
        contract_value,
        bins=[-0.1, 35, 50, 65, 80, 100.1],
        labels=["Overpaid", "Fair", "Solid value", "Bargain", "Steal"],
    ).astype(str)


def _contender_gain(
    frame: pd.DataFrame,
    portability: pd.Series,
    expected_share: pd.Series,
    feasibility: pd.Series,
) -> pd.Series:
    """Minutes-aware contention lift: a bench piece cannot score like a starter."""
    quality = _num(frame, "quality_percentile").fillna(0.0)
    minutes_factor = (expected_share / MINUTES_SHARE_BY_TIER["Star"]).clip(0, 1)
    portability_modifier = 0.6 + 0.4 * (portability / 100.0)
    feasibility_modifier = 0.7 + 0.3 * (feasibility / 100.0)
    gain = (
        100.0
        * minutes_factor
        * (0.5 + 0.5 * quality)
        * portability_modifier
        * feasibility_modifier
    )
    return gain.clip(0, 100)


def _need_match(
    category_scores: pd.DataFrame,
    weights: dict[str, float],
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Weight per-category fit by gap severity; surface the gaps each player answers."""
    active = {k: max(0.0, float(v)) for k, v in weights.items() if k in category_scores}
    total = sum(active.values()) or 1.0
    need = pd.Series(0.0, index=category_scores.index)
    for key, weight in active.items():
        need += category_scores[key] * (weight / total)

    ranked_gaps = sorted(active.items(), key=lambda kv: kv[1], reverse=True)
    top_gap_keys = [k for k, v in ranked_gaps if v > 0][:4]

    gaps_addressed: list[str] = []
    gap_scores_json: list[str] = []
    why: list[str] = []
    for idx in category_scores.index:
        addressed = [
            _pretty(key) for key in top_gap_keys if category_scores.at[idx, key] >= 60
        ]
        gaps_addressed.append("; ".join(addressed) if addressed else "none")
        gap_scores_json.append(
            json.dumps(
                {
                    _pretty(key): round(float(category_scores.at[idx, key]), 1)
                    for key in top_gap_keys
                }
            )
        )
        if addressed:
            why.append(f"Answers top Sixers gaps: {', '.join(addressed)}.")
        else:
            lead = top_gap_keys[0] if top_gap_keys else "team need"
            why.append(f"Does not move the needle on the top gap ({_pretty(lead)}).")
    return (
        need.clip(0, 100),
        pd.Series(gaps_addressed, index=category_scores.index),
        pd.Series(gap_scores_json, index=category_scores.index),
        pd.Series(why, index=category_scores.index),
    )


def _risk(
    frame: pd.DataFrame,
    *,
    portability: pd.Series,
    expected_share: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Eight continuous risk components -> graded 0-100 score with a tier."""
    age = _num(frame, "age")
    minutes = _num(frame, "minutes").fillna(0.0)
    three_pa = _num(frame, "three_pa").fillna(0.0)
    years = _num(frame, "years_remaining").fillna(0.0)
    salary = _num(frame, "salary_millions").fillna(0.0)
    sample = _dim(frame, "sample_reliability")

    age_risk = age.apply(_age_risk)
    minutes_risk = (1 - (minutes / 2000.0)).clip(0, 1)
    shooting_sample_risk = (1 - (three_pa / 250.0)).clip(0, 1)
    role_uncertainty = (
        0.6 * frame.get("role_confidence", "medium").map(_confidence_risk).fillna(0.4)
        + 0.4 * (1 - sample / 100.0)
    ).clip(0, 1)
    contract_risk = ((salary / 35.0) * (years.clip(0, 4) / 4.0)).clip(0, 1)
    acquisition_risk = frame["candidate_type"].map(ACQUISITION_COST_RISK).fillna(0.45)
    missing_risk = frame.get("missing_data_flags", "none").apply(_missing_risk)
    playoff_risk = (1 - portability / 100.0).clip(0, 1)

    risk = 100 * (
        0.14 * age_risk
        + 0.16 * minutes_risk
        + 0.10 * shooting_sample_risk
        + 0.14 * role_uncertainty
        + 0.10 * contract_risk
        + 0.16 * acquisition_risk
        + 0.08 * missing_risk
        + 0.12 * playoff_risk
    )
    risk = risk.clip(0, 100)

    unknown = missing_risk >= 0.75
    tier = pd.cut(
        risk,
        bins=[-0.1, 25, 45, 65, 100.1],
        labels=["Low", "Medium", "High", "Severe"],
    ).astype(str)
    tier = tier.where(~unknown, "Unknown")
    return risk, tier


def _final_fit(
    *,
    need_match: pd.Series,
    contender_gain: pd.Series,
    portability: pd.Series,
    contract_value: pd.Series,
    feasibility: pd.Series,
    risk_score: pd.Series,
) -> pd.Series:
    base = (
        0.30 * need_match
        + 0.25 * contender_gain
        + 0.20 * portability
        + 0.15 * contract_value
        + 0.10 * feasibility
    )
    return (base - 0.20 * risk_score).clip(0, 100)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _age_risk(age: float) -> float:
    if pd.isna(age):
        return 0.35
    if 24 <= age <= 29:
        return 0.10
    if age < 24:
        return min(0.7, 0.10 + (24 - age) * 0.10)
    return min(0.9, 0.10 + (age - 29) * 0.10)


def _confidence_risk(value: object) -> float:
    return {"high": 0.10, "medium": 0.40, "low": 0.80}.get(str(value).lower(), 0.40)


def _missing_risk(value: object) -> float:
    text = str(value or "none").lower()
    if text in ("", "none"):
        return 0.0
    return min(1.0, text.count(";") * 0.25 + 0.25)


def _pretty(key: str) -> str:
    return str(key).replace("_", " ")


def _dim(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce").fillna(50.0).clip(0, 100)
    return pd.Series(50.0, index=frame.index)


def _num(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(np.nan, index=frame.index)


def _rank01(series: pd.Series) -> pd.Series:
    ranked = series.rank(pct=True)
    return ranked.fillna(ranked.median() if ranked.notna().any() else 0.5)


def _scale_ratio(series: pd.Series, *, low: float, high: float) -> pd.Series:
    values = series.copy()
    values = values.where(values.abs() <= 1.5, values / 100.0)
    scaled = ((values - low) / (high - low)).clip(0, 1)
    return scaled.fillna(0.5)
