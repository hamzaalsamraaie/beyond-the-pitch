"""
Association football (soccer) relevance filter.

All classification is based on title and channel title metadata only.
No video content is accessed or viewed. Classification is a heuristic
estimate — it cannot be confirmed without watching the video.

Relevance tiers:
  soccer        — strong positive signals, no negative signals
  likely_soccer — at least one soccer-specific signal, no strong negative
  uncertain     — no clear signals in either direction (excluded from report)
  other         — clear non-soccer or non-sport content (excluded from report)

Age tiers (computed from publication date, not from view velocity):
  RECENT_BREAKOUT — published within 30 days
  RECENT_SUCCESS  — published 31–90 days ago
  EVERGREEN       — older than 90 days

Growth rate cannot be claimed from a single snapshot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Keyword sets (all lowercase) ──────────────────────────────────────────────

_SOCCER_PLAYERS = frozenset({
    "messi", "ronaldo", "neymar", "haaland", "mbappe", "vinicius",
    "bellingham", "zidane", "pele", "maradona", "ronaldinho", "ibrahimovic",
    "salah", "de bruyne", "modric", "benzema", "suarez", "cavani", "pogba",
    "drogba", "henry", "cantona", "beckham", "rooney", "gerrard", "lampard",
    "scholes", "giggs", "cruyff", "van basten", "gullit", "platini",
    "roberto carlos", "maldini", "pirlo", "buffon", "casillas", "xavi",
    "iniesta", "fabregas", "aguero", "batistuta", "klinsmann", "baggio",
    "totti", "del piero", "inzaghi", "shevchenko", "ballack", "klose",
    "neuer", "lewandowski", "rashford", "sterling", "lacazette",
    "aubameyang", "vardy", "kane", "son", "firmino", "mane", "van dijk",
    "alisson", "oblak", "ter stegen", "courtois", "havertz", "pulisic",
    "pedri", "gavi", "yamal", "chhetri", "sunil chhetri", "eriksen",
    "rice", "saka", "odegaard", "r9", "cr7", "gazza", "gascoigne",
    "shearer", "bergkamp", "kaka", "rivaldo", "pires",
})

_SOCCER_CLUBS = frozenset({
    "barcelona", "barca", "real madrid", "manchester united", "man utd",
    "man united", "liverpool", "chelsea", "arsenal", "manchester city",
    "man city", "tottenham", "spurs", "juventus", "juve", "ac milan",
    "inter milan", "napoli", "roma", "lazio", "bayern munich", "borussia",
    "dortmund", "bvb", "psg", "paris saint-germain", "ajax", "porto",
    "benfica", "atletico madrid", "sevilla", "valencia", "celtic",
    "rangers", "feyenoord", "psv", "anderlecht", "galatasaray",
    "boca juniors", "flamengo", "river plate", "al-nassr", "al nassr",
    "al-hilal", "aston villa", "newcastle", "brighton", "west ham",
    "leicester", "everton", "wolves", "brentford", "inter miami",
})

_SOCCER_COMPETITIONS = frozenset({
    "champions league", "ucl", "premier league", "epl", "la liga",
    "bundesliga", "serie a", "ligue 1", "world cup", "euro 2024", "euros",
    "copa del rey", "fa cup", "copa america", "afcon", "africa cup",
    "community shield", "club world cup", "carabao cup", "efl cup",
    "conference league", "europa league",
})

# Soccer-exclusive terms (not shared with American football)
_SOCCER_TERMS = frozenset({
    "free kick", "freekick", "penalty", "penalties", "goalkeeper",
    "dribble", "dribbling", "hat trick", "hattrick", "offside", "var",
    "header", "volley", "assist", "clean sheet", "own goal", "set piece",
    "corner kick", "back heel", "nutmeg", "bicycle kick", "overhead kick",
    "rabona", "panenka", "chip", "siuuu", "siuu",
    "#soccer", "soccer game", "soccer match", "soccer player",
    "#futbol", "futbol", "#footy", "footy",
})

# Strong American-football-specific signals
_AMERICAN_FOOTBALL_SIGNALS = frozenset({
    " nfl ", " nfl,", " nfl.", "#nfl", "nfl game", "nfl player",
    "super bowl", "superbowl",
    "touchdown", "#touchdown",
    "quarterback", " qb ", "#qb ",
    "tight end", "wide receiver", "linebacker", "running back",
    "#micdup", "mic'd up", "mic up",
    "first down", "fumble recovery", "punt return",
    "marquise goodwin",    # NFL player (appeared in live data)
    "american football",
})

# Other non-soccer sports
_OTHER_SPORT_SIGNALS = frozenset({
    "#nba", " nba ", "nba game", "nba player", "basketball game",
    "#mlb", " mlb ", "baseball game",
    "#nhl", " nhl ", "ice hockey",
    "cricket match", "cricket game",
    "rugby match", "rugby league", "rugby union",
    " golf ", "golf tournament",
    "tennis match", "tennis tournament",
    "boxing match", "#mma", "ufc fight",
})

# Clearly non-sport motivation / lifestyle content
_NON_SPORT_SIGNALS = frozenset({
    "army athletes", "military motivation",
    "gym motivation #gym",
    "bodybuilding", "powerlifting",
})


@dataclass
class RelevanceResult:
    score: float
    tier: str                      # "soccer" | "likely_soccer" | "uncertain" | "other"
    positive_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def is_soccer(self) -> bool:
        return self.tier in ("soccer", "likely_soccer")


def _norm(text: str) -> str:
    """Lowercase with leading/trailing spaces for whole-word matching."""
    return " " + text.lower() + " "


def assess_soccer_relevance(title: str, channel_title: str = "") -> RelevanceResult:
    """
    Classify a video as soccer-relevant based on title and channel title.

    Returns a RelevanceResult. All classification is **metadata_only** —
    the video has NOT been watched or inspected beyond title text.
    Signals are detected via substring matching on lowercased text.
    """
    combined = _norm(title + " " + channel_title)
    score = 0.0
    pos: list[str] = []
    neg: list[str] = []

    # ── Positive signals (first match wins to avoid double-counting) ──────────
    for player in _SOCCER_PLAYERS:
        if player in combined:
            score += 2.0
            pos.append(f"player:{player}")
            break

    for club in _SOCCER_CLUBS:
        if club in combined:
            score += 2.0
            pos.append(f"club:{club}")
            break

    for comp in _SOCCER_COMPETITIONS:
        if comp in combined:
            score += 2.0
            pos.append(f"competition:{comp}")
            break

    for term in _SOCCER_TERMS:
        if term in combined:
            score += 1.0
            pos.append(f"term:{term}")
            break

    # ── Negative signals ──────────────────────────────────────────────────────
    for sig in _AMERICAN_FOOTBALL_SIGNALS:
        if sig in combined:
            score -= 4.0
            neg.append(f"american_football:{sig.strip()}")
            break

    for sig in _OTHER_SPORT_SIGNALS:
        if sig in combined:
            score -= 3.0
            neg.append(f"other_sport:{sig.strip()}")
            break

    for sig in _NON_SPORT_SIGNALS:
        if sig in combined:
            score -= 2.0
            neg.append(f"non_sport:{sig.strip()}")
            break

    # ── Classify ──────────────────────────────────────────────────────────────
    if score >= 2.0 and not neg:
        tier = "soccer"
        note = "Strong soccer signal (metadata-only — not verified by watching)"
    elif score >= 1.0 and score > sum(                     # positive outweighs negative
        abs(s) for s in [len(neg) * -1]
    ):
        tier = "likely_soccer"
        note = "Weak soccer signal — human review recommended (metadata-only)"
    elif score <= -2.0:
        tier = "other"
        note = "Classified as non-soccer by metadata signals (not verified by watching)"
    elif score >= 1.0:
        tier = "likely_soccer"
        note = "Soccer term present — human review recommended (metadata-only)"
    else:
        tier = "uncertain"
        note = "No clear signal — excluded from soccer-only report (metadata-only)"

    return RelevanceResult(
        score=score,
        tier=tier,
        positive_signals=pos,
        negative_signals=neg,
        note=note,
    )


def age_tier(published_at: str) -> str:
    """
    Classify a video by publication age relative to today.

    RECENT_BREAKOUT  — published within 30 days (may still be accumulating views)
    RECENT_SUCCESS   — published 31–90 days ago
    EVERGREEN        — older than 90 days

    Age is computed from publication date only.
    Growth rate CANNOT be asserted from a single view-count snapshot.
    """
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - pub).days
    except Exception:
        return "EVERGREEN"

    if age_days <= 30:
        return "RECENT_BREAKOUT"
    if age_days <= 90:
        return "RECENT_SUCCESS"
    return "EVERGREEN"
