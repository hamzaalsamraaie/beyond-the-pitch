"""
Transparent topic scorer.

Each dimension is computed independently and the final score is a weighted
sum of the five dimensions defined in config/settings.yaml under idea_scoring.

All scoring logic is deterministic and testable without any API calls.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from src.core.config import get_section
from src.research.models import ContentType, ScoredTopic, TopicCandidate, TopicScore


# ── Keyword signals used for audience_interest scoring ────────────────────────

_HIGH_INTEREST_TERMS: set[str] = {
    "messi", "ronaldo", "mbappé", "mbappe", "haaland", "neymar",
    "world cup", "champions league", "premier league", "la liga", "bundesliga",
    "goal", "hat trick", "hat-trick", "penalty", "final", "legend",
    "greatest", "best ever", "record", "historic", "comeback",
}

_EMOTIONAL_AMPLIFIERS: set[str] = {
    "overcame", "survived", "tragedy", "dream", "journey", "refused",
    "humble", "childhood", "poverty", "sacrifice", "inspiration",
    "tears", "emotional", "miracle", "underdog", "never gave up",
}

# Topics covered in the last N days penalise originality
_ORIGINALITY_WINDOW_DAYS = 90


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def _jaccard_similarity(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


# ── Scorer ─────────────────────────────────────────────────────────────────────

class TopicScorer:
    def __init__(
        self,
        existing_topics: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        cfg = get_section("idea_scoring")
        self.weights: dict[str, float] = weights or {
            "freshness": cfg.get("freshness", 0.20),
            "audience_interest": cfg.get("audience_interest", 0.25),
            "emotional_impact": cfg.get("emotional_impact", 0.25),
            "originality": cfg.get("originality", 0.20),
            "visual_feasibility": cfg.get("visual_feasibility", 0.10),
        }
        self.existing_topics: list[str] = existing_topics or []
        self._similarity_cutoff: float = get_section("research").get(
            "originality_similarity_cutoff", 0.55
        )

    # ── Individual dimension scorers ──────────────────────────────────────────

    def _score_freshness(self, candidate: TopicCandidate) -> float:
        """
        1.0 for content published < 7 days ago.
        0.8 for 7–30 days.
        0.6 for evergreen content (no date).
        0.4 for 30–180 days.
        0.2 for > 180 days.
        """
        today = date.today()
        dates = [
            _parse_date(item.source.date_published)
            for item in candidate.research_items
            if item.source.date_published
        ]
        if not dates:
            return 0.6  # evergreen — moderate freshness score

        most_recent = max(d for d in dates if d is not None)
        age_days = (today - most_recent).days

        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.8
        if age_days <= 180:
            return 0.4
        return 0.2

    def _score_audience_interest(self, candidate: TopicCandidate) -> float:
        """
        Score based on presence of high-interest football keywords in
        the topic title and summary. Max 1.0.
        """
        combined = (candidate.title + " " + candidate.summary).lower()
        matches = sum(1 for kw in _HIGH_INTEREST_TERMS if kw in combined)
        # 0 hits = 0.1, 1 = 0.4, 2 = 0.65, 3+ = 0.85+, capped at 1.0
        base = 0.1 + min(matches * 0.25, 0.9)
        return round(min(base, 1.0), 4)

    def _score_emotional_impact(self, candidate: TopicCandidate) -> float:
        """
        Score based on emotional amplifier keywords and content type.
        PLAYER_STORIES and FOOTBALL_MOTIVATION get a base boost.
        """
        combined = (candidate.title + " " + candidate.summary).lower()
        matches = sum(1 for kw in _EMOTIONAL_AMPLIFIERS if kw in combined)

        content_type_base = {
            ContentType.FOOTBALL_MOMENTS: 0.55,
            ContentType.PLAYER_STORIES: 0.70,
            ContentType.FOOTBALL_MOTIVATION: 0.75,
        }.get(candidate.content_type, 0.50)

        boost = min(matches * 0.08, 0.25)
        return round(min(content_type_base + boost, 1.0), 4)

    def _score_originality(self, candidate: TopicCandidate) -> float:
        """
        1.0 for a completely novel topic.
        Penalise by Jaccard similarity to any recently used topic.
        If any existing topic exceeds the similarity cutoff → 0.0.
        """
        if not self.existing_topics:
            return 1.0

        max_similarity = max(
            _jaccard_similarity(candidate.title, existing)
            for existing in self.existing_topics
        )

        if max_similarity >= self._similarity_cutoff:
            return 0.0
        # Linear decay: similarity 0 → 1.0 score, similarity at cutoff → 0.0
        return round(1.0 - (max_similarity / self._similarity_cutoff), 4)

    def _score_visual_feasibility(self, candidate: TopicCandidate) -> float:
        """
        Score based on whether the topic can be illustrated with
        generic graphics/text rather than requiring specific licensed footage.

        FOOTBALL_MOTIVATION is easiest to illustrate (0.90 base).
        FOOTBALL_MOMENTS requires more specific visuals (0.55 base).
        PLAYER_STORIES can often use archive-style graphics (0.70 base).
        """
        return {
            ContentType.FOOTBALL_MOMENTS: 0.55,
            ContentType.PLAYER_STORIES: 0.70,
            ContentType.FOOTBALL_MOTIVATION: 0.90,
        }.get(candidate.content_type, 0.60)

    # ── Main scoring method ───────────────────────────────────────────────────

    def score(self, candidate: TopicCandidate) -> ScoredTopic:
        ts = TopicScore(
            freshness=self._score_freshness(candidate),
            audience_interest=self._score_audience_interest(candidate),
            emotional_impact=self._score_emotional_impact(candidate),
            originality=self._score_originality(candidate),
            visual_feasibility=self._score_visual_feasibility(candidate),
        )
        total = ts.total(self.weights)
        breakdown = ts.breakdown(self.weights)
        return ScoredTopic(
            candidate=candidate,
            score=ts,
            total_score=total,
            score_breakdown=breakdown,
        )

    def rank(self, candidates: list[TopicCandidate]) -> list[ScoredTopic]:
        """Score all candidates and return sorted by total_score descending."""
        scored = [self.score(c) for c in candidates]
        return sorted(scored, key=lambda s: s.total_score, reverse=True)
