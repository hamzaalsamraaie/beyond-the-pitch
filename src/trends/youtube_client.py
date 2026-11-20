"""
YouTube Data API v3 client with quota budget tracking and SQLite caching.

Quota costs (units per call):
  search.list    100 units  — used for discovery queries
  videos.list      1 unit  — used for batch stats fetching
  channels.list    1 unit  — used for channel profiling

Free tier: 10,000 units/day per project.
This client enforces a daily ceiling (default 8,000) stored in the DB.
A hard stop at 9,000 is applied regardless of the configured ceiling.

Mock mode: set api_key=None or YOUTUBE_API_KEY="" — returns fixture data
so all tests run fully offline without consuming quota.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import isodate

import src.core.database as db_module
from src.core.logger import get_logger

logger = get_logger(__name__)

HARD_QUOTA_CEILING = 9_000
DEFAULT_QUOTA_BUDGET = 8_000

# Cost in units for each API method
QUOTA_COST = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
}


# ── Quota tracking (stored in api_usage table) ────────────────────────────────

def _quota_used_today() -> int:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(tokens_used), 0) as total
               FROM api_usage
               WHERE provider = 'youtube_data_api'
               AND request_date = date('now')""",
        ).fetchone()
    return int(row[0]) if row else 0


def _charge_quota(units: int, detail: str) -> None:
    db_module.record_api_usage("youtube_data_api", units, detail)
    logger.info("youtube_quota_charged", units=units, detail=detail,
                total_today=_quota_used_today())


def _check_quota(units_needed: int, budget: int) -> None:
    used = _quota_used_today()
    if used + units_needed > HARD_QUOTA_CEILING:
        raise RuntimeError(
            f"YouTube quota hard ceiling reached: {used} used today, "
            f"need {units_needed} more (ceiling {HARD_QUOTA_CEILING})."
        )
    if used + units_needed > budget:
        raise RuntimeError(
            f"YouTube quota budget exceeded: {used} used today, "
            f"need {units_needed} more (budget {budget}). "
            "Increase trends.quota_daily_budget in settings.yaml or wait until tomorrow."
        )


# ── Duration parser ───────────────────────────────────────────────────────────

def parse_duration_secs(iso_duration: str) -> int:
    """Convert ISO 8601 duration (PT45S, PT1M30S) to seconds."""
    try:
        td = isodate.parse_duration(iso_duration)
        return int(td.total_seconds())
    except Exception:
        return 0


# ── Mock fixture data ─────────────────────────────────────────────────────────
# Used when api_key is absent. Clearly labeled as fixture data throughout.

_MOCK_SEARCH_RESULTS: list[dict] = [
    # Evergreen high-performer style
    {"id": {"videoId": "mock_ev01"}, "snippet": {
        "title": "Ronaldo's INSANE free kick that shocked the world",
        "channelId": "UCmock01", "channelTitle": "Football Moments",
        "publishedAt": "2023-03-15T10:00:00Z"}},
    {"id": {"videoId": "mock_ev02"}, "snippet": {
        "title": "Messi dribbles past 7 players | Greatest Goal",
        "channelId": "UCmock02", "channelTitle": "Porsevio",
        "publishedAt": "2023-05-20T10:00:00Z"}},
    {"id": {"videoId": "mock_ev03"}, "snippet": {
        "title": "The day Zidane's career ended forever",
        "channelId": "UCmock03", "channelTitle": "Football Stories",
        "publishedAt": "2023-07-10T10:00:00Z"}},
    {"id": {"videoId": "mock_ev04"}, "snippet": {
        "title": "Gazza crying at Italia 90 is still heartbreaking",
        "channelId": "UCmock04", "channelTitle": "Classic Football",
        "publishedAt": "2022-11-05T10:00:00Z"}},
    {"id": {"videoId": "mock_ev05"}, "snippet": {
        "title": "The 10 year old who embarrassed Pele",
        "channelId": "UCmock01", "channelTitle": "Football Moments",
        "publishedAt": "2023-09-01T10:00:00Z"}},
    # Recent viral style
    {"id": {"videoId": "mock_rv01"}, "snippet": {
        "title": "Nobody expected this tackle from Vinicius Jr",
        "channelId": "UCmock05", "channelTitle": "Real Madrid Clips",
        "publishedAt": "2024-10-01T10:00:00Z"}},
    {"id": {"videoId": "mock_rv02"}, "snippet": {
        "title": "Haaland scored before he even had boots on",
        "channelId": "UCmock06", "channelTitle": "Football Facts",
        "publishedAt": "2024-10-10T10:00:00Z"}},
    {"id": {"videoId": "mock_rv03"}, "snippet": {
        "title": "Bellingham's response to being called average",
        "channelId": "UCmock05", "channelTitle": "Real Madrid Clips",
        "publishedAt": "2024-10-18T10:00:00Z"}},
    {"id": {"videoId": "mock_rv04"}, "snippet": {
        "title": "The goalkeeper who never spoke again after this save",
        "channelId": "UCmock07", "channelTitle": "GK Stories",
        "publishedAt": "2024-11-01T10:00:00Z"}},
    {"id": {"videoId": "mock_rv05"}, "snippet": {
        "title": "Why every defender feared Ronaldo in 2008",
        "channelId": "UCmock02", "channelTitle": "Porsevio",
        "publishedAt": "2024-11-05T10:00:00Z"}},
]

_MOCK_VIDEO_STATS: dict[str, dict] = {
    "mock_ev01": {"statistics": {"viewCount": "8200000", "likeCount": "340000", "commentCount": "12000"},
                  "contentDetails": {"duration": "PT52S"}},
    "mock_ev02": {"statistics": {"viewCount": "15600000", "likeCount": "620000", "commentCount": "28000"},
                  "contentDetails": {"duration": "PT47S"}},
    "mock_ev03": {"statistics": {"viewCount": "5800000", "likeCount": "210000", "commentCount": "9500"},
                  "contentDetails": {"duration": "PT58S"}},
    "mock_ev04": {"statistics": {"viewCount": "3400000", "likeCount": "180000", "commentCount": "7200"},
                  "contentDetails": {"duration": "PT43S"}},
    "mock_ev05": {"statistics": {"viewCount": "11200000", "likeCount": "480000", "commentCount": "21000"},
                  "contentDetails": {"duration": "PT55S"}},
    "mock_rv01": {"statistics": {"viewCount": "2900000", "likeCount": "120000", "commentCount": "4300"},
                  "contentDetails": {"duration": "PT38S"}},
    "mock_rv02": {"statistics": {"viewCount": "4100000", "likeCount": "195000", "commentCount": "8800"},
                  "contentDetails": {"duration": "PT42S"}},
    "mock_rv03": {"statistics": {"viewCount": "1800000", "likeCount": "78000", "commentCount": "2900"},
                  "contentDetails": {"duration": "PT35S"}},
    "mock_rv04": {"statistics": {"viewCount": "3300000", "likeCount": "143000", "commentCount": "5600"},
                  "contentDetails": {"duration": "PT50S"}},
    "mock_rv05": {"statistics": {"viewCount": "5600000", "likeCount": "240000", "commentCount": "11200"},
                  "contentDetails": {"duration": "PT44S"}},
}

_MOCK_CHANNEL_STATS: dict[str, dict] = {
    "UCmock01": {"statistics": {"subscriberCount": "280000", "videoCount": "340", "viewCount": "95000000"},
                 "snippet": {"title": "Football Moments", "country": "GB", "description": "Best football moments"}},
    "UCmock02": {"statistics": {"subscriberCount": "1200000", "videoCount": "580", "viewCount": "420000000"},
                 "snippet": {"title": "Porsevio", "country": "PT", "description": "Football stories and moments"}},
    "UCmock03": {"statistics": {"subscriberCount": "95000", "videoCount": "190", "viewCount": "31000000"},
                 "snippet": {"title": "Football Stories", "country": "GB", "description": "Football stories"}},
    "UCmock04": {"statistics": {"subscriberCount": "450000", "videoCount": "720", "viewCount": "180000000"},
                 "snippet": {"title": "Classic Football", "country": "GB", "description": "Classic football content"}},
    "UCmock05": {"statistics": {"subscriberCount": "380000", "videoCount": "290", "viewCount": "120000000"},
                 "snippet": {"title": "Real Madrid Clips", "country": "ES", "description": "Real Madrid highlights"}},
    "UCmock06": {"statistics": {"subscriberCount": "160000", "videoCount": "210", "viewCount": "52000000"},
                 "snippet": {"title": "Football Facts", "country": "DE", "description": "Football facts"}},
    "UCmock07": {"statistics": {"subscriberCount": "72000", "videoCount": "150", "viewCount": "18000000"},
                 "snippet": {"title": "GK Stories", "country": "GB", "description": "Goalkeeper stories"}},
}


# ── Client ────────────────────────────────────────────────────────────────────

class YouTubeClient:
    """
    Thin wrapper around YouTube Data API v3.

    api_key=None → mock mode (fixture data, no network, no quota).
    quota_budget sets the daily soft ceiling (default 8,000 units).
    """

    def __init__(
        self,
        api_key: str | None = None,
        quota_budget: int = DEFAULT_QUOTA_BUDGET,
    ) -> None:
        self._key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self._budget = quota_budget
        self._mock = not bool(self._key)
        if self._mock:
            logger.info("youtube_client_mock_mode",
                        reason="No YOUTUBE_API_KEY — using fixture data")
        else:
            logger.info("youtube_client_live_mode")

    @property
    def is_mock(self) -> bool:
        return self._mock

    def quota_used_today(self) -> int:
        return _quota_used_today()

    def quota_breakdown_today(self) -> dict:
        """
        Return a per-method breakdown of quota used today, read directly from
        the api_usage DB. The 'total' key will exactly equal quota_used_today().
        """
        with db_module._connect() as conn:
            rows = conn.execute(
                """SELECT detail, tokens_used FROM api_usage
                   WHERE provider = 'youtube_data_api'
                   AND request_date = date('now')""",
            ).fetchall()
        methods: dict[str, dict] = {
            "search.list": {"calls": 0, "units": 0},
            "videos.list": {"calls": 0, "units": 0},
            "channels.list": {"calls": 0, "units": 0},
            "other": {"calls": 0, "units": 0},
        }
        for detail, units in rows:
            if "search.list" in (detail or ""):
                k = "search.list"
            elif "videos.list" in (detail or ""):
                k = "videos.list"
            elif "channels.list" in (detail or ""):
                k = "channels.list"
            else:
                k = "other"
            methods[k]["calls"] += 1
            methods[k]["units"] += units
        total = sum(m["units"] for m in methods.values())
        return {"methods": methods, "total": total}

    # ── Search ────────────────────────────────────────────────────────────────

    def search_shorts(
        self,
        query: str,
        published_after: str | None = None,
        published_before: str | None = None,
        max_results: int = 50,
        order: str = "viewCount",
    ) -> list[dict]:
        """
        Run a YouTube search for Shorts matching `query`.
        Returns raw items from search.list response.
        Quota cost: 100 units per call.

        Note: YouTube's API has no direct "isShorts" filter.
        We use videoDuration=short (<4min) and filter to <=60s after fetching stats.
        """
        if self._mock:
            logger.info("youtube_search_mock", query=query)
            return list(_MOCK_SEARCH_RESULTS)

        _check_quota(QUOTA_COST["search.list"], self._budget)

        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=self._key)

        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoDuration": "short",
            "maxResults": min(max_results, 50),
            "order": order,
            "relevanceLanguage": "en",
        }
        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before

        response = youtube.search().list(**params).execute()
        _charge_quota(QUOTA_COST["search.list"],
                      f"search.list q={query!r} order={order}")
        items = response.get("items", [])
        logger.info("youtube_search_done", query=query, results=len(items))
        return items

    # ── Video stats ───────────────────────────────────────────────────────────

    def get_videos_stats(self, video_ids: list[str]) -> list[dict]:
        """
        Fetch statistics + contentDetails for up to 50 video IDs per call.
        Quota cost: 1 unit per call (regardless of how many IDs, up to 50).
        Returns list of video items from videos.list response.
        """
        if not video_ids:
            return []

        if self._mock:
            return [
                {"id": vid, **_MOCK_VIDEO_STATS[vid]}
                for vid in video_ids
                if vid in _MOCK_VIDEO_STATS
            ]

        # Batch into groups of 50
        results: list[dict] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            _check_quota(QUOTA_COST["videos.list"], self._budget)
            from googleapiclient.discovery import build
            youtube = build("youtube", "v3", developerKey=self._key)
            response = youtube.videos().list(
                part="statistics,contentDetails",
                id=",".join(batch),
            ).execute()
            _charge_quota(QUOTA_COST["videos.list"],
                          f"videos.list {len(batch)} ids")
            results.extend(response.get("items", []))

        return results

    # ── Channel stats ─────────────────────────────────────────────────────────

    def get_channel(self, channel_id: str) -> dict | None:
        """
        Fetch channel statistics and snippet by channelId.
        Quota cost: 1 unit.
        """
        if self._mock:
            if channel_id in _MOCK_CHANNEL_STATS:
                return {"id": channel_id, **_MOCK_CHANNEL_STATS[channel_id]}
            return None

        _check_quota(QUOTA_COST["channels.list"], self._budget)
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=self._key)
        response = youtube.channels().list(
            part="snippet,statistics",
            id=channel_id,
        ).execute()
        _charge_quota(QUOTA_COST["channels.list"], f"channels.list {channel_id}")
        items = response.get("items", [])
        return items[0] if items else None

    def get_channel_by_handle(self, handle: str) -> dict | None:
        """
        Fetch channel by @handle (e.g. '@Porsevio').
        Quota cost: 1 unit.
        """
        if self._mock:
            # Look up by title in mock data
            for cid, data in _MOCK_CHANNEL_STATS.items():
                if handle.lstrip("@").lower() in data["snippet"]["title"].lower():
                    return {"id": cid, **data}
            return None

        _check_quota(QUOTA_COST["channels.list"], self._budget)
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=self._key)
        clean_handle = handle.lstrip("@")
        response = youtube.channels().list(
            part="snippet,statistics",
            forHandle=clean_handle,
        ).execute()
        _charge_quota(QUOTA_COST["channels.list"], f"channels.list handle={handle}")
        items = response.get("items", [])
        return items[0] if items else None

    def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 50,
        order: str = "viewCount",
    ) -> list[dict]:
        """
        Search for a channel's Shorts using search.list with channelId filter.
        Quota cost: 100 units.
        """
        if self._mock:
            return list(_MOCK_SEARCH_RESULTS)

        _check_quota(QUOTA_COST["search.list"], self._budget)
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=self._key)
        response = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            videoDuration="short",
            maxResults=min(max_results, 50),
            order=order,
        ).execute()
        _charge_quota(QUOTA_COST["search.list"],
                      f"search.list channelId={channel_id}")
        items = response.get("items", [])
        logger.info("youtube_channel_search_done",
                    channel_id=channel_id, results=len(items))
        return items
