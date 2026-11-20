"""
RSS-based research provider for current football news.

Reads from free public RSS feeds (BBC Sport, Sky Sports, ESPN, Google News).
Converts recent headlines into TopicCandidate objects for the StoryboardPipeline.

No authentication required. All sources are public RSS.
Facts extracted from RSS summaries are marked 'unverified' — the pipeline's
safety filter and human review gate determine what actually gets published.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlencode

import feedparser

from src.core.logger import get_logger
from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    TopicCandidate,
)
from src.research.providers import ResearchProvider

logger = get_logger(__name__)

_REQUEST_DELAY = 0.5  # seconds between feed fetches


def _google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })


# Public RSS feeds — no API keys needed
_FEEDS: dict[ContentType, list[tuple[str, str]]] = {
    ContentType.FOOTBALL_MOMENTS: [
        ("BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
        ("Sky Sports Football", "https://www.skysports.com/rss/12040"),
        ("ESPN FC", "https://www.espn.com/espn/rss/soccer/news"),
    ],
    ContentType.PLAYER_STORIES: [
        ("BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
        ("Sky Sports Football", "https://www.skysports.com/rss/12040"),
        ("Google News Football", _google_news_url("football player story biography")),
    ],
    ContentType.FOOTBALL_MOTIVATION: [
        ("BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
        ("Google News Football", _google_news_url("football inspirational comeback story")),
    ],
}

# Keywords that increase relevance for each content type
_RELEVANCE_KEYWORDS: dict[ContentType, list[str]] = {
    ContentType.FOOTBALL_MOMENTS: [
        "goal", "save", "record", "final", "champion", "world cup", "penalty",
        "hat-trick", "historic", "unforgettable", "legendary", "greatest",
    ],
    ContentType.PLAYER_STORIES: [
        "career", "journey", "overcome", "struggle", "rise", "biography",
        "childhood", "debut", "transfer", "retirement", "comeback",
    ],
    ContentType.FOOTBALL_MOTIVATION: [
        "inspire", "inspirational", "motivation", "comeback", "dream",
        "perseverance", "humble", "adversity", "breakthrough", "believe",
    ],
}

# Keywords that make an entry unsuitable for our channel
_REJECTION_KEYWORDS = [
    "transfer rumour", "close to signing", "set to join", "reportedly",
    "allegedly", "sources claim", "insider", "exclusive deal", "wages",
    "agent", "contract extension", "loan move", "bid rejected",
    "gambling", "betting", "odds", "fantasy football",
]


def _relevance_score(text: str, content_type: ContentType) -> float:
    lower = text.lower()
    keywords = _RELEVANCE_KEYWORDS.get(content_type, [])
    matches = sum(1 for kw in keywords if kw in lower)
    return min(1.0, matches / max(1, len(keywords) * 0.3))


def _is_suitable(title: str, summary: str) -> bool:
    combined = (title + " " + summary).lower()
    return not any(kw in combined for kw in _REJECTION_KEYWORDS)


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]


def _entry_to_candidate(
    entry: "feedparser.FeedParserDict",
    source_name: str,
    feed_url: str,
    content_type: ContentType,
) -> TopicCandidate | None:
    title = _clean_html(getattr(entry, "title", "") or "")
    summary = _clean_html(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
    link = getattr(entry, "link", "") or ""
    published = getattr(entry, "published", "") or ""

    if not title or len(title) < 10:
        return None
    if not summary or len(summary) < 20:
        summary = title  # fall back to title as the summary
    if not link:
        return None
    if not _is_suitable(title, summary):
        return None

    # Truncate ISO date to YYYY-MM-DD if present
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", published)
    date_str = date_match.group(0) if date_match else ""

    try:
        item = ResearchItem(
            fact=f"{title}. {summary[:300]}".strip(),
            source=SourceCitation(
                url=link,
                title=title[:200],
                publisher=source_name,
                date_published=date_str,
            ),
            reliability="unverified",
        )
    except Exception as exc:
        logger.debug("rss_item_rejected", title=title[:60], reason=str(exc))
        return None

    score = _relevance_score(title + " " + summary, content_type)
    if score < 0.1:
        return None

    return TopicCandidate(
        title=title[:200],
        content_type=content_type,
        summary=summary[:800],
        research_items=[item],
        suggested_hook="",
    )


class RSSResearchProvider(ResearchProvider):
    """
    Fetches current football news from public RSS feeds.

    All facts are marked 'unverified'. The pipeline's safety filter and
    score threshold ensure only suitable topics enter production.

    Falls back gracefully if a feed is unavailable.
    """

    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "rss"

    def _fetch_feed(self, url: str) -> list:
        try:
            feed = feedparser.parse(url, request_headers={
                "User-Agent": "BeyondThePitch/0.3 (football-shorts; RSS reader)",
            })
            return feed.entries or []
        except Exception as exc:
            logger.warning("rss_feed_failed", url=url[:80], error=str(exc))
            return []

    def get_topics(
        self,
        content_type: ContentType,
        count: int = 5,
    ) -> list[TopicCandidate]:
        feeds = _FEEDS.get(content_type, [])
        candidates: list[TopicCandidate] = []
        seen_titles: set[str] = set()

        for source_name, feed_url in feeds:
            if len(candidates) >= count:
                break
            entries = self._fetch_feed(feed_url)
            time.sleep(_REQUEST_DELAY)

            for entry in entries:
                if len(candidates) >= count:
                    break
                candidate = _entry_to_candidate(entry, source_name, feed_url, content_type)
                if candidate is None:
                    continue
                norm = candidate.title.lower()[:80]
                if norm in seen_titles:
                    continue
                seen_titles.add(norm)
                candidates.append(candidate)

        logger.info(
            "rss_topics_fetched",
            content_type=content_type.value,
            count=len(candidates),
        )
        return candidates
