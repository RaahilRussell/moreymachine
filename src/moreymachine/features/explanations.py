"""Explanation engine: a structured, human-readable rationale per score.

MoreyMachine never shows a number without an explanation. Every engineered
team/player score is registered here with five facets:

* ``what`` - what the score means
* ``why`` - why it matters
* ``how`` - how it is calculated
* ``high`` / ``low`` - what high vs low values imply
* ``playoff_link`` - how it relates to playoff roster construction

The registry is consumed by the Streamlit app (Contender Blueprint, score
breakdowns) and the markdown reports so explanations stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ScoreExplanation:
    """A structured explanation for a single engineered score."""

    key: str
    label: str
    what: str
    why: str
    how: str
    high: str
    low: str
    playoff_link: str

    def to_markdown(self) -> str:
        """Render the explanation as a markdown block."""
        return (
            f"**{self.label}**\n\n"
            f"- *What it means:* {self.what}\n"
            f"- *Why it matters:* {self.why}\n"
            f"- *How it is calculated:* {self.how}\n"
            f"- *High values imply:* {self.high}\n"
            f"- *Low values imply:* {self.low}\n"
            f"- *Playoff roster link:* {self.playoff_link}\n"
        )

    def as_dict(self) -> dict[str, str]:
        """Return the explanation facets as a flat dict (for tables)."""
        return {
            "score": self.label,
            "what_it_means": self.what,
            "why_it_matters": self.why,
            "how_calculated": self.how,
            "high_values": self.high,
            "low_values": self.low,
            "playoff_link": self.playoff_link,
        }


_EXPLANATIONS: dict[str, ScoreExplanation] = {}


def _register(explanation: ScoreExplanation) -> None:
    _EXPLANATIONS[explanation.key] = explanation


def explanation_for(key: str) -> ScoreExplanation | None:
    """Return the registered explanation for a score key, if any."""
    return _EXPLANATIONS.get(key)


def all_explanations() -> tuple[ScoreExplanation, ...]:
    """Return every registered explanation."""
    return tuple(_EXPLANATIONS.values())


def explanation_table() -> pd.DataFrame:
    """Return all explanations as a DataFrame for display."""
    return pd.DataFrame([item.as_dict() for item in _EXPLANATIONS.values()])


def describe_value(key: str, value: float | None) -> str:
    """Return a one-line description of a score, optionally with its value."""
    explanation = explanation_for(key)
    if explanation is None:
        return f"{key} (no explanation registered)"
    if value is None or pd.isna(value):
        return f"{explanation.label}: {explanation.what}"
    return f"{explanation.label} = {float(value):.3g}. {explanation.what}"


_register(
    ScoreExplanation(
        key="offensive_rating",
        label="Offensive rating",
        what="Points scored per 100 possessions.",
        why="Pace-neutral scoring efficiency; the cleanest measure of offense.",
        how="Taken directly from NBA.com Advanced box score (OFF_RATING).",
        high="An efficient offense that converts possessions into points.",
        low="A stagnant or low-efficiency offense.",
        playoff_link="Title teams almost always pair a top-10 offense with "
        "playoff-proof shot creation and spacing.",
    )
)
_register(
    ScoreExplanation(
        key="defensive_rating",
        label="Defensive rating",
        what="Points allowed per 100 possessions (lower is better).",
        why="Defense travels in the playoffs when offenses bog down.",
        how="Taken directly from NBA.com Advanced box score (DEF_RATING).",
        high="A leaky defense that concedes efficient looks.",
        low="A stingy defense that forces tough shots.",
        playoff_link="Deep-run teams typically have at least a top-10 defense "
        "and a rim/anchor plus switchable wings.",
    )
)
_register(
    ScoreExplanation(
        key="net_rating",
        label="Net rating",
        what="Offensive rating minus defensive rating per 100 possessions.",
        why="The single best one-number summary of team strength.",
        how="OFF_RATING - DEF_RATING from NBA.com Advanced stats.",
        high="A dominant team on both ends.",
        low="A team being outscored over the season.",
        playoff_link="Champions are nearly always top-5 in net rating; a strong "
        "net rating is the price of entry for contention.",
    )
)
_register(
    ScoreExplanation(
        key="pace",
        label="Pace",
        what="Possessions per 48 minutes.",
        why="Sets the tempo and the number of shot opportunities.",
        how="NBA.com Advanced PACE.",
        high="A fast, transition-oriented style.",
        low="A slow, half-court-oriented style.",
        playoff_link="Pace itself does not win playoff series, but rosters must "
        "fit their tempo (transition shooting vs half-court creation).",
    )
)
_register(
    ScoreExplanation(
        key="efg_percentage",
        label="Effective FG%",
        what="Field-goal percentage that credits 3-pointers 1.5x.",
        why="The most important of the four factors for offense.",
        how="NBA.com Four Factors / Advanced EFG_PCT.",
        high="Efficient, well-spaced shot-making.",
        low="A team settling for or missing inefficient shots.",
        playoff_link="Playoff defenses take away easy looks; teams that keep eFG% "
        "high under pressure need real shooting, not volume scorers.",
    )
)
_register(
    ScoreExplanation(
        key="turnover_percentage",
        label="Turnover %",
        what="Share of possessions ending in a turnover (lower is better).",
        why="Turnovers are wasted possessions and transition points against.",
        how="NBA.com Advanced TM_TOV_PCT.",
        high="A careless offense that gives away possessions.",
        low="A secure offense that values the ball.",
        playoff_link="Half-court playoff offense magnifies turnovers; low-turnover "
        "connectors and secure ball-handlers gain value.",
    )
)
_register(
    ScoreExplanation(
        key="offensive_rebounding_percentage",
        label="Offensive rebound %",
        what="Share of available offensive rebounds grabbed.",
        why="Creates extra possessions and second-chance points.",
        how="NBA.com Advanced OREB_PCT.",
        high="A team that crashes the glass for extra possessions.",
        low="A team that gets back on defense and concedes the glass.",
        playoff_link="Offensive rebounding is a repeatable way to add possessions "
        "when half-court offense stalls in a series.",
    )
)
_register(
    ScoreExplanation(
        key="defensive_rebounding_percentage",
        label="Defensive rebound %",
        what="Share of available defensive rebounds secured.",
        why="Ends opponent possessions and prevents second chances.",
        how="NBA.com Advanced DREB_PCT.",
        high="A defense that closes possessions with the rebound.",
        low="A defense that surrenders second-chance opportunities.",
        playoff_link="Series are lost on second-chance points; contenders need "
        "at least one strong defensive rebounder in the rotation.",
    )
)
_register(
    ScoreExplanation(
        key="free_throw_rate",
        label="Free-throw rate",
        what="Free-throw attempts per field-goal attempt.",
        why="Free points and a proxy for rim pressure and physicality.",
        how="NBA.com Four Factors FTA_RATE.",
        high="A team that attacks the rim and draws fouls.",
        low="A jump-shooting team that lives on the perimeter.",
        playoff_link="Officiating tightens in the playoffs; rim pressure that "
        "draws fouls is a reliable points source when shots stop falling.",
    )
)
_register(
    ScoreExplanation(
        key="three_point_attempt_rate",
        label="3-point attempt rate",
        what="Share of field-goal attempts taken from three.",
        why="Measures how much a team leans on spacing and the long ball.",
        how="FG3A / FGA from NBA.com Base stats.",
        high="A spacing-heavy, modern shot profile.",
        low="A team that lives inside the arc.",
        playoff_link="Volume, not just accuracy, stresses playoff defenses; "
        "real 3-point volume keeps the floor spaced for stars.",
    )
)
_register(
    ScoreExplanation(
        key="three_point_percentage",
        label="3-point %",
        what="Share of 3-point attempts made.",
        why="Accuracy converts spacing into actual points.",
        how="FG3_PCT from NBA.com Base stats.",
        high="A team that punishes defenses for helping off shooters.",
        low="A team whose spacing is not respected.",
        playoff_link="Percentage is noisy in small samples; it must be paired "
        "with volume to be a trustworthy playoff signal.",
    )
)
_register(
    ScoreExplanation(
        key="estimated_shooting_pressure",
        label="Shooting pressure score",
        what="A 0-1 blend of how much shooting stress a team applies.",
        why="Captures spacing + accuracy + rim pressure in one number.",
        how="Mean of within-season percentiles for eFG%, 3-point attempt rate, "
        "3-point %, and free-throw rate.",
        high="A team that stretches and punishes defenses from everywhere.",
        low="A team defenses can pack the paint against.",
        playoff_link="Shooting pressure is what preserves star driving lanes; "
        "contenders surround creators with high-pressure shooters.",
    )
)
_register(
    ScoreExplanation(
        key="estimated_possession_control",
        label="Possession control score",
        what="A 0-1 blend of how well a team wins the possession battle.",
        why="Extra and protected possessions add efficient points.",
        how="Mean of within-season percentiles for low turnover %, offensive "
        "rebound %, and defensive rebound %.",
        high="A team that protects the ball and controls the glass.",
        low="A team that leaks possessions via turnovers or the boards.",
        playoff_link="Half-court playoff series reward every extra possession; "
        "rebounding bigs and low-turnover guards raise this score.",
    )
)
_register(
    ScoreExplanation(
        key="estimated_two_way_balance",
        label="Two-way balance score",
        what="A 0-1 blend of overall strength and offense/defense balance.",
        why="Balanced teams have fewer exploitable weaknesses in a series.",
        how="Mean of within-season net-rating percentile, offense and defense "
        "percentiles, and an offense-vs-defense balance term.",
        high="A team strong and balanced on both ends.",
        low="A lopsided team a playoff opponent can attack.",
        playoff_link="Series expose one-way teams; balance is what lets a roster "
        "survive matchup-specific game-planning.",
    )
)
_register(
    ScoreExplanation(
        key="playoff_tier",
        label="Playoff tier (0-5)",
        what="How far a team advanced: 0 missed, 1 first round, 2 second round, "
        "3 conference finals, 4 finals, 5 champion.",
        why="The ground-truth outcome label models learn to predict.",
        how="Real, hand-verified results in data/manual/playoff_tiers.csv.",
        high="A deep playoff run.",
        low="An early exit or lottery season.",
        playoff_link="Tiers 3+ ('deep playoff') define the contender blueprint "
        "MoreyMachine reverse-engineers.",
    )
)
_register(
    ScoreExplanation(
        key="quality_tier",
        label="Regular-season quality tier (0-5)",
        what="Within-season strength band from net rating: 0 bottom, 5 elite.",
        why="Separates contender-level rosters from pretenders before playoffs.",
        how="Within-season percentile rank of net rating mapped to 0-5 bands.",
        high="A top-of-league regular-season team.",
        low="A lottery-level regular-season team.",
        playoff_link="Quality tier is the regular-season filter; deep runs almost "
        "always come from tier 4-5 rosters.",
    )
)
_register(
    ScoreExplanation(
        key="deep_playoff",
        label="Deep playoff flag",
        what="True when a team reached the conference finals or better (tier >= 3).",
        why="The binary contender target the contender model predicts.",
        how="Derived from playoff_tier >= 3.",
        high="A genuine contender-level outcome.",
        low="A team that did not reach the final four.",
        playoff_link="The fingerprint of deep_playoff teams is the template the "
        "Sixers roster is measured against.",
    )
)
