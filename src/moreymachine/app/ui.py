"""MoreyMachine UI design system: the "War Room" front-office console.

This module owns the visual identity so the page modules can stay focused on
data. It injects one theme and exposes a small set of components — scoreboard
KPIs, tier/severity chips, decision cards, and stat bars — that encode meaning
in color so a GM can read the board at a glance instead of parsing a dataframe.

Direction: a precision front-office console. Court navy carries the brand, a
single hardwood-amber accent does the warm work, and signal red is reserved for
"avoid" and high-severity gaps. Numbers are set in a mono face so every metric
reads like a scoreboard.
"""

from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any

import streamlit as st

# --- Design tokens -----------------------------------------------------------
# Palette is named so meaning travels with color across the whole product.
INK = "#0B1B2B"  # deep navy-ink, primary text
COURT_NAVY = "#17408B"  # brand primary
SIGNAL_RED = "#C8102E"  # avoid / critical, used sparingly
HARDWOOD = "#C9872E"  # the one warm accent (hardwood)
GOOD_GREEN = "#1F8A70"  # strong fit / low severity
SLATE = "#5B6B7B"  # muted captions
HAIRLINE = "#E3E8EF"
SURFACE = "#FFFFFF"
APP_BG = "#F3F5F8"

# Recommendation tier -> chip kind. One vocabulary across every board and card.
_TIER_KIND = {
    "priority target": "primary",
    "strong fit if affordable": "good",
    "role-player target": "neutral",
    "only if cheap": "warn",
    "avoid": "bad",
    "manual review required": "review",
    "unrealistic / unavailable": "ghost",
}

_CONFIDENCE_KIND = {"high": "good", "medium": "warn", "low": "bad"}


THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Inter:wght@400;500;600&family=Roboto+Mono:wght@500;600;700&display=swap');

:root {{
  --ink: {INK};
  --navy: {COURT_NAVY};
  --red: {SIGNAL_RED};
  --amber: {HARDWOOD};
  --green: {GOOD_GREEN};
  --slate: {SLATE};
  --hairline: {HAIRLINE};
  --surface: {SURFACE};
  --bg: {APP_BG};
}}

/* Base canvas ----------------------------------------------------------- */
.stApp {{ background: var(--bg); }}
.stApp, .stApp p, .stApp li, [data-testid="stMarkdownContainer"] {{
  font-family: 'Inter', system-ui, sans-serif;
  color: var(--ink);
}}
.block-container {{ padding-top: 2.4rem; max-width: 1380px; }}

h1, h2, h3, h4 {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  color: var(--ink) !important;
  letter-spacing: -0.012em;
}}
h1 {{ font-weight: 800 !important; font-size: 2.0rem !important; }}
h2 {{ font-weight: 700 !important; font-size: 1.35rem !important; }}
h3 {{ font-weight: 700 !important; font-size: 1.08rem !important; }}

/* Sidebar = the GM's nav rail ------------------------------------------ */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--ink) 0%, #0d2236 100%);
  border-right: 1px solid rgba(255,255,255,0.06);
}}
section[data-testid="stSidebar"] * {{ color: #DCE5EF; }}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: #FFFFFF !important; }}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
  text-transform: uppercase; font-size: 0.68rem; letter-spacing: 0.08em;
  font-weight: 600; color: #8FA4BC;
}}
/* Nav links in grouped st.navigation */
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{
  border-radius: 8px;
}}

/* Scoreboard + cards ---------------------------------------------------- */
.mm-board {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin: 6px 0 4px; }}
.mm-kpi {{
  background: var(--surface); border: 1px solid var(--hairline);
  border-left: 4px solid var(--navy); border-radius: 12px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(11,27,43,0.04);
}}
.mm-kpi.accent-amber {{ border-left-color: var(--amber); }}
.mm-kpi.accent-red {{ border-left-color: var(--red); }}
.mm-kpi.accent-green {{ border-left-color: var(--green); }}
.mm-kpi.accent-slate {{ border-left-color: var(--slate); }}
.mm-kpi .lab {{
  font-family: 'Archivo', sans-serif; text-transform: uppercase;
  font-size: 0.66rem; letter-spacing: 0.09em; font-weight: 600; color: var(--slate);
}}
.mm-kpi .val {{
  font-family: 'Roboto Mono', monospace; font-size: 1.7rem; font-weight: 700;
  color: var(--ink); line-height: 1.15; margin-top: 3px;
}}
.mm-kpi .sub {{ font-size: 0.74rem; color: var(--slate); margin-top: 2px; }}

.mm-eyebrow {{
  font-family: 'Archivo', sans-serif; text-transform: uppercase;
  font-size: 0.72rem; letter-spacing: 0.11em; font-weight: 700; color: var(--navy);
  display: flex; align-items: center; gap: 8px; margin: 22px 0 10px;
}}
.mm-eyebrow::after {{ content: ""; flex: 1; height: 1px; background: var(--hairline); }}

/* Status band (team header) */
.mm-band {{
  background: linear-gradient(110deg, var(--ink) 0%, #143256 60%, var(--navy) 100%);
  border-radius: 16px; padding: 20px 24px; color: #fff; margin-bottom: 6px;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;
}}
.mm-band .team {{ font-family: 'Archivo', sans-serif; font-weight: 800; font-size: 1.7rem; letter-spacing: -0.01em; }}
.mm-band .meta {{ color: #9FB6D2; font-size: 0.82rem; margin-top: 2px; }}
.mm-band .band-right {{ display: flex; gap: 10px; flex-wrap: wrap; }}

/* Chips: one shape, color encodes the call ------------------------------ */
.mm-chip {{
  display: inline-flex; align-items: center; gap: 5px; font-family: 'Archivo', sans-serif;
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase;
  padding: 3px 9px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap;
}}
.mm-chip.primary {{ background: #E7EEFA; color: var(--navy); border-color: #C7D8F2; }}
.mm-chip.good    {{ background: #E2F3EE; color: #126a55; border-color: #BDE4D8; }}
.mm-chip.warn    {{ background: #FBF0DC; color: #946115; border-color: #F0DBAE; }}
.mm-chip.bad     {{ background: #FBE4E7; color: #9c1325; border-color: #F3C2C9; }}
.mm-chip.neutral {{ background: #EEF2F6; color: #44586c; border-color: #DCE4ED; }}
.mm-chip.review  {{ background: #F0E9F8; color: #6c3fae; border-color: #DDCCF1; }}
.mm-chip.ghost   {{ background: #F3F5F8; color: #8a98a8; border-color: #E3E8EF; }}
.mm-chip.solid   {{ background: var(--ink); color: #fff; }}

/* Decision card --------------------------------------------------------- */
.mm-card {{
  background: var(--surface); border: 1px solid var(--hairline); border-radius: 14px;
  padding: 16px 18px; margin-bottom: 12px; border-left: 5px solid var(--slate);
  box-shadow: 0 1px 2px rgba(11,27,43,0.04);
}}
.mm-card.t-primary {{ border-left-color: var(--navy); }}
.mm-card.t-good {{ border-left-color: var(--green); }}
.mm-card.t-warn {{ border-left-color: var(--amber); }}
.mm-card.t-bad {{ border-left-color: var(--red); }}
.mm-card.t-review {{ border-left-color: #6c3fae; }}
.mm-card .cat {{
  font-family: 'Archivo', sans-serif; text-transform: uppercase; font-size: 0.64rem;
  letter-spacing: 0.09em; font-weight: 700; color: var(--slate);
}}
.mm-card .title {{ font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 1.06rem; margin: 3px 0 8px; color: var(--ink); }}
.mm-card .row {{ display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 9px; }}
.mm-card .line {{ font-size: 0.86rem; line-height: 1.42; margin: 4px 0; color: #28323d; }}
.mm-card .line b {{ color: var(--ink); }}
.mm-card .pro::before {{ content: "▸ "; color: var(--green); font-weight: 700; }}
.mm-card .con::before {{ content: "▸ "; color: var(--red); font-weight: 700; }}
.mm-card .foot {{ font-size: 0.72rem; color: var(--slate); margin-top: 8px; border-top: 1px dashed var(--hairline); padding-top: 7px; }}

/* Stat bars (gaps / benchmark) ------------------------------------------ */
.mm-bar-row {{ margin: 9px 0; }}
.mm-bar-top {{ display: flex; justify-content: space-between; font-size: 0.84rem; margin-bottom: 4px; }}
.mm-bar-top .nm {{ font-weight: 600; color: var(--ink); }}
.mm-bar-top .vl {{ font-family: 'Roboto Mono', monospace; font-weight: 600; color: var(--slate); }}
.mm-track {{ height: 9px; background: #EDF1F6; border-radius: 999px; overflow: hidden; }}
.mm-fill {{ height: 100%; border-radius: 999px; background: var(--navy); }}
.mm-fill.bad {{ background: var(--red); }}
.mm-fill.warn {{ background: var(--amber); }}
.mm-fill.good {{ background: var(--green); }}

/* Depth chart whiteboard ------------------------------------------------ */
.mm-slot {{ background: var(--surface); border: 1px solid var(--hairline); border-radius: 12px; padding: 12px 14px; height: 100%; }}
.mm-slot .slot-name {{
  font-family: 'Archivo', sans-serif; text-transform: uppercase; font-size: 0.7rem;
  letter-spacing: 0.07em; font-weight: 700; color: var(--navy); margin-bottom: 8px;
  display: flex; justify-content: space-between;
}}
.mm-slot .pl {{ display: flex; justify-content: space-between; align-items: baseline; padding: 5px 0; border-top: 1px solid #F0F3F7; }}
.mm-slot .pl:first-of-type {{ border-top: none; }}
.mm-slot .pl .nm {{ font-size: 0.86rem; font-weight: 600; color: var(--ink); }}
.mm-slot .pl.starter .nm::before {{ content: "★ "; color: var(--amber); }}
.mm-slot .pl .mn {{ font-family: 'Roboto Mono', monospace; font-size: 0.72rem; color: var(--slate); }}
.mm-slot .pl .age-old {{ color: var(--red); }}

.mm-note {{ background: #F7F9FB; border: 1px solid var(--hairline); border-radius: 12px; padding: 14px 18px; }}
.mm-note p:last-child {{ margin-bottom: 0; }}

/* Streamlit element polish ---------------------------------------------- */
[data-testid="stMetric"] {{
  background: var(--surface); border: 1px solid var(--hairline); border-left: 4px solid var(--navy);
  border-radius: 12px; padding: 12px 14px;
}}
[data-testid="stMetricValue"] {{ font-family: 'Roboto Mono', monospace; font-weight: 700; color: var(--ink); }}
[data-testid="stMetricLabel"] p {{
  font-family: 'Archivo', sans-serif; text-transform: uppercase; font-size: 0.66rem !important;
  letter-spacing: 0.08em; font-weight: 600; color: var(--slate);
}}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; flex-wrap: wrap; }}
.stTabs [data-baseweb="tab"] {{
  font-family: 'Archivo', sans-serif; font-weight: 600; font-size: 0.82rem;
  border-radius: 8px 8px 0 0; padding: 6px 12px;
}}
.stTabs [aria-selected="true"] {{ color: var(--navy); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--hairline); border-radius: 10px; }}
div[data-testid="stExpander"] {{ border: 1px solid var(--hairline); border-radius: 10px; }}
</style>
"""


def inject_theme() -> None:
    """Install the War Room theme once per session run."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def _h(value: Any) -> str:
    """HTML-escape a value for safe interpolation."""
    return html.escape("" if value is None else str(value))


def tier_kind(recommendation: Any) -> str:
    """Map a recommendation tier to a chip/border kind."""
    return _TIER_KIND.get(str(recommendation).strip().lower(), "neutral")


def confidence_kind(confidence: Any) -> str:
    return _CONFIDENCE_KIND.get(str(confidence).strip().lower(), "neutral")


def severity_kind(value: float, *, hi: float = 20.0, mid: float = 8.0) -> str:
    """Bucket a numeric gap-severity magnitude into a fill color."""
    try:
        magnitude = float(value)
    except (TypeError, ValueError):
        return "warn"
    if magnitude >= hi:
        return "bad"
    if magnitude >= mid:
        return "warn"
    return "good"


def chip(text: Any, kind: str = "neutral") -> str:
    """Return chip HTML. Caller renders with unsafe_allow_html=True."""
    return f'<span class="mm-chip {kind}">{_h(text)}</span>'


def tier_chip(recommendation: Any) -> str:
    return chip(recommendation, tier_kind(recommendation))


def render(html_string: str) -> None:
    """Render a block of component HTML."""
    st.markdown(html_string, unsafe_allow_html=True)


def eyebrow(text: str) -> None:
    """Render a section eyebrow divider."""
    render(f'<div class="mm-eyebrow">{_h(text)}</div>')


def status_band(team: str, *, level: str, score: Any, percentile: Any, archetype: str, season: Any) -> None:
    """Render the team status header band."""
    chips = "".join(
        [
            chip(f"Level: {level}", "solid"),
            chip(f"Contender %ile: {percentile}", "primary"),
            chip(f"Closest: {archetype}", "neutral"),
        ]
    )
    render(
        f'<div class="mm-band">'
        f'<div><div class="team">{_h(team)}</div>'
        f'<div class="meta">Season {_h(season)} · Roster-construction read · Level score {_h(score)}</div></div>'
        f'<div class="band-right">{chips}</div>'
        f'</div>'
    )


def scoreboard(items: Iterable[dict[str, Any]]) -> None:
    """Render a row of scoreboard KPI cards.

    Each item: {label, value, sub?, accent?} where accent in
    {navy, amber, red, green, slate}.
    """
    cards = []
    for item in items:
        accent = item.get("accent", "navy")
        accent_class = "" if accent == "navy" else f" accent-{accent}"
        sub = f'<div class="sub">{_h(item["sub"])}</div>' if item.get("sub") else ""
        cards.append(
            f'<div class="mm-kpi{accent_class}">'
            f'<div class="lab">{_h(item.get("label"))}</div>'
            f'<div class="val">{_h(item.get("value"))}</div>{sub}</div>'
        )
    render(f'<div class="mm-board">{"".join(cards)}</div>')


def decision_card(card: dict[str, Any]) -> None:
    """Render one GM action card as a styled decision card."""
    kind = tier_kind(card.get("recommendation"))
    category = str(card.get("action_category", "")).replace("_", " ").title()
    title = card.get("action_title") or card.get("player_name") or "Action"
    chips = tier_chip(card.get("recommendation"))
    if card.get("confidence"):
        chips += chip(f"{card.get('confidence')} confidence", confidence_kind(card.get("confidence")))
    if str(card.get("priority", "")).lower() == "high":
        chips += chip("Priority", "warn")
    do = card.get("why_do_this")
    dont = card.get("why_not_do_this")
    flags = card.get("missing_data_flags")
    do_line = f'<div class="line pro"><b>Do this.</b> {_h(do)}</div>' if do else ""
    dont_line = f'<div class="line con"><b>But watch.</b> {_h(dont)}</div>' if dont else ""
    foot = ""
    if flags and str(flags).lower() not in ("none", "nan", ""):
        foot = f'<div class="foot">Missing data: {_h(flags)}</div>'
    render(
        f'<div class="mm-card t-{kind}">'
        f'<div class="cat">{_h(category)}</div>'
        f'<div class="title">{_h(title)}</div>'
        f'<div class="row">{chips}</div>'
        f"{do_line}{dont_line}{foot}</div>"
    )


def stat_bar(name: str, value: float, *, max_value: float, kind: str = "primary", right: str | None = None) -> None:
    """Render a labelled horizontal magnitude bar."""
    try:
        pct = max(0.0, min(100.0, (float(value) / max_value) * 100.0)) if max_value else 0.0
    except (TypeError, ValueError):
        pct = 0.0
    right_label = right if right is not None else value
    render(
        f'<div class="mm-bar-row"><div class="mm-bar-top">'
        f'<span class="nm">{_h(name)}</span><span class="vl">{_h(right_label)}</span></div>'
        f'<div class="mm-track"><div class="mm-fill {kind}" style="width:{pct:.1f}%"></div></div></div>'
    )


def note(markdown_html: str) -> None:
    """Render a soft callout container around already-rendered HTML/markdown."""
    render(f'<div class="mm-note">{markdown_html}</div>')


def depth_slot(slot_name: str, count: int, players: list[dict[str, Any]]) -> str:
    """Return HTML for one depth-chart slot column."""
    rows = []
    for i, player in enumerate(players):
        starter = " starter" if i == 0 else ""
        age = player.get("age")
        age_class = " age-old" if _is_old(age) else ""
        meta = f"{_fmt_age(age)} · {player.get('mins', '')}"
        rows.append(
            f'<div class="pl{starter}"><span class="nm">{_h(player.get("name"))}</span>'
            f'<span class="mn{age_class}">{_h(meta)}</span></div>'
        )
    body = "".join(rows) or '<div class="pl"><span class="mn">—</span></div>'
    return (
        f'<div class="mm-slot"><div class="slot-name"><span>{_h(slot_name)}</span>'
        f'<span class="mn">{count}</span></div>{body}</div>'
    )


def _is_old(age: Any) -> bool:
    try:
        return float(age) >= 33
    except (TypeError, ValueError):
        return False


def _fmt_age(age: Any) -> str:
    try:
        return f"age {int(float(age))}"
    except (TypeError, ValueError):
        return "age ?"
