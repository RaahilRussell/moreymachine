"""Saturation-free, role-aware candidate scoring (max rebuild).

Six scores, every one percentile/role-relative and distribution-checked:

1. **Need match** - severity-weighted answer to PHI's real roster gaps.
2. **Contender gain** - marginal and minutes-aware: expected minutes share x need
   x role quality x portability x feasibility, so a bench player cannot post a
   star's contention lift.
3. **Portability** - percentile-scaled so >=95 is structurally rare (<=5%).
4. **Contract value** - role-relative surplus, never auto-100 for a minimum
   player who is not actually playable (<=10% >=95).
5. **Risk** - eight continuous components into a graded tier (no constant floor).
6. **Final fit** - 0.30 need + 0.25 gain + 0.20 portability + 0.15 value +
   0.10 feasibility - risk penalty (a *theoretical* fit for the watchlist).

Inputs are the candidate universe joined with the role engine (new role
dimensions + impact-gated ``expected_role``) and the roster-gap report.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

# Expected share of available minutes by impact-gated role. A bench/fringe
# player simply cannot occupy a star's minutes, capping his contention lift.
MINUTES_SHARE_BY_ROLE = {
    "Star": 0.70,
    "High-Level Starter": 0.60,
    "Starter": 0.50,
    "Rotation Player": 0.35,
    "Bench Specialist": 0.20,
    "Developmental": 0.10,
    "Fringe": 0.05,
    "Unknown": 0.05,
}

# Map each roster-gap category to the role dimension(s) that answer it.
def _category_scorers() -> dict:
    return {
        "shooting_pressure": lambda d: 0.6 * d("spacing_score")
        + 0.4 * d("catch_and_shoot_score"),
        "role_player_shooting": lambda d: 0.5 * d("catch_and_shoot_score")
        + 0.3 * d("low_usage_fit_score")
        + 0.2 * d("spacing_score"),
        "role_player_shooting_volume": lambda d: d("catch_and_shoot_score"),
        "real_spacing": lambda d: 0.7 * d("spacing_score")
        + 0.3 * d("catch_and_shoot_score"),
        "defense": lambda d: (
            d("wing_defense_proxy")
            + d("rim_protection_proxy")
            + d("point_of_attack_defense_proxy")
        )
        / 3.0,
        "wing_defensive_depth": lambda d: d("wing_defense_proxy"),
        "point_of_attack_defense": lambda d: d("point_of_attack_defense_proxy"),
        "non_embiid_rim_protection": lambda d: d("rim_protection_proxy"),
        "backup_center_stability": lambda d: d("rim_protection_proxy"),
        "rebounding": lambda d: (
            d("defensive_rebounding_score") + d("offensive_rebounding_score")
        )
        / 2.0,
        "defensive_rebounding_depth": lambda d: d("defensive_rebounding_score"),
        "offensive_rebounding_depth": lambda d: d("offensive_rebounding_score"),
        "turnover_control": lambda d: 0.6 * d("connector_score")
        + 0.4 * d("low_usage_fit_score"),
        "connector_passing": lambda d: d("connector_score"),
        "pace_transition": lambda d: 0.6 * d("rim_pressure_score")
        + 0.4 * d("wing_defense_proxy"),
        "bench_rotation_depth": lambda d: d("sample_reliability"),
        "bench_creation": lambda d: d("secondary_creation_score"),
        "usage_concentration": lambda d: 0.6 * d("secondary_creation_score")
        + 0.4 * d("connector_score"),
        "lineup_versatility": lambda d: 0.5 * d("low_usage_fit_score")
        + 0.5 * d("playoff_role_proxy"),
        "playoff_playable_size": lambda d: d("playoff_role_proxy"),
        "playoff_portability_proxy": lambda d: d("playoff_role_proxy"),
    }


SCORE_COLUMNS = (
    "need_match",
    "gaps_addressed",
    "gap_specific_scores",
    "why_need_match",
    "contender_gain",
    "marginal_contender_delta",
    "expected_minutes_share",
    "why_contender_gain",
    "portability",
    "portability_tier",
    "portability_reasons",
    "portability_concerns",
    "contract_value",
    "salary_bucket",
    "salary_percentile_within_role",
    "surplus_or_overpay_label",
    "contract_value_explanation",
    "risk_score",
    "risk_tier",
    "risk_reasons",
    "final_fit",
    "theoretical_fit",
)


def score_candidates(
    candidates: pd.DataFrame,
    *,
    roster_gaps: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return ``candidates`` with all six scores and their explanations."""
    if candidates.empty:
        empty = candidates.copy()
        for column in SCORE_COLUMNS:
            empty[column] = pd.Series(dtype="object")
        return empty

    frame = candidates.reset_index(drop=True).copy()
    weights = _gap_weights(roster_gaps)

    portability, p_tier, p_reasons, p_concerns = _portability(frame)
    category_scores = _category_scores(frame, portability)
    need, gaps_addressed, gap_json, why_need = _need_match(category_scores, weights)

    role = frame.get("expected_role", pd.Series("Unknown", index=frame.index)).fillna(
        "Unknown"
    )
    minutes_share = role.map(MINUTES_SHARE_BY_ROLE).fillna(0.05)
    quality = _num(frame, "quality_percentile").fillna(0.5)
    feasibility = _num(frame, "acquisition_feasibility").fillna(45.0)

    contender_gain, why_gain = _contender_gain(
        need, minutes_share, quality, portability, feasibility
    )
    marginal = (contender_gain - contender_gain.median()).round(1)

    contract_value, salary_bucket, salary_pct, surplus_label, cv_expl = _contract_value(
        frame, quality
    )
    risk, risk_tier, risk_reasons = _risk(frame, portability=portability)

    final_fit = _final_fit(
        need, contender_gain, portability, contract_value, feasibility, risk
    )

    frame["need_match"] = need.round(1)
    frame["gaps_addressed"] = gaps_addressed
    frame["gap_specific_scores"] = gap_json
    frame["why_need_match"] = why_need
    frame["contender_gain"] = contender_gain.round(1)
    frame["marginal_contender_delta"] = marginal
    frame["expected_minutes_share"] = minutes_share.round(3)
    frame["why_contender_gain"] = why_gain
    frame["portability"] = portability.round(1)
    frame["portability_tier"] = p_tier
    frame["portability_reasons"] = p_reasons
    frame["portability_concerns"] = p_concerns
    frame["contract_value"] = contract_value.round(1)
    frame["salary_bucket"] = salary_bucket
    frame["salary_percentile_within_role"] = salary_pct.round(1)
    frame["surplus_or_overpay_label"] = surplus_label
    frame["contract_value_explanation"] = cv_expl
    frame["risk_score"] = risk.round(1)
    frame["risk_tier"] = risk_tier
    frame["risk_reasons"] = risk_reasons
    frame["final_fit"] = final_fit.round(1)
    # On the watchlist this same number is a *theoretical* fit, not a recommendation.
    frame["theoretical_fit"] = final_fit.round(1)
    return frame


# --------------------------------------------------------------------------- #
# Score 1: need match
# --------------------------------------------------------------------------- #
def _gap_weights(roster_gaps: pd.DataFrame | None) -> dict[str, float]:
    if roster_gaps is None or roster_gaps.empty or "category_key" not in roster_gaps:
        return {}
    severity = (
        roster_gaps.assign(
            severity_score=pd.to_numeric(
                roster_gaps["severity_score"], errors="coerce"
            )
        )
        .dropna(subset=["severity_score"])
        .groupby("category_key")["severity_score"]
        .max()
    )
    severity = severity[severity > 0]
    total = float(severity.sum()) or 1.0
    return {str(k): float(v / total) for k, v in severity.items()}


def _category_scores(frame: pd.DataFrame, portability: pd.Series) -> pd.DataFrame:
    dims = {dim: _dim(frame, dim) for dim in _ROLE_DIMS}

    def d(name: str) -> pd.Series:
        return dims.get(name, pd.Series(50.0, index=frame.index))

    scores = pd.DataFrame(index=frame.index)
    for key, scorer in _category_scorers().items():
        scores[key] = scorer(d).clip(0, 100)
    scores["playoff_portability_proxy"] = portability
    return scores


def _need_match(category_scores: pd.DataFrame, weights: dict[str, float]):
    active = {k: v for k, v in weights.items() if k in category_scores and v > 0}
    if not active:
        active = {c: 1.0 for c in category_scores.columns}
    total = sum(active.values()) or 1.0

    need = pd.Series(0.0, index=category_scores.index)
    for key, weight in active.items():
        need += category_scores[key] * (weight / total)

    ranked = sorted(active.items(), key=lambda kv: kv[1], reverse=True)
    top_keys = [k for k, _ in ranked][:5]
    gaps_addressed, gap_json, why = [], [], []
    for idx in category_scores.index:
        addressed = [
            _pretty(k) for k in top_keys if category_scores.at[idx, k] >= 60
        ]
        gaps_addressed.append("; ".join(addressed) if addressed else "none")
        gap_json.append(
            json.dumps(
                {
                    _pretty(k): round(float(category_scores.at[idx, k]), 1)
                    for k in top_keys
                }
            )
        )
        why.append(
            f"Answers top PHI gaps: {', '.join(addressed)}."
            if addressed
            else f"Does not move the top gap ({_pretty(top_keys[0])})."
            if top_keys
            else "No weighted gaps available."
        )
    return (
        need.clip(0, 100),
        pd.Series(gaps_addressed, index=category_scores.index),
        pd.Series(gap_json, index=category_scores.index),
        pd.Series(why, index=category_scores.index),
    )


# --------------------------------------------------------------------------- #
# Score 2: contender gain (marginal + minutes-aware)
# --------------------------------------------------------------------------- #
def _contender_gain(
    need: pd.Series,
    minutes_share: pd.Series,
    quality: pd.Series,
    portability: pd.Series,
    feasibility: pd.Series,
):
    minutes_factor = (minutes_share / MINUTES_SHARE_BY_ROLE["Star"]).clip(0, 1)
    portability_modifier = 0.6 + 0.4 * (portability / 100.0)
    feasibility_modifier = 0.7 + 0.3 * (feasibility / 100.0)
    gain = (
        100.0
        * minutes_factor
        * (need / 100.0)
        * (0.5 + 0.5 * quality)
        * portability_modifier
        * feasibility_modifier
    ).clip(0, 100)

    why = [
        f"{share:.0%} projected minutes share x need {n:.0f} x role quality "
        f"{q:.0%}, portability- and feasibility-adjusted."
        for share, n, q in zip(minutes_share, need, quality, strict=False)
    ]
    return gain, pd.Series(why, index=need.index)


# --------------------------------------------------------------------------- #
# Score 3: portability (percentile-scaled, rare 95+)
# --------------------------------------------------------------------------- #
def _portability(frame: pd.DataFrame):
    spacing = _dim(frame, "spacing_score")
    movement = _dim(frame, "catch_and_shoot_score")
    low_usage = _dim(frame, "low_usage_fit_score")
    wing_def = _dim(frame, "wing_defense_proxy")
    rim = _dim(frame, "rim_protection_proxy")
    poa = _dim(frame, "point_of_attack_defense_proxy")
    reb = _dim(frame, "defensive_rebounding_score")
    sample = _dim(frame, "sample_reliability")
    role_proxy = _dim(frame, "playoff_role_proxy")
    cs_volume = _rank01(_num(frame, "catch_shoot_fg3a")) * 100
    low_tov = 100 - _scale_ratio(_num(frame, "turnover_pct"), low=0.07, high=0.18) * 100

    raw = (
        0.22 * np.maximum(movement, spacing)
        + 0.12 * cs_volume
        + 0.14 * low_usage
        + 0.12 * low_tov
        + 0.16 * ((wing_def + rim + poa) / 3.0)
        + 0.08 * reb
        + 0.06 * sample
        + 0.10 * role_proxy
    )
    # Percentile-rank, then a mild convex curve so a 95+ is structurally rare
    # (well under 5% of the pool) rather than a flat top-5% cutoff.
    portability = ((_rank01(raw) ** 1.25) * 100).round(1)
    tier = pd.cut(
        portability,
        bins=[-0.1, 30, 50, 70, 88, 100.1],
        labels=["Low", "Questionable", "Playable", "Strong", "Elite"],
    ).astype(str)

    reasons, concerns = [], []
    minutes = _num(frame, "minutes").fillna(0.0)
    for i in frame.index:
        good, bad = [], []
        if max(movement.iloc[i], spacing.iloc[i]) >= 60:
            good.append("real floor spacing")
        if (wing_def.iloc[i] + rim.iloc[i] + poa.iloc[i]) / 3 >= 58:
            good.append("two-way defensive value")
        if low_usage.iloc[i] >= 60:
            good.append("low-usage, plug-and-play fit")
        if low_tov.iloc[i] >= 60:
            good.append("takes care of the ball")
        if minutes.iloc[i] < 800:
            bad.append("thin minutes / playoff sample")
        if max(movement.iloc[i], spacing.iloc[i]) < 40:
            bad.append("limited shooting -> matchup-huntable")
        if (wing_def.iloc[i] + rim.iloc[i] + poa.iloc[i]) / 3 < 40:
            bad.append("weak defensive proxies")
        reasons.append("; ".join(good) if good else "no standout portable traits")
        concerns.append("; ".join(bad) if bad else "no major portability concerns")
    return (
        portability,
        tier,
        pd.Series(reasons, index=frame.index),
        pd.Series(concerns, index=frame.index),
    )


# --------------------------------------------------------------------------- #
# Score 4: contract value (role-relative surplus)
# --------------------------------------------------------------------------- #
def _contract_value(frame: pd.DataFrame, quality: pd.Series):
    cap_hit = _num(frame, "cap_hit_millions")
    if cap_hit.isna().all():
        cap_hit = _num(frame, "salary_millions")
    role = frame.get("expected_role", pd.Series("Unknown", index=frame.index)).fillna(
        "Unknown"
    )

    salary_pct = pd.Series(0.5, index=frame.index)
    for value in role.unique():
        mask = role == value
        salary_pct.loc[mask] = _rank01(cap_hit[mask].fillna(cap_hit[mask].median()))
    salary_pct = salary_pct.fillna(0.5)

    surplus = (quality - salary_pct).clip(-1, 1)
    contract_value = (50 + 45 * surplus).clip(0, 100)
    # A minimum player who is not actually playable is not a "steal".
    not_playable = quality < 0.35
    cheap = cap_hit.fillna(99) <= 2.6
    contract_value = contract_value.where(
        ~(not_playable & cheap), 50 + 0.4 * (contract_value - 50)
    )
    # No contract -> cannot judge value; sit neutral and flag it elsewhere.
    contract_value = contract_value.where(cap_hit.notna(), 50.0)

    bucket = pd.cut(
        cap_hit,
        bins=[-0.1, 2.6, 8, 18, 30, 1000],
        labels=["Minimum", "Cheap", "Mid", "Large", "Max/Near-max"],
    ).astype(str)
    bucket = bucket.where(cap_hit.notna(), "Unknown")

    label = pd.cut(
        surplus,
        bins=[-1.01, -0.3, -0.1, 0.1, 0.3, 1.01],
        labels=["Overpay", "Slight overpay", "Fair", "Bargain", "Steal"],
    ).astype(str)
    label = label.where(cap_hit.notna(), "Unknown")

    expl = [
        f"{lab} - quality {q:.0%} vs salary percentile {s:.0%} within role "
        f"({b} cap hit)."
        for lab, q, s, b in zip(label, quality, salary_pct, bucket, strict=False)
    ]
    return (
        contract_value,
        bucket,
        salary_pct * 100,
        label,
        pd.Series(expl, index=frame.index),
    )


# --------------------------------------------------------------------------- #
# Score 5: risk (eight continuous components)
# --------------------------------------------------------------------------- #
def _risk(frame: pd.DataFrame, *, portability: pd.Series):
    age = _num(frame, "age")
    minutes = _num(frame, "minutes").fillna(0.0)
    three_pa = _num(frame, "three_pa").fillna(0.0)
    years = _num(frame, "years_remaining").fillna(0.0)
    cap_hit = _num(frame, "cap_hit_millions").fillna(0.0)
    sample = _dim(frame, "sample_reliability")
    role_conf = frame.get("role_confidence", "medium").map(_conf_risk).fillna(0.4)

    age_risk = age.apply(_age_risk)
    minutes_risk = (1 - minutes / 2000.0).clip(0, 1)
    shooting_sample_risk = (1 - three_pa / 250.0).clip(0, 1)
    role_uncertainty = (0.6 * role_conf + 0.4 * (1 - sample / 100.0)).clip(0, 1)
    contract_risk = ((cap_hit / 35.0) * (years.clip(0, 4) / 4.0)).clip(0, 1)
    feasibility = _num(frame, "acquisition_feasibility").fillna(45.0)
    acquisition_risk = (1 - feasibility / 100.0).clip(0, 1)
    missing_risk = frame.get("missing_data_flags", "none").apply(_missing_risk)
    playoff_risk = (1 - portability / 100.0).clip(0, 1)

    risk = (
        100
        * (
            0.13 * age_risk
            + 0.15 * minutes_risk
            + 0.10 * shooting_sample_risk
            + 0.14 * role_uncertainty
            + 0.10 * contract_risk
            + 0.14 * acquisition_risk
            + 0.10 * missing_risk
            + 0.14 * playoff_risk
        )
    ).clip(0, 100)

    unknown = missing_risk >= 0.75
    tier = pd.cut(
        risk, bins=[-0.1, 25, 45, 65, 100.1], labels=["Low", "Medium", "High", "Severe"]
    ).astype(str)
    tier = tier.where(~unknown, "Unknown")

    reasons = []
    for i in frame.index:
        parts = []
        if minutes_risk.iloc[i] >= 0.6:
            parts.append("thin minutes sample")
        if age_risk.iloc[i] >= 0.5:
            parts.append("age profile")
        if acquisition_risk.iloc[i] >= 0.6:
            parts.append("hard to acquire")
        if playoff_risk.iloc[i] >= 0.6:
            parts.append("limited playoff portability")
        if missing_risk.iloc[i] > 0:
            parts.append("missing inputs")
        reasons.append("; ".join(parts) if parts else "no dominant risk driver")
    return risk, tier, pd.Series(reasons, index=frame.index)


def _final_fit(need, gain, portability, contract_value, feasibility, risk):
    base = (
        0.30 * need
        + 0.25 * gain
        + 0.20 * portability
        + 0.15 * contract_value
        + 0.10 * feasibility
    )
    return (base - 0.20 * risk).clip(0, 100)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_ROLE_DIMS = (
    "creation_score",
    "secondary_creation_score",
    "spacing_score",
    "movement_shooting_score",
    "catch_and_shoot_score",
    "pull_up_shooting_score",
    "rim_pressure_score",
    "connector_score",
    "low_usage_fit_score",
    "wing_defense_proxy",
    "point_of_attack_defense_proxy",
    "rim_protection_proxy",
    "defensive_rebounding_score",
    "offensive_rebounding_score",
    "usage_dependency",
    "playoff_role_proxy",
    "sample_reliability",
)


def _age_risk(age: float) -> float:
    if pd.isna(age):
        return 0.35
    if 24 <= age <= 29:
        return 0.10
    if age < 24:
        return min(0.7, 0.10 + (24 - age) * 0.10)
    return min(0.9, 0.10 + (age - 29) * 0.10)


def _conf_risk(value: object) -> float:
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
