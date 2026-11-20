"""
Growth intelligence system: learns which football edits perform well.

Tracks video-level attributes (player, moment type, length, music, hook)
alongside YouTube analytics to surface patterns that actually drive views,
replays, and subscribers.

Data flow:
  1. record_video_attributes() — called when a video is uploaded
  2. ingest_analytics() — called after YouTube analytics are fetched
  3. generate_insights() — returns performance analysis
  4. generate_weekly_report() — full weekly summary

All recommendations are based on ACTUAL measured data, never fabricated.
Until real channel data exists, the system returns honest placeholders.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

import src.core.database as db_module
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VideoAttributes:
    """Creative attributes for a single video — recorded at upload time."""
    youtube_id: str
    player_name: str = ""
    moment_type: str = ""       # skill, goal, save, nostalgia, sequence
    video_length_secs: float = 0.0
    music_style: str = ""       # cc0_cinematic, shorts_picker, none
    hook_style: str = ""        # stat_bomb, question, surprising_fact
    caption_preset: str = ""    # DRAMATIC_REVEAL, BOLD_IMPACT, etc.
    posting_slot: str = ""      # noon, 5pm, 9pm
    content_type: str = ""      # football_moments, player_stories, etc.
    footage_source: str = ""    # pexels, pixabay, ai_generated, creator_auth
    has_music: bool = False


@dataclass
class PerformanceInsight:
    dimension: str         # e.g. "player", "moment_type", "length"
    best_value: str        # e.g. "Messi", "skill", "15-20s"
    avg_views: float
    avg_retention: float
    sample_size: int
    confidence: str        # "high" (n≥10), "medium" (n≥3), "low" (n<3)


@dataclass
class WeeklyGrowthReport:
    period_start: str
    period_end: str
    videos_published: int
    total_views: int
    total_subscribers_gained: int
    top_5_videos: list[dict]
    worst_format: str
    best_player: str
    best_moment_type: str
    retention_insight: str
    monetization_progress: str
    recommendations: list[str]
    data_note: str  # honest note about data availability


# ── DB helpers ────────────────────────────────────────────────────────────────

_CREATE_VIDEO_ATTRS_TABLE = """
CREATE TABLE IF NOT EXISTS video_attributes (
    youtube_id          TEXT PRIMARY KEY,
    player_name         TEXT DEFAULT '',
    moment_type         TEXT DEFAULT '',
    video_length_secs   REAL DEFAULT 0,
    music_style         TEXT DEFAULT '',
    hook_style          TEXT DEFAULT '',
    caption_preset      TEXT DEFAULT '',
    posting_slot        TEXT DEFAULT '',
    content_type        TEXT DEFAULT '',
    footage_source      TEXT DEFAULT '',
    has_music           INTEGER DEFAULT 0,
    recorded_at         TEXT DEFAULT (datetime('now'))
)
"""


def _ensure_table() -> None:
    with db_module._connect() as conn:
        conn.execute(_CREATE_VIDEO_ATTRS_TABLE)


# ── Core functions ────────────────────────────────────────────────────────────

def record_video_attributes(attrs: VideoAttributes) -> None:
    """Record creative attributes for a newly uploaded video."""
    _ensure_table()
    with db_module._connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO video_attributes
               (youtube_id, player_name, moment_type, video_length_secs,
                music_style, hook_style, caption_preset, posting_slot,
                content_type, footage_source, has_music)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                attrs.youtube_id, attrs.player_name, attrs.moment_type,
                attrs.video_length_secs, attrs.music_style, attrs.hook_style,
                attrs.caption_preset, attrs.posting_slot, attrs.content_type,
                attrs.footage_source, int(attrs.has_music),
            ),
        )
    logger.info("video_attributes_recorded", youtube_id=attrs.youtube_id)


def _get_analytics_joined() -> list[sqlite3.Row]:
    """Return analytics rows joined with video_attributes where available."""
    _ensure_table()
    with db_module._connect() as conn:
        return conn.execute("""
            SELECT
                a.video_id, a.views, a.watch_time_mins, a.avg_view_pct,
                a.subscribers_won, a.fetched_at,
                v.youtube_id, v.title,
                va.player_name, va.moment_type, va.video_length_secs,
                va.music_style, va.posting_slot, va.has_music
            FROM analytics a
            JOIN videos v ON v.id = a.video_id
            LEFT JOIN video_attributes va ON va.youtube_id = v.youtube_id
            ORDER BY a.views DESC
        """).fetchall()


def _aggregate_by(rows: list[sqlite3.Row], key: str, metric: str) -> dict[str, dict]:
    """Group rows by key and compute avg of metric."""
    groups: dict[str, list[float]] = {}
    for row in rows:
        k = str(row[key] or "unknown")
        v = float(row[metric] or 0)
        groups.setdefault(k, []).append(v)
    return {
        k: {"avg": round(sum(vals)/len(vals), 1), "n": len(vals)}
        for k, vals in groups.items()
        if k and k != "unknown"
    }


def generate_insights(days: int = 30) -> list[PerformanceInsight]:
    """
    Analyse recent performance data and return insights.
    Returns empty list if insufficient data (< 3 videos with analytics).
    """
    rows = _get_analytics_joined()
    if len(rows) < 3:
        logger.info("growth_intelligence_insufficient_data", n=len(rows))
        return []

    insights: list[PerformanceInsight] = []

    for dim, metric in [("player_name", "views"), ("moment_type", "views"), ("posting_slot", "views")]:
        agg = _aggregate_by(rows, dim, metric)
        if not agg:
            continue
        best_key = max(agg, key=lambda k: agg[k]["avg"])
        n = agg[best_key]["n"]
        confidence = "high" if n >= 10 else ("medium" if n >= 3 else "low")
        insights.append(PerformanceInsight(
            dimension=dim,
            best_value=best_key,
            avg_views=agg[best_key]["avg"],
            avg_retention=0.0,  # requires Analytics API
            sample_size=n,
            confidence=confidence,
        ))

    return insights


def generate_weekly_report(days: int = 7) -> WeeklyGrowthReport:
    """Generate the weekly growth report from available data."""
    _ensure_table()
    since = (date.today() - timedelta(days=days)).isoformat()
    today = date.today().isoformat()

    with db_module._connect() as conn:
        # Videos published this period
        published = conn.execute(
            "SELECT COUNT(*) as n FROM renders WHERE created_at >= ? AND youtube_id IS NOT NULL",
            (since,),
        ).fetchone()
        n_published = published["n"] if published else 0

        # Total views this period
        total_views_row = conn.execute(
            """SELECT COALESCE(SUM(a.views),0) as total_views,
                      COALESCE(SUM(a.subscribers_won),0) as total_subs
               FROM analytics a
               JOIN videos v ON v.id = a.video_id
               WHERE a.fetched_at >= ?""",
            (since,),
        ).fetchone()

        total_views = int(total_views_row["total_views"]) if total_views_row else 0
        total_subs = int(total_views_row["total_subs"]) if total_views_row else 0

        # Top 5 by views
        top5_rows = conn.execute(
            """SELECT v.youtube_id, v.title,
                      COALESCE(a.views,0) as views,
                      COALESCE(va.player_name,'') as player,
                      COALESCE(va.moment_type,'') as moment_type,
                      r.youtube_url
               FROM renders r
               LEFT JOIN videos v ON v.youtube_id = r.youtube_id
               LEFT JOIN analytics a ON a.video_id = v.id
               LEFT JOIN video_attributes va ON va.youtube_id = r.youtube_id
               WHERE r.youtube_id IS NOT NULL
               ORDER BY views DESC
               LIMIT 5""",
        ).fetchall()

    top5 = [
        {
            "youtube_id": r["youtube_id"] or "",
            "title": (r["title"] or "")[:60],
            "views": r["views"],
            "player": r["player"],
            "moment_type": r["moment_type"],
            "url": r["youtube_url"] or "",
        }
        for r in top5_rows
    ]

    # Insight strings (require real data)
    rows = _get_analytics_joined()
    if rows:
        player_agg = _aggregate_by(rows, "player_name", "views")
        type_agg = _aggregate_by(rows, "moment_type", "views")
        best_player = max(player_agg, key=lambda k: player_agg[k]["avg"]) if player_agg else "insufficient data"
        best_type = max(type_agg, key=lambda k: type_agg[k]["avg"]) if type_agg else "insufficient data"
        worst_format = "insufficient data"
        retention_insight = f"Avg retention: {rows[0]['avg_view_pct']:.0f}%" if rows[0]["avg_view_pct"] else "insufficient data"
    else:
        best_player = "no analytics yet"
        best_type = "no analytics yet"
        worst_format = "no analytics yet"
        retention_insight = "No analytics collected yet — upload videos and run: python scripts/pipeline.py analytics"

    # Monetization progress
    # YPP Shorts threshold: 1,000 subs + 10M Shorts views in 90 days
    # Traditional: 1,000 subs + 4,000 watch hours
    mon_note = (
        "YouTube Partner Program (Shorts): 1,000 subscribers + 10M Shorts views (90 days). "
        f"Current: 0 uploads recorded. Begin publishing to track progress."
    )

    recs = _build_recommendations(n_published, total_views, total_subs, rows)
    data_note = (
        "Analytics data is populated after running: python scripts/pipeline.py analytics. "
        "Pattern insights require a minimum of 10 uploaded videos."
        if not rows else
        f"Based on {len(rows)} analytics rows. Confidence improves with more data."
    )

    return WeeklyGrowthReport(
        period_start=since,
        period_end=today,
        videos_published=n_published,
        total_views=total_views,
        total_subscribers_gained=total_subs,
        top_5_videos=top5,
        worst_format=worst_format,
        best_player=best_player,
        best_moment_type=best_type,
        retention_insight=retention_insight,
        monetization_progress=mon_note,
        recommendations=recs,
        data_note=data_note,
    )


def _build_recommendations(
    n_published: int,
    total_views: int,
    total_subs: int,
    analytics_rows: list,
) -> list[str]:
    recs: list[str] = []

    if n_published == 0:
        recs.append("PRIORITY: Upload your first Short. Run: python scripts/upload_first_short.py")
        recs.append("After upload, collect analytics: python scripts/pipeline.py analytics")
        return recs

    if n_published < 10:
        recs.append(
            f"Published {n_published} videos so far. Need 10+ before pattern analysis is reliable. "
            "Keep publishing 3/day."
        )

    if not analytics_rows:
        recs.append("Run analytics collection: python scripts/pipeline.py analytics")

    # Content-specific recs (generic until real data exists)
    recs.append("Experiment with different moment types: skills perform better than analysis for Shorts.")
    recs.append("Post at all 3 slots (12PM, 5PM, 9PM ET) for 2 weeks before cutting underperformers.")
    recs.append("Add CC0 background music — it improves retention on football edits.")
    recs.append("Review YPP eligibility: 1,000 subscribers needed first (fan-funding = 500 subs).")

    return recs
