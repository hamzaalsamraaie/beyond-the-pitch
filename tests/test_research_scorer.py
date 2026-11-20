"""Tests for the transparent topic scorer."""

from datetime import date, timedelta

import pytest

from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    TopicCandidate,
)
from src.research.scorer import TopicScorer, _jaccard_similarity


# ── Helpers ────────────────────────────────────────────────────────────────────

def _candidate(
    title: str = "Pelé scores 1000th goal",
    content_type: ContentType = ContentType.FOOTBALL_MOMENTS,
    summary: str = "Pelé scored his 1000th career goal in 1969.",
    date_published: str = "",
) -> TopicCandidate:
    return TopicCandidate(
        title=title,
        content_type=content_type,
        summary=summary,
        research_items=[
            ResearchItem(
                fact="Pelé scored his 1000th professional goal on 19 November 1969.",
                source=SourceCitation(
                    url="https://en.wikipedia.org/wiki/Pel%C3%A9",
                    title="Pelé",
                    publisher="Wikipedia",
                    date_published=date_published,
                ),
            )
        ],
    )


# ── Jaccard similarity ─────────────────────────────────────────────────────────

def test_jaccard_identical():
    assert _jaccard_similarity("messi goal final", "messi goal final") == 1.0


def test_jaccard_no_overlap():
    sim = _jaccard_similarity("messi goal final", "weather today sunny")
    assert sim == 0.0


def test_jaccard_partial():
    sim = _jaccard_similarity("messi goal final champions", "messi goal premier league")
    assert 0.0 < sim < 1.0


# ── Freshness scoring ──────────────────────────────────────────────────────────

def test_freshness_very_recent():
    today = date.today().strftime("%Y-%m-%d")
    c = _candidate(date_published=today)
    scorer = TopicScorer()
    result = scorer._score_freshness(c)
    assert result == 1.0


def test_freshness_last_week():
    week_ago = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    c = _candidate(date_published=week_ago)
    result = TopicScorer()._score_freshness(c)
    assert result == 1.0


def test_freshness_last_month():
    three_weeks = (date.today() - timedelta(days=20)).strftime("%Y-%m-%d")
    c = _candidate(date_published=three_weeks)
    result = TopicScorer()._score_freshness(c)
    assert result == 0.8


def test_freshness_old_content():
    old = (date.today() - timedelta(days=200)).strftime("%Y-%m-%d")
    c = _candidate(date_published=old)
    result = TopicScorer()._score_freshness(c)
    assert result == 0.2


def test_freshness_evergreen_no_date():
    c = _candidate(date_published="")  # no date
    result = TopicScorer()._score_freshness(c)
    assert result == 0.6


# ── Audience interest scoring ──────────────────────────────────────────────────

def test_audience_interest_high_profile_names():
    c = _candidate(
        title="Messi and Ronaldo face off in Champions League final",
        summary="A historic match between two legends.",
    )
    result = TopicScorer()._score_audience_interest(c)
    assert result > 0.6


def test_audience_interest_low_profile():
    c = _candidate(
        title="A local amateur match in 1934",
        summary="Two teams played a game last century.",
    )
    result = TopicScorer()._score_audience_interest(c)
    assert result < 0.5


# ── Emotional impact scoring ───────────────────────────────────────────────────

def test_emotional_impact_motivation_has_base_boost():
    c = _candidate(content_type=ContentType.FOOTBALL_MOTIVATION)
    result = TopicScorer()._score_emotional_impact(c)
    assert result >= 0.75


def test_emotional_impact_amplifier_keywords():
    c = _candidate(
        content_type=ContentType.PLAYER_STORIES,
        summary="He overcame poverty and sacrifice to reach his dream.",
    )
    result = TopicScorer()._score_emotional_impact(c)
    assert result > 0.70


# ── Originality scoring ────────────────────────────────────────────────────────

def test_originality_novel_topic():
    c = _candidate(title="Something completely new and unrelated")
    scorer = TopicScorer(existing_topics=["Messi Champions League goal 2015"])
    result = scorer._score_originality(c)
    assert result == 1.0


def test_originality_duplicate_topic():
    title = "Pelé scores 1000th goal career milestone"
    c = _candidate(title=title)
    scorer = TopicScorer(existing_topics=[title])
    result = scorer._score_originality(c)
    assert result == 0.0


def test_originality_similar_topic_penalised():
    c = _candidate(title="Pelé scores 1000th career goal in stadium")
    scorer = TopicScorer(
        existing_topics=["Pelé scores 1000th career goal"],
        weights={"freshness": 0.2, "audience_interest": 0.25,
                 "emotional_impact": 0.25, "originality": 0.2, "visual_feasibility": 0.1},
    )
    result = scorer._score_originality(c)
    assert result < 1.0


def test_originality_no_existing_topics():
    c = _candidate()
    result = TopicScorer(existing_topics=[])._score_originality(c)
    assert result == 1.0


# ── Visual feasibility ─────────────────────────────────────────────────────────

def test_visual_feasibility_motivation_highest():
    c_motiv = _candidate(content_type=ContentType.FOOTBALL_MOTIVATION)
    c_moment = _candidate(content_type=ContentType.FOOTBALL_MOMENTS)
    scorer = TopicScorer()
    assert scorer._score_visual_feasibility(c_motiv) > scorer._score_visual_feasibility(c_moment)


# ── Full score ─────────────────────────────────────────────────────────────────

def test_full_score_in_range():
    c = _candidate()
    scored = TopicScorer().score(c)
    assert 0.0 <= scored.total_score <= 1.0


def test_score_breakdown_sums_to_total():
    c = _candidate()
    scored = TopicScorer().score(c)
    total_from_breakdown = round(sum(scored.score_breakdown.values()), 4)
    assert abs(total_from_breakdown - scored.total_score) < 0.001


def test_rank_returns_sorted_descending():
    candidates = [
        _candidate("Low interest obscure 1908 match in Belgium"),
        _candidate("Messi Ronaldo Champions League greatest goal world cup"),
    ]
    scored = TopicScorer().rank(candidates)
    assert scored[0].total_score >= scored[1].total_score
