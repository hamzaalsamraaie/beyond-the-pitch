"""
YouTube Analytics collector: fetches performance metrics for uploaded videos
and stores them in the analytics table.

Metrics collected per video per run:
  views                 — total view count
  estimatedMinutesWatched
  averageViewPercentage — audience retention %
  subscribersGained

Requires the same OAuth credentials as the uploader.
Run daily via: python scripts/pipeline.py analytics

The feedback loop:
  Metrics are stored in the analytics table, which the idea_ranker and
  metadata_generator can query to learn which topics/hooks perform best.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

import src.core.database as db_module
from src.core.logger import get_logger
from src.youtube.oauth import build_analytics_client, build_youtube_client, credentials_available

logger = get_logger(__name__)


@dataclass
class VideoMetrics:
    youtube_id: str
    views: int
    watch_time_mins: float
    avg_view_pct: float
    subscribers_won: int


# ── Fetchers ──────────────────────────────────────────────────────────────────

def _fetch_video_stats(youtube_id: str) -> VideoMetrics:
    """
    Fetch basic stats via YouTube Data API (no Analytics OAuth needed).
    Returns ViewCount + LikeCount. Full analytics needs Analytics API.
    """
    yt = build_youtube_client()
    response = (
        yt.videos()
        .list(part="statistics", id=youtube_id)
        .execute()
    )
    items = response.get("items", [])
    if not items:
        raise ValueError(f"Video not found or not accessible: {youtube_id}")

    stats = items[0].get("statistics", {})
    views = int(stats.get("viewCount", 0))

    return VideoMetrics(
        youtube_id=youtube_id,
        views=views,
        watch_time_mins=0.0,       # Data API doesn't expose watch time
        avg_view_pct=0.0,          # Requires Analytics API
        subscribers_won=0,
    )


def _fetch_analytics(youtube_id: str, channel_id: str) -> VideoMetrics:
    """
    Fetch full analytics via YouTube Analytics API.
    Requires youtubeAnalytics.readonly scope in the OAuth token.
    """
    analytics = build_analytics_client()
    today = date.today().isoformat()

    response = (
        analytics.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate="2024-01-01",
            endDate=today,
            metrics="views,estimatedMinutesWatched,averageViewPercentage,subscribersGained",
            filters=f"video=={youtube_id}",
            dimensions="video",
        )
        .execute()
    )

    rows = response.get("rows", [])
    if not rows:
        # Video may be too new for analytics to populate
        return VideoMetrics(
            youtube_id=youtube_id,
            views=0,
            watch_time_mins=0.0,
            avg_view_pct=0.0,
            subscribers_won=0,
        )

    row = rows[0]
    return VideoMetrics(
        youtube_id=youtube_id,
        views=int(row[1]),
        watch_time_mins=float(row[2]),
        avg_view_pct=float(row[3]),
        subscribers_won=int(row[4]),
    )


# ── Main collector ────────────────────────────────────────────────────────────

class AnalyticsCollector:
    """
    Collects YouTube Analytics for all uploaded videos and stores them in DB.

    If the full Analytics API fails (no scope or no data), falls back to
    basic Data API stats.
    """

    def __init__(self, channel_id: str = "") -> None:
        self._channel_id = channel_id

    def _get_uploaded_videos(self) -> list[tuple[int, str]]:
        """Return [(db_id, youtube_id)] for all uploaded videos."""
        with db_module._connect() as conn:
            rows = conn.execute(
                "SELECT id, youtube_id FROM videos WHERE youtube_id IS NOT NULL"
            ).fetchall()
        return [(r["id"], r["youtube_id"]) for r in rows]

    def _store_metrics(self, video_db_id: int, m: VideoMetrics) -> None:
        with db_module._connect() as conn:
            conn.execute(
                """INSERT INTO analytics
                   (video_id, views, watch_time_mins, subscribers_won, avg_view_pct)
                   VALUES (?,?,?,?,?)""",
                (video_db_id, m.views, m.watch_time_mins, m.subscribers_won, m.avg_view_pct),
            )

    def collect_all(self) -> list[VideoMetrics]:
        if not credentials_available():
            logger.warning(
                "analytics_credentials_missing",
                blocker=(
                    "BLOCKER: Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env "
                    "to enable analytics collection."
                ),
            )
            return []

        videos = self._get_uploaded_videos()
        if not videos:
            logger.info("analytics_no_uploaded_videos")
            return []

        results: list[VideoMetrics] = []
        for db_id, yt_id in videos:
            try:
                if self._channel_id:
                    metrics = _fetch_analytics(yt_id, self._channel_id)
                else:
                    metrics = _fetch_video_stats(yt_id)
                self._store_metrics(db_id, metrics)
                results.append(metrics)
                logger.info(
                    "analytics_stored",
                    youtube_id=yt_id,
                    views=metrics.views,
                    avg_view_pct=metrics.avg_view_pct,
                )
            except Exception as exc:
                logger.warning("analytics_fetch_failed", youtube_id=yt_id, error=str(exc))

        return results

    def collect_one(self, youtube_id: str) -> VideoMetrics | None:
        if not credentials_available():
            return None
        try:
            metrics = _fetch_video_stats(youtube_id)
            # Find DB id
            with db_module._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM videos WHERE youtube_id=?", (youtube_id,)
                ).fetchone()
            if row:
                self._store_metrics(row["id"], metrics)
            return metrics
        except Exception as exc:
            logger.warning("analytics_single_failed", youtube_id=youtube_id, error=str(exc))
            return None


# ── Performance insights ──────────────────────────────────────────────────────

def get_top_performing_topics(limit: int = 10) -> list[dict]:
    """
    Return the top topics ranked by average view percentage (retention).
    Used by the idea_ranker to weight future topic selection.
    """
    with db_module._connect() as conn:
        rows = conn.execute(
            """
            SELECT v.topic, AVG(a.avg_view_pct) as avg_ret, SUM(a.views) as total_views
            FROM analytics a
            JOIN videos v ON a.video_id = v.id
            WHERE a.avg_view_pct > 0
            GROUP BY v.topic
            ORDER BY avg_ret DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
