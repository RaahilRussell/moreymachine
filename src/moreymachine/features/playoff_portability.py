"""Transparent player playoff portability scoring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PlayoffPortabilityScore:
    """Rule-based player playoff portability score and explanations."""

    score: float
    bullets: tuple[str, ...]


def score_player_playoff_portability(
    player: Mapping[str, Any] | pd.Series,
) -> PlayoffPortabilityScore:
    """Score whether a player profile is likely to survive playoff basketball."""
    features = _player_features(player)
    score = 50.0
    bullets: list[str] = []

    score += _shooting_volume_adjustment(features, bullets)
    score += _shooting_accuracy_adjustment(features, bullets)
    score += _efficiency_usage_adjustment(features, bullets)
    score += _turnover_adjustment(features, bullets)
    score += _defense_rebounding_adjustment(features, bullets)
    score += _minutes_adjustment(features, bullets)
    score += _age_adjustment(features, bullets)
    score += _foul_adjustment(features, bullets)
    score += _one_dimensional_adjustment(features, bullets)

    clipped_score = round(max(0.0, min(100.0, score)), 1)
    return PlayoffPortabilityScore(score=clipped_score, bullets=tuple(bullets))


def add_playoff_portability_scores(player_seasons: pd.DataFrame) -> pd.DataFrame:
    """Append playoff portability score and explanation columns to player rows."""
    result = player_seasons.copy()
    scores = [
        score_player_playoff_portability(row)
        for row in player_seasons.to_dict(orient="records")
    ]
    result["playoff_portability_score"] = [score.score for score in scores]
    result["playoff_portability_bullets"] = [score.bullets for score in scores]
    result["playoff_portability_explanation"] = [
        "\n".join(f"- {bullet}" for bullet in score.bullets) for score in scores
    ]
    return result


def _shooting_volume_adjustment(
    features: dict[str, Any],
    bullets: list[str],
) -> float:
    three_point_rate = features["three_point_attempt_rate"]
    three_pa_per_36 = features["three_pa_per_36"]
    three_point_percentage = features["three_point_percentage"]
    bucket = features["position_bucket"]
    high_rate = {"guard": 0.42, "wing": 0.40, "big": 0.34, "unknown": 0.38}[bucket]
    solid_rate = {"guard": 0.32, "wing": 0.30, "big": 0.26, "unknown": 0.30}[bucket]
    high_per_36 = {"guard": 7.0, "wing": 6.5, "big": 5.0, "unknown": 6.0}[bucket]

    if _is_known(three_point_rate) and three_point_rate >= high_rate:
        bullets.append("Strong position-adjusted three-point volume.")
        return 14.0
    if _is_known(three_pa_per_36) and three_pa_per_36 >= high_per_36:
        bullets.append("Strong three-point volume per 36 minutes.")
        return 14.0
    if _is_known(three_point_rate) and three_point_rate >= solid_rate:
        bullets.append("Usable playoff spacing volume.")
        return 7.0
    if (
        _is_known(three_point_percentage)
        and three_point_percentage >= 0.36
        and (not _is_known(three_point_rate) or three_point_rate < 0.20)
        and (not _is_known(three_pa_per_36) or three_pa_per_36 < 3.0)
    ):
        bullets.append("Low-volume fake shooting risk despite the percentage.")
        return -16.0
    if _is_known(three_point_rate) and three_point_rate < 0.18:
        bullets.append("Limited three-point volume compresses spacing.")
        return -8.0
    return 0.0


def _shooting_accuracy_adjustment(
    features: dict[str, Any],
    bullets: list[str],
) -> float:
    three_point_percentage = features["three_point_percentage"]
    three_point_rate = features["three_point_attempt_rate"]
    if not _is_known(three_point_percentage):
        return 0.0
    if _low_volume_shooting_profile(features):
        return 0.0
    if three_point_percentage >= 0.38:
        bullets.append("Plus three-point accuracy.")
        return 10.0
    if three_point_percentage >= 0.35:
        bullets.append("Acceptable three-point accuracy.")
        return 6.0
    if _is_known(three_point_rate) and three_point_rate >= 0.30:
        bullets.append("High shooting volume comes with weak three-point accuracy.")
        return -10.0
    return 0.0


def _efficiency_usage_adjustment(
    features: dict[str, Any],
    bullets: list[str],
) -> float:
    usage_rate = features["usage_rate"]
    efficiency = features["shooting_efficiency"]
    adjustment = 0.0

    if _is_known(usage_rate) and _is_known(efficiency):
        if usage_rate >= 0.30 and efficiency < 0.53:
            bullets.append("High-usage scoring is inefficient for playoff creation.")
            adjustment -= 25.0
        elif usage_rate >= 0.26 and efficiency < 0.55:
            bullets.append("Usage load depends on below-average efficiency.")
            adjustment -= 18.0
        elif usage_rate <= 0.20 and efficiency >= 0.55:
            bullets.append("Low-usage role does not require difficult self-creation.")
            adjustment += 8.0

    if _is_known(efficiency):
        if efficiency >= 0.60:
            bullets.append("Efficient scoring profile travels well.")
            adjustment += 10.0
        elif efficiency >= 0.56:
            bullets.append("Solid overall scoring efficiency.")
            adjustment += 5.0
        elif efficiency < 0.52:
            bullets.append("Poor scoring efficiency is likely to be stressed.")
            adjustment -= 10.0

    if _is_known(usage_rate) and usage_rate >= 0.32 and adjustment >= 0:
        bullets.append("High usage dependency adds playoff fragility.")
        adjustment -= 8.0

    return adjustment


def _turnover_adjustment(features: dict[str, Any], bullets: list[str]) -> float:
    turnover_rate = features["turnover_rate"]
    if not _is_known(turnover_rate):
        return 0.0
    if turnover_rate <= 0.10:
        bullets.append("Low turnover profile protects possessions.")
        return 10.0
    if turnover_rate <= 0.13:
        bullets.append("Turnover rate is manageable.")
        return 6.0
    if turnover_rate >= 0.19:
        bullets.append("Severe turnover issue raises playoff risk.")
        return -18.0
    if turnover_rate >= 0.16:
        bullets.append("Turnover rate is vulnerable to playoff pressure.")
        return -12.0
    return 0.0


def _defense_rebounding_adjustment(
    features: dict[str, Any],
    bullets: list[str],
) -> float:
    steal_rate = features["steal_rate"]
    block_rate = features["block_rate"]
    rebound_rate = features["rebound_rate"]
    defensive_metric = features["defensive_metric"]
    defensive_rating = features["defensive_rating"]
    adjustment = 0.0

    if _is_known(defensive_metric):
        if defensive_metric >= 1.0:
            bullets.append("Positive defensive impact proxy.")
            adjustment += 8.0
        elif defensive_metric >= 0.0:
            bullets.append("Acceptable defensive impact proxy.")
            adjustment += 4.0
        elif defensive_metric <= -1.0:
            bullets.append("Poor defensive impact proxy.")
            adjustment -= 10.0

    if _is_known(defensive_rating):
        if defensive_rating <= 112:
            bullets.append("Defensive rating proxy is playoff-friendly.")
            adjustment += 5.0
        elif defensive_rating >= 118:
            bullets.append("Defensive rating proxy is a concern.")
            adjustment -= 8.0

    activity_score = 0.0
    if _is_known(steal_rate) and steal_rate >= 0.015:
        activity_score += 1.0
    if _is_known(block_rate) and block_rate >= 0.015:
        activity_score += 1.0
    if _is_known(rebound_rate) and rebound_rate >= 0.10:
        activity_score += 1.0

    if activity_score >= 2:
        bullets.append("Defensive activity and rebounding proxies add portability.")
        adjustment += 8.0
    elif _has_defense_rebound_sample(features) and activity_score == 0:
        bullets.append("Weak defensive and rebounding proxies limit lineup utility.")
        adjustment -= 10.0

    return adjustment


def _minutes_adjustment(features: dict[str, Any], bullets: list[str]) -> float:
    minutes = features["minutes"]
    if not _is_known(minutes):
        return 0.0
    if minutes >= 1800:
        bullets.append("Strong minutes sample supports role reliability.")
        return 10.0
    if minutes >= 1200:
        bullets.append("Reliable rotation minutes sample.")
        return 7.0
    if minutes >= 800:
        bullets.append("Moderate minutes sample.")
        return 3.0
    if minutes < 500:
        bullets.append("Tiny minutes sample makes the profile fragile.")
        return -18.0
    bullets.append("Limited minutes sample adds uncertainty.")
    return -10.0


def _age_adjustment(features: dict[str, Any], bullets: list[str]) -> float:
    age = features["age"]
    if not _is_known(age):
        return 0.0
    if 24 <= age <= 32:
        bullets.append("Age is in the typical playoff-prime band.")
        return 6.0
    if 21 <= age <= 34:
        bullets.append("Age is within a workable playoff range.")
        return 3.0
    if age < 21:
        bullets.append("Very young players often face playoff adjustment risk.")
        return -5.0
    bullets.append("Older age adds durability and matchup risk.")
    return -8.0


def _foul_adjustment(features: dict[str, Any], bullets: list[str]) -> float:
    foul_rate = features["foul_rate"]
    fouls_per_36 = features["fouls_per_36"]
    if _is_known(fouls_per_36):
        if fouls_per_36 >= 4.5:
            bullets.append("High foul rate threatens playoff availability.")
            return -10.0
        if fouls_per_36 >= 3.8:
            bullets.append("Foul rate can pressure playoff rotations.")
            return -6.0
    if _is_known(foul_rate):
        if foul_rate >= 0.07:
            bullets.append("High foul rate threatens playoff availability.")
            return -10.0
        if foul_rate >= 0.055:
            bullets.append("Foul rate can pressure playoff rotations.")
            return -6.0
    return 0.0


def _one_dimensional_adjustment(
    features: dict[str, Any],
    bullets: list[str],
) -> float:
    shooting_value = (
        _is_known(features["three_point_attempt_rate"])
        and features["three_point_attempt_rate"] >= 0.30
        and _is_known(features["three_point_percentage"])
        and features["three_point_percentage"] >= 0.35
    )
    defensive_value = _defensive_value_present(features)
    connective_value = (
        _is_known(features["assist_rate"]) and features["assist_rate"] >= 0.12
    )
    usage_rate = features["usage_rate"]

    value_count = sum((shooting_value, defensive_value, connective_value))
    if shooting_value and value_count == 1:
        bullets.append("Shooting is useful but the profile looks one-dimensional.")
        return -7.0
    if (
        _is_known(usage_rate)
        and usage_rate >= 0.24
        and not shooting_value
        and not defensive_value
    ):
        bullets.append("Scoring role lacks enough secondary playoff value.")
        return -8.0
    return 0.0


def _low_volume_shooting_profile(features: dict[str, Any]) -> bool:
    three_point_rate = features["three_point_attempt_rate"]
    three_pa_per_36 = features["three_pa_per_36"]
    return (not _is_known(three_point_rate) or three_point_rate < 0.20) and (
        not _is_known(three_pa_per_36) or three_pa_per_36 < 3.0
    )


def _player_features(player: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
    return {
        "age": _number(player, ("age",)),
        "minutes": _number(player, ("minutes", "min", "mp")),
        "usage_rate": _ratio(
            player,
            ("usage_rate", "usage_percentage", "usg_pct", "usg"),
        ),
        "shooting_efficiency": _shooting_efficiency(player),
        "three_point_attempt_rate": _three_point_attempt_rate(player),
        "three_pa_per_36": _three_pa_per_36(player),
        "three_point_percentage": _ratio(
            player,
            ("three_point_percentage", "three_point_pct", "three_p_pct", "fg3_pct"),
        ),
        "turnover_rate": _turnover_rate(player),
        "assist_rate": _assist_rate(player),
        "rebound_rate": _ratio(
            player,
            ("rebound_rate", "rebound_percentage", "rebound_pct", "reb_pct", "trb_pct"),
        ),
        "steal_rate": _event_rate(player, ("steal_rate", "stl_rate"), ("stl",)),
        "block_rate": _event_rate(player, ("block_rate", "blk_rate"), ("blk",)),
        "foul_rate": _event_rate(
            player,
            ("foul_rate", "personal_foul_rate", "pf_rate"),
            ("pf", "personal_fouls"),
        ),
        "fouls_per_36": _fouls_per_36(player),
        "defensive_metric": _number(
            player,
            (
                "defensive_box_plus_minus",
                "dbpm",
                "defensive_estimated_plus_minus",
                "d_epm",
                "defensive_raptor",
            ),
        ),
        "defensive_rating": _number(
            player,
            ("defensive_rating", "def_rating", "def_rtg", "drtg"),
        ),
        "position_bucket": _position_bucket(
            _raw_value(
                player,
                ("position", "player_position", "player_position_abbreviation", "pos"),
            )
        ),
    }


def _shooting_efficiency(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _ratio(
        player,
        ("true_shooting_percentage", "true_shooting", "ts_pct", "ts"),
    )
    if _is_known(direct):
        return direct

    points = _number(player, ("pts", "points"))
    fga = _number(player, ("fga", "field_goals_attempted"))
    fta = _number(player, ("fta", "free_throws_attempted"))
    if _is_known(points) and _is_known(fga) and _is_known(fta):
        denominator = 2 * (fga + (0.44 * fta))
        if denominator > 0:
            return points / denominator

    efg = _ratio(
        player,
        ("effective_fg_percentage", "efg_percentage", "efg_pct", "e_fg_pct"),
    )
    if _is_known(efg):
        return efg
    return _ratio(player, ("fg_pct", "field_goal_percentage"))


def _three_point_attempt_rate(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _ratio(
        player,
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
    fg3a = _number(player, ("fg3a", "three_pointers_attempted"))
    fga = _number(player, ("fga", "field_goals_attempted"))
    if _is_known(fg3a) and _is_known(fga) and fga > 0:
        return fg3a / fga
    return None


def _three_pa_per_36(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _number(player, ("three_point_attempts_per_36", "fg3a_per_36"))
    if _is_known(direct):
        return direct
    fg3a = _number(player, ("fg3a", "three_pointers_attempted"))
    minutes = _number(player, ("minutes", "min", "mp"))
    if _is_known(fg3a) and _is_known(minutes) and minutes > 0:
        return fg3a / minutes * 36
    return None


def _turnover_rate(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _ratio(
        player,
        ("turnover_rate", "turnover_percentage", "turnover_pct", "tov_pct"),
    )
    if _is_known(direct):
        return direct

    turnovers = _number(player, ("tov", "turnovers"))
    fga = _number(player, ("fga", "field_goals_attempted"))
    fta = _number(player, ("fta", "free_throws_attempted"))
    if _is_known(turnovers) and _is_known(fga) and _is_known(fta):
        denominator = fga + (0.44 * fta) + turnovers
        if denominator > 0:
            return turnovers / denominator
    return _event_rate(player, (), ("tov", "turnovers"))


def _assist_rate(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _ratio(
        player, ("assist_rate", "assist_percentage", "assist_pct", "ast_pct")
    )
    if _is_known(direct):
        return direct
    return _event_rate(player, (), ("ast", "assists"))


def _event_rate(
    player: Mapping[str, Any] | pd.Series,
    direct_aliases: tuple[str, ...],
    count_aliases: tuple[str, ...],
) -> float | None:
    direct = _ratio(player, direct_aliases)
    if _is_known(direct):
        return direct
    count = _number(player, count_aliases)
    minutes = _number(player, ("minutes", "min", "mp"))
    if _is_known(count) and _is_known(minutes) and minutes > 0:
        return count / minutes
    return None


def _fouls_per_36(player: Mapping[str, Any] | pd.Series) -> float | None:
    direct = _number(player, ("fouls_per_36", "personal_fouls_per_36", "pf_per_36"))
    if _is_known(direct):
        return direct
    fouls = _number(player, ("pf", "personal_fouls"))
    minutes = _number(player, ("minutes", "min", "mp"))
    if _is_known(fouls) and _is_known(minutes) and minutes > 0:
        return fouls / minutes * 36
    return None


def _number(
    player: Mapping[str, Any] | pd.Series, aliases: tuple[str, ...]
) -> float | None:
    value = _raw_value(player, aliases)
    if value is None:
        return None
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _ratio(
    player: Mapping[str, Any] | pd.Series, aliases: tuple[str, ...]
) -> float | None:
    value = _number(player, aliases)
    if value is None:
        return None
    if abs(value) > 1.5:
        return value / 100
    return value


def _raw_value(player: Mapping[str, Any] | pd.Series, aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).lower(): key for key in player.keys()}
    for alias in aliases:
        key = normalized.get(alias.lower())
        if key is not None:
            return player[key]
    return None


def _position_bucket(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "").replace("/", "")
    if text in {"", "nan", "none"}:
        return "unknown"
    if "pf" in text or "c" in text or text in {"fc", "cf"}:
        return "big"
    if "sf" in text or text in {"f", "gf", "fg"}:
        return "wing"
    if "pg" in text or "sg" in text or text == "g":
        return "guard"
    if "center" in text or "big" in text:
        return "big"
    if "wing" in text or "forward" in text:
        return "wing"
    if "guard" in text:
        return "guard"
    return "unknown"


def _has_defense_rebound_sample(features: dict[str, Any]) -> bool:
    return any(
        _is_known(features[column])
        for column in ("steal_rate", "block_rate", "rebound_rate")
    )


def _defensive_value_present(features: dict[str, Any]) -> bool:
    defensive_metric = features["defensive_metric"]
    defensive_rating = features["defensive_rating"]
    if _is_known(defensive_metric) and defensive_metric >= 0:
        return True
    if _is_known(defensive_rating) and defensive_rating <= 114:
        return True
    if _is_known(features["steal_rate"]) and features["steal_rate"] >= 0.015:
        return True
    if _is_known(features["block_rate"]) and features["block_rate"] >= 0.015:
        return True
    return _is_known(features["rebound_rate"]) and features["rebound_rate"] >= 0.10


def _is_known(value: float | None) -> bool:
    return value is not None and not pd.isna(value)
