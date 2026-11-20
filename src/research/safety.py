"""
Content safety checker.

Runs twice per storyboard cycle:
  1. On incoming research items (before scoring)
  2. On the generated storyboard (before saving)

Returns a list of violation strings. An empty list means clean.
Never throws — it reports, the caller decides whether to reject.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.research.models import ResearchItem, Storyboard


# ── Banned patterns ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    category: str
    message: str


_RULES: list[_Rule] = [
    _Rule(
        re.compile(r"\b(bet|betting|odds|wager|wagering|gambl(?:e|ing)|bookmaker|stake(?:s)?|parlay)\b", re.I),
        "gambling",
        "Content references gambling or betting",
    ),
    _Rule(
        re.compile(r"\b(nsfw|pornograph\w*|explicit\s+content|sex\s+scandal)\b", re.I),
        "explicit",
        "Content contains explicit material references",
    ),
    _Rule(
        re.compile(r"\b(set\s+to\s+sign|close\s+to\s+signing|about\s+to\s+join|confirmed\s+transfer|transfer\s+fee\s+of)\b", re.I),
        "transfer_rumor",
        "Content contains unverified transfer claim language",
    ),
    _Rule(
        re.compile(r"\b(sources?\s+(claim|say|told|confirm)|insider\s+says|leak(?:ed)?)\b", re.I),
        "unverified_sourcing",
        "Content references unnamed or unverifiable sources",
    ),
    _Rule(
        re.compile(r"\b(earn\s+\$|win\s+big|make\s+money|financial\s+advice|invest\s+in)\b", re.I),
        "financial_promotion",
        "Content contains financial promotion language",
    ),
]

# Topics that are categorically rejected regardless of wording
_BANNED_TOPIC_KEYWORDS: list[str] = [
    "gambling", "betting odds", "sex scandal", "explicit",
    "violence against", "racial abuse", "hate speech",
]


# ── Public API ─────────────────────────────────────────────────────────────────

def check_text(text: str) -> list[str]:
    """Return a list of violation messages found in `text`."""
    violations: list[str] = []
    for rule in _RULES:
        if rule.pattern.search(text):
            violations.append(f"[{rule.category}] {rule.message}")
    return violations


def check_topic_title(title: str) -> list[str]:
    violations = check_text(title)
    lower = title.lower()
    for kw in _BANNED_TOPIC_KEYWORDS:
        if kw in lower:
            violations.append(f"[banned_topic] Title contains banned keyword: '{kw}'")
    return violations


def check_research_items(items: list[ResearchItem]) -> list[str]:
    """Screen all research items. Returns combined violation list."""
    all_violations: list[str] = []
    for i, item in enumerate(items):
        v = check_text(item.fact)
        if v:
            all_violations.extend(f"research_item[{i}]: {msg}" for msg in v)
    return all_violations


def check_storyboard(sb: Storyboard) -> list[str]:
    """Screen the generated storyboard narration and on-screen text."""
    violations: list[str] = []

    for scene in sb.scenes:
        v_narration = check_text(scene.narration)
        v_onscreen = check_text(scene.on_screen_text)
        v_visual = check_text(scene.visual_requirement)
        for msg in v_narration:
            violations.append(f"scene[{scene.scene_number}].narration: {msg}")
        for msg in v_onscreen:
            violations.append(f"scene[{scene.scene_number}].on_screen_text: {msg}")
        for msg in v_visual:
            violations.append(f"scene[{scene.scene_number}].visual_requirement: {msg}")

    # Reject any storyboard that claims specific footage is licensed
    footage_claim = re.compile(
        r"\b(official\s+footage|broadcast\s+clip|match\s+recording|tv\s+rights|licensed\s+clip)\b", re.I
    )
    for scene in sb.scenes:
        if footage_claim.search(scene.visual_requirement):
            violations.append(
                f"scene[{scene.scene_number}].visual_requirement: "
                "Claims specific footage is licensed — visual_requirement must describe "
                "the type of visual needed, not name specific clips"
            )

    return violations


def is_safe_research(items: list[ResearchItem]) -> tuple[bool, list[str]]:
    v = check_research_items(items)
    return len(v) == 0, v


def is_safe_storyboard(sb: Storyboard) -> tuple[bool, list[str]]:
    v = check_storyboard(sb)
    return len(v) == 0, v
