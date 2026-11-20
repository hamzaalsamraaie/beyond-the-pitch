"""
Research provider interface.

ResearchProvider (ABC)
  └─ MockResearchProvider  — deterministic fixture data, no network calls
  └─ WikipediaResearchProvider — free public Wikipedia REST API, no auth needed

Providers return TopicCandidate objects with verified source citations.
They must NOT fabricate facts or invent source URLs.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from src.core.logger import get_logger
from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    TopicCandidate,
)

logger = get_logger(__name__)


# ── Abstract base ─────────────────────────────────────────────────────────────

class ResearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_topics(
        self,
        content_type: ContentType,
        count: int = 3,
    ) -> list[TopicCandidate]:
        """
        Return up to `count` topic candidates of the given content type.
        Each TopicCandidate must include at least one ResearchItem with a
        real, verifiable source URL.
        """
        ...


# ── Mock provider ─────────────────────────────────────────────────────────────
#
# Fixture data covers historical events that are publicly documented.
# All Wikipedia URLs are real and stable.
# IMPORTANT: This data is for testing and demonstration only.
# It should NOT be used as current news or presented as recent events.

_MOCK_DATA: dict[ContentType, list[TopicCandidate]] = {

    ContentType.FOOTBALL_MOMENTS: [
        TopicCandidate(
            title="Zinedine Zidane's volley in the 2002 Champions League Final",
            content_type=ContentType.FOOTBALL_MOMENTS,
            summary=(
                "Zinedine Zidane scored what many consider the greatest goal in "
                "Champions League history — a left-footed volley in the 45th minute "
                "of the 2002 final between Real Madrid and Bayer Leverkusen in Glasgow."
            ),
            suggested_hook="THE GREATEST GOAL EVER?",
            research_items=[
                ResearchItem(
                    fact=(
                        "Zinedine Zidane scored a left-footed volley in the 45th minute "
                        "of the UEFA Champions League Final on 15 May 2002 at Hampden Park, "
                        "Glasgow. Real Madrid won 2–1 against Bayer Leverkusen."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/2002_UEFA_Champions_League_final",
                        title="2002 UEFA Champions League Final",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
                ResearchItem(
                    fact=(
                        "The goal was voted the greatest goal in Champions League history "
                        "in a poll conducted by UEFA in 2012."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/Zinedine_Zidane",
                        title="Zinedine Zidane",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="unverified",
                ),
            ],
        ),
        TopicCandidate(
            title="Lionel Messi's Goal of the Century vs Getafe (2007)",
            content_type=ContentType.FOOTBALL_MOMENTS,
            summary=(
                "In April 2007, Lionel Messi scored a goal for Barcelona against Getafe "
                "that drew direct comparisons to Diego Maradona's famous 1986 World Cup goal. "
                "Messi dribbled from his own half past five defenders and the goalkeeper."
            ),
            suggested_hook="MESSI CHANNELS MARADONA",
            research_items=[
                ResearchItem(
                    fact=(
                        "On 18 April 2007, Lionel Messi scored a goal for FC Barcelona "
                        "against Getafe CF in the Copa del Rey semi-final, dribbling from "
                        "his own half and beating five outfield players and the goalkeeper."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/Lionel_Messi",
                        title="Lionel Messi",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
            ],
        ),
    ],

    ContentType.PLAYER_STORIES: [
        TopicCandidate(
            title="Didier Drogba's role in Ivory Coast's peace agreement",
            content_type=ContentType.PLAYER_STORIES,
            summary=(
                "After Ivory Coast qualified for the 2006 FIFA World Cup, Didier Drogba "
                "made an emotional televised appeal to end the country's civil war. "
                "His plea is credited with contributing to a brief ceasefire."
            ),
            suggested_hook="ONE SPEECH STOPPED A WAR",
            research_items=[
                ResearchItem(
                    fact=(
                        "In October 2005, following Ivory Coast's qualification for the "
                        "2006 FIFA World Cup, Didier Drogba knelt on the pitch and made "
                        "a televised plea to warring factions to lay down their weapons. "
                        "The government and rebels subsequently agreed to a ceasefire."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/Didier_Drogba",
                        title="Didier Drogba",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
            ],
        ),
        TopicCandidate(
            title="Ronaldo (R9) overcame a heart condition to win the 1994 World Cup",
            content_type=ContentType.PLAYER_STORIES,
            summary=(
                "Brazilian striker Ronaldo Nazário was diagnosed with a heart condition "
                "and experienced a seizure the night before the 1998 World Cup final. "
                "Despite this, he played in the final. He went on to win the World Cup "
                "in 2002 as the tournament's top scorer."
            ),
            suggested_hook="HE SHOULDN'T HAVE PLAYED",
            research_items=[
                ResearchItem(
                    fact=(
                        "On the eve of the 1998 FIFA World Cup Final, Ronaldo Nazário "
                        "suffered a convulsive fit at the team hotel. He was initially "
                        "left off the starting lineup before being reinstated hours before "
                        "kick-off. Brazil lost 3–0 to France."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/Ronaldo_(Brazilian_footballer)",
                        title="Ronaldo (Brazilian footballer)",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
                ResearchItem(
                    fact=(
                        "In the 2002 FIFA World Cup, Ronaldo Nazário scored eight goals "
                        "to win the Golden Boot and led Brazil to the championship, "
                        "defeating Germany 2–0 in the final."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/2002_FIFA_World_Cup",
                        title="2002 FIFA World Cup",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
            ],
        ),
    ],

    ContentType.FOOTBALL_MOTIVATION: [
        TopicCandidate(
            title="N'Golo Kanté: from amateur football to two league titles and a World Cup",
            content_type=ContentType.FOOTBALL_MOTIVATION,
            summary=(
                "N'Golo Kanté was playing for an amateur club in France aged 19 and "
                "was rejected by several professional academies for being too small. "
                "He went on to win the Premier League twice, the FIFA World Cup, "
                "and the UEFA Champions League."
            ),
            suggested_hook="TOO SMALL TO PLAY PRO?",
            research_items=[
                ResearchItem(
                    fact=(
                        "N'Golo Kanté played for US Boulogne's reserve team and amateur "
                        "sides until age 19, having been rejected by professional clubs "
                        "who considered him too small. He stood 5 ft 6 in (168 cm)."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/N%27Golo_Kant%C3%A9",
                        title="N'Golo Kanté",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
                ResearchItem(
                    fact=(
                        "Kanté won the Premier League with Leicester City in 2015–16 and "
                        "with Chelsea in 2016–17, was named PFA Players' Player of the Year "
                        "in 2017, and won the 2018 FIFA World Cup with France."
                    ),
                    source=SourceCitation(
                        url="https://en.wikipedia.org/wiki/N%27Golo_Kant%C3%A9",
                        title="N'Golo Kanté",
                        publisher="Wikipedia",
                        date_published="",
                    ),
                    reliability="verified",
                ),
            ],
        ),
    ],
}


class MockResearchProvider(ResearchProvider):
    """
    Returns hardcoded football facts for testing and demonstration.
    No network calls are made.

    IMPORTANT: All data is for demonstration purposes only.
    Do not present this content as current news or recent events.
    """

    @property
    def name(self) -> str:
        return "mock"

    def get_topics(
        self,
        content_type: ContentType,
        count: int = 3,
    ) -> list[TopicCandidate]:
        topics = _MOCK_DATA.get(content_type, [])
        return topics[:count]


# ── Wikipedia provider ────────────────────────────────────────────────────────

_WIKIPEDIA_QUERIES: dict[ContentType, list[str]] = {
    ContentType.FOOTBALL_MOMENTS: [
        "famous football goals history",
        "greatest UEFA Champions League moments",
        "iconic FIFA World Cup goals",
    ],
    ContentType.PLAYER_STORIES: [
        "football player adversity story biography",
        "footballer humble beginnings career",
    ],
    ContentType.FOOTBALL_MOTIVATION: [
        "football player inspirational story",
        "footballer overcome adversity",
    ],
}

_WIKIPEDIA_SEARCH_API = "https://en.wikipedia.org/w/api.php"
_WIKIPEDIA_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_REQUEST_DELAY = 1.0  # seconds between Wikipedia requests


class WikipediaResearchProvider(ResearchProvider):
    """
    Fetches summaries from the Wikipedia public REST API.
    No authentication required.

    Returns TopicCandidates with Wikipedia as the source citation.
    Pages returned are always real Wikipedia articles — the URLs are verifiable.

    Limitations:
    - Wikipedia summaries are evergreen; they do not reflect current events.
    - Facts should be independently verified before publication.
    """

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "BeyondThePitch/0.2 (football-shorts-project; educational use)"
        )

    @property
    def name(self) -> str:
        return "wikipedia"

    def _search(self, query: str, limit: int = 3) -> list[str]:
        """Return up to `limit` Wikipedia page titles matching `query`."""
        try:
            resp = self._session.get(
                _WIKIPEDIA_SEARCH_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": limit,
                    "format": "json",
                    "srprop": "snippet",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])
            return [r["title"] for r in results]
        except Exception as exc:
            logger.warning("wikipedia_search_failed", query=query, error=str(exc))
            return []

    def _get_summary(self, title: str) -> dict | None:
        """Fetch the Wikipedia REST summary for a page title."""
        try:
            time.sleep(_REQUEST_DELAY)
            url = _WIKIPEDIA_SUMMARY_API.format(title=title.replace(" ", "_"))
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("wikipedia_summary_failed", title=title, error=str(exc))
            return None

    def _summary_to_candidate(
        self, summary: dict, content_type: ContentType
    ) -> TopicCandidate | None:
        extract = summary.get("extract", "").strip()
        title = summary.get("title", "").strip()
        page_url = summary.get("content_urls", {}).get("desktop", {}).get("page", "")

        if not extract or not title or not page_url:
            return None

        # Use the first two sentences as a research item fact
        sentences = extract.split(". ")
        fact_text = ". ".join(sentences[:2]).strip()
        if len(fact_text) < 20:
            return None

        try:
            item = ResearchItem(
                fact=fact_text,
                source=SourceCitation(
                    url=page_url,
                    title=title,
                    publisher="Wikipedia",
                    date_published="",
                ),
                reliability="unverified",
            )
        except Exception as exc:
            logger.warning("wikipedia_item_rejected", title=title, reason=str(exc))
            return None

        return TopicCandidate(
            title=title,
            content_type=content_type,
            summary=extract[:500],
            research_items=[item],
        )

    def get_topics(
        self,
        content_type: ContentType,
        count: int = 3,
    ) -> list[TopicCandidate]:
        queries = _WIKIPEDIA_QUERIES.get(content_type, [])
        candidates: list[TopicCandidate] = []
        seen_titles: set[str] = set()

        for query in queries:
            if len(candidates) >= count:
                break
            titles = self._search(query, limit=count)
            for title in titles:
                if title in seen_titles or len(candidates) >= count:
                    continue
                seen_titles.add(title)
                summary = self._get_summary(title)
                if not summary:
                    continue
                candidate = self._summary_to_candidate(summary, content_type)
                if candidate:
                    candidates.append(candidate)

        logger.info(
            "wikipedia_topics_fetched",
            content_type=content_type.value,
            count=len(candidates),
        )
        return candidates
