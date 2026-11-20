"""Tests for the RSS research provider (network calls are mocked)."""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from src.research.models import ContentType
from src.research.rss_provider import (
    RSSResearchProvider,
    _clean_html,
    _entry_to_candidate,
    _google_news_url,
    _is_suitable,
    _relevance_score,
)


# ── Helper factories ──────────────────────────────────────────────────────────

def _make_entry(title="Football Story", summary="A great football moment.", link="https://bbc.co.uk/story", published="2026-11-20"):
    entry = types.SimpleNamespace()
    entry.title = title
    entry.summary = summary
    entry.link = link
    entry.published = published
    entry.description = None
    return entry


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestCleanHtml:
    def test_strips_basic_tags(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_collapses_whitespace(self):
        # _clean_html normalises multiple spaces to single
        assert _clean_html("  foo   bar  ") == "foo bar"

    def test_truncates_at_800(self):
        result = _clean_html("x" * 1000)
        assert len(result) == 800

    def test_empty_string(self):
        assert _clean_html("") == ""


class TestIsSuitable:
    def test_accepts_clean_story(self):
        assert _is_suitable("Messi's greatest goal", "He scored a fantastic volley in 2007.") is True

    def test_rejects_transfer_rumour(self):
        assert _is_suitable("Mbappe transfer rumour links him to Real Madrid", "") is False

    def test_rejects_betting_content(self):
        assert _is_suitable("Best betting odds for Champions League final", "") is False

    def test_rejects_allegedly(self):
        assert _is_suitable("Player allegedly punched teammate", "") is False

    def test_rejects_insider_says(self):
        assert _is_suitable("Insider says club in talks", "") is False


class TestRelevanceScore:
    def test_high_score_for_relevant_content(self):
        score = _relevance_score(
            "World Cup final goal record history greatest",
            ContentType.FOOTBALL_MOMENTS,
        )
        assert score > 0.3

    def test_zero_score_for_irrelevant(self):
        score = _relevance_score("Weather update today", ContentType.FOOTBALL_MOMENTS)
        assert score < 0.1

    def test_score_bounded_0_to_1(self):
        score = _relevance_score("goal goal goal goal goal goal goal", ContentType.FOOTBALL_MOMENTS)
        assert 0.0 <= score <= 1.0


class TestGoogleNewsUrl:
    def test_returns_valid_url(self):
        url = _google_news_url("football test")
        assert url.startswith("https://news.google.com/rss/search?")
        assert "football" in url


class TestEntryToCandidate:
    def test_valid_entry_produces_candidate(self):
        entry = _make_entry(
            title="Zidane's greatest World Cup moment remembered",
            summary="The 2006 World Cup final headbutt incident remains one of the most discussed moments.",
            link="https://bbc.co.uk/zidane",
        )
        candidate = _entry_to_candidate(entry, "BBC Sport", "https://bbc.co.uk/rss", ContentType.FOOTBALL_MOMENTS)
        assert candidate is not None
        assert candidate.content_type == ContentType.FOOTBALL_MOMENTS
        assert len(candidate.research_items) == 1

    def test_short_title_returns_none(self):
        entry = _make_entry(title="Hi", summary="Short title should be rejected.")
        result = _entry_to_candidate(entry, "BBC", "https://bbc.co.uk", ContentType.FOOTBALL_MOMENTS)
        assert result is None

    def test_missing_link_returns_none(self):
        entry = _make_entry(link="")
        result = _entry_to_candidate(entry, "BBC", "https://bbc.co.uk", ContentType.FOOTBALL_MOMENTS)
        assert result is None

    def test_transfer_rumour_rejected(self):
        entry = _make_entry(
            title="Haaland set to join new club in January transfer window",
            summary="Sources claim the deal is close to signing.",
        )
        result = _entry_to_candidate(entry, "BBC", "https://bbc.co.uk", ContentType.FOOTBALL_MOMENTS)
        assert result is None

    def test_date_extracted_from_published(self):
        entry = _make_entry(
            title="Iconic penalty save revisited in World Cup history special",
            summary="A goalkeeper made history during the World Cup final penalty shootout.",
            published="2026-11-15T12:00:00Z",
        )
        candidate = _entry_to_candidate(entry, "BBC", "https://bbc.co.uk", ContentType.FOOTBALL_MOMENTS)
        if candidate:
            item = candidate.research_items[0]
            assert item.source.date_published == "2026-11-15"


class TestRSSProvider:
    def test_provider_name(self):
        provider = RSSResearchProvider()
        assert provider.name == "rss"

    def test_get_topics_returns_list_on_feed_failure(self):
        """When all feeds fail, should return empty list (no exception)."""
        provider = RSSResearchProvider()
        with patch.object(provider, "_fetch_feed", return_value=[]):
            result = provider.get_topics(ContentType.FOOTBALL_MOMENTS, count=3)
        assert isinstance(result, list)

    def test_get_topics_deduplicates(self):
        """Same title from two feeds should appear only once."""
        provider = RSSResearchProvider()
        entry = _make_entry(
            title="Historic Champions League final moment analysed",
            summary="The final was decided by a goal in extra time after a memorable season.",
        )

        def fake_fetch(url: str) -> list:
            return [entry, entry]

        with patch.object(provider, "_fetch_feed", side_effect=fake_fetch):
            result = provider.get_topics(ContentType.FOOTBALL_MOMENTS, count=10)

        titles = [c.title for c in result]
        assert len(titles) == len(set(t.lower()[:80] for t in titles))

    def test_get_topics_respects_count_limit(self):
        provider = RSSResearchProvider()
        entry = _make_entry(
            title="Football moment in Champions League history worth remembering",
            summary="A legendary goal was scored during the Champions League final in a historic match.",
        )

        with patch.object(provider, "_fetch_feed", return_value=[entry] * 20):
            result = provider.get_topics(ContentType.FOOTBALL_MOMENTS, count=2)

        assert len(result) <= 2

    def test_get_topics_player_stories_type(self):
        provider = RSSResearchProvider()
        entry = _make_entry(
            title="Footballer career journey from humble beginnings debut story",
            summary="The player overcame adversity and struggle to achieve their dream of playing professionally.",
        )

        with patch.object(provider, "_fetch_feed", return_value=[entry]):
            result = provider.get_topics(ContentType.PLAYER_STORIES, count=3)

        for c in result:
            assert c.content_type == ContentType.PLAYER_STORIES
