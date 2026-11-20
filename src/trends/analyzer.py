"""
Trend analysis and earnings model.

IMPORTANT — analysis honesty contract:
  All analysis of hook style, subject, emotional tone and storytelling structure
  is derived EXCLUSIVELY from video metadata (title, description if available,
  duration, view/like/comment counts). We cannot watch the videos via the API.

  Every MetadataAnalysis object has analysis_type="metadata_only".
  No claims are made about visual editing, camera angles, pacing or audio.

Viral tier classification:
  MEGA:    ≥ 10M views
  VIRAL:   ≥  1M views
  GROWING: ≥  100K views
  MODEST:  <  100K views
"""

from __future__ import annotations

import re

from src.core.logger import get_logger
from src.trends.models import (
    DiscoveredShort,
    EarningsScenario,
    MetadataAnalysis,
)

logger = get_logger(__name__)


# ── Keyword sets for metadata analysis ────────────────────────────────────────

_PLAYER_NAMES = {
    "messi", "ronaldo", "haaland", "mbappe", "neymar", "bellingham",
    "vinicius", "salah", "benzema", "modric", "de bruyne", "lewandowski",
    "zidane", "pele", "maradona", "ronaldinho", "beckham", "henry",
    "cantona", "rooney", "gerrard", "lampard", "giggs", "pires", "bergkamp",
    "van nistelrooy", "kaka", "ibrahimovic", "suarez", "drogba", "toure",
    "gazza", "gascoigne", "shearer", "inzaghi", "totti", "del piero",
    "r9", "cr7", "leo",
}

_SHOCK_WORDS = {
    "insane", "shocked", "unbelievable", "incredible", "nobody expected",
    "you won't believe", "craziest", "destroyed", "embarrassed", "humiliated",
    "never seen", "impossible", "world record", "greatest ever", "changed everything",
}

_EMOTION_WORDS = {
    "awe": {"incredible", "insane", "unbelievable", "greatest", "best ever",
             "world record", "perfect", "genius"},
    "inspiration": {"comeback", "never gave up", "believed", "dream", "journey",
                    "rise", "humble", "overcame", "legend", "inspiring"},
    "shock": {"shocked", "nobody expected", "you won't believe", "craziest",
               "destroyed", "embarrassed", "humiliated", "exposed"},
    "nostalgia": {"remember", "classic", "throwback", "forgotten", "golden",
                   "era", "childhood", "retro"},
    "sadness": {"tragedy", "crying", "tears", "heartbreaking", "farewell",
                 "died", "retired", "last time"},
}

_SUBJECT_PATTERNS = {
    "player_story": re.compile(
        r"\b(story|career|journey|life|rise|grew up|humble|forgotten|sad|died|cried|last)\b", re.I
    ),
    "goal_moment": re.compile(
        r"\b(goal|scored|volley|free kick|hat trick|bicycle kick|screamer|brace)\b", re.I
    ),
    "skill_moment": re.compile(
        r"\b(dribble|skill|trick|nutmeg|destroyed|embarrassed|humiliated|pace|sprint)\b", re.I
    ),
    "motivation": re.compile(
        r"\b(never give up|believe|dream|mindset|mindset|attitude|inspire|work hard|dedication)\b", re.I
    ),
    "controversy": re.compile(
        r"\b(banned|fight|argument|red card|conflict|drama|incident|war|scandal)\b", re.I
    ),
    "record_fact": re.compile(
        r"\b(record|most|ever|first|only|fastest|youngest|oldest|best|highest)\b", re.I
    ),
}


def analyse_short(short: DiscoveredShort) -> MetadataAnalysis:
    """
    Derive structural patterns from title text only.
    Returns a MetadataAnalysis with analysis_type='metadata_only'.
    """
    title = short.title
    title_lower = title.lower()
    words = title_lower.split()

    # Hook style detection from title
    if title.endswith("?"):
        hook_style = "question"
    elif any(w in title_lower for w in _SHOCK_WORDS):
        hook_style = "shocking_claim"
    elif re.search(r"\b\d+\b", title):
        hook_style = "number_or_stat"
    elif any(name in title_lower for name in _PLAYER_NAMES):
        hook_style = "player_name_led"
    else:
        hook_style = "narrative"

    # Subject category
    subject = "general_football"
    for cat, pattern in _SUBJECT_PATTERNS.items():
        if pattern.search(title):
            subject = cat
            break

    # Emotional tone
    tone = "neutral"
    for emotion, keywords in _EMOTION_WORDS.items():
        if any(kw in title_lower for kw in keywords):
            tone = emotion
            break

    # Structural flags
    has_number = bool(re.search(r"\b\d+\b", title))
    has_question = "?" in title
    has_name = any(name in title_lower for name in _PLAYER_NAMES)

    return MetadataAnalysis(
        video_id=short.video_id,
        analysis_type="metadata_only",
        hook_style=hook_style,
        subject_category=subject,
        emotional_tone=tone,
        title_word_count=len(words),
        title_has_number=has_number,
        title_has_question=has_question,
        title_has_name=has_name,
        notes=(
            f"Title only. No video content was accessed. "
            f"Duration: {short.duration_secs}s. "
            f"Views: {short.view_count:,}."
        ),
    )


def viral_tier(views: int) -> str:
    if views >= 10_000_000:
        return "MEGA"
    if views >= 1_000_000:
        return "VIRAL"
    if views >= 100_000:
        return "GROWING"
    return "MODEST"


def summarise_patterns(analyses: list[MetadataAnalysis]) -> dict:
    """Aggregate analysis across a set of Shorts. Returns frequency counts."""
    if not analyses:
        return {}

    def freq(lst: list) -> dict:
        d: dict = {}
        for x in lst:
            d[x] = d.get(x, 0) + 1
        return dict(sorted(d.items(), key=lambda kv: kv[1], reverse=True))

    return {
        "hook_styles": freq([a.hook_style for a in analyses]),
        "subject_categories": freq([a.subject_category for a in analyses]),
        "emotional_tones": freq([a.emotional_tone for a in analyses]),
        "pct_with_player_name": round(
            sum(a.title_has_name for a in analyses) / len(analyses) * 100
        ),
        "pct_with_number": round(
            sum(a.title_has_number for a in analyses) / len(analyses) * 100
        ),
        "pct_with_question": round(
            sum(a.title_has_question for a in analyses) / len(analyses) * 100
        ),
        "analysis_note": (
            "All pattern counts are derived from title text only (metadata_only). "
            "Video content was not inspected."
        ),
    }


# ── Earnings model ────────────────────────────────────────────────────────────

def build_earnings_scenarios(
    monthly_videos: int = 30,
) -> list[EarningsScenario]:
    """
    Build three RPM scenarios for a football Shorts channel.

    RPM reference ranges used:
      - YouTube Shorts creator share: 45% of ad revenue from Shorts feed ads
      - Sports category Shorts RPM (creator share): $0.03–$0.15 per 1,000 views
        (Based on publicly reported creator experiences; individual results vary widely)
      - These are NOT channel-specific figures. No competitor revenue is claimed.

    Average views per Short scenarios are illustrative, not forecasts.
    """
    return [
        EarningsScenario(
            scenario_name="conservative",
            rpm_usd=0.03,
            monthly_videos=monthly_videos,
            avg_views_per_short=50_000,
        ),
        EarningsScenario(
            scenario_name="mid",
            rpm_usd=0.07,
            monthly_videos=monthly_videos,
            avg_views_per_short=200_000,
        ),
        EarningsScenario(
            scenario_name="optimistic",
            rpm_usd=0.12,
            monthly_videos=monthly_videos,
            avg_views_per_short=800_000,
        ),
    ]


def earnings_report(scenarios: list[EarningsScenario]) -> str:
    lines = [
        "Hypothetical earnings model (football Shorts channel)",
        "Assumptions:",
        "  · RPM = creator's share per 1,000 Shorts feed views (sports category)",
        "  · Shorts RPM range: $0.03–$0.15 (publicly reported; individual results vary)",
        "  · No competitor-specific revenue data is used or implied",
        "  · Channel must qualify for Shorts monetisation (1,000 subs + 10M Shorts views in 90 days)",
        "",
    ]
    for s in scenarios:
        lines.append(s.report_line())
    return "\n".join(lines)
