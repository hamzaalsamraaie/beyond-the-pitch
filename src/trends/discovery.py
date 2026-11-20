"""
Viral Shorts discovery engine.

Pipeline (in order):
  1a. Run search queries           — with 24h search-result cache
  1b. Run channel-handle searches  — with per-channel video-search cache
  2.  Batch-fetch video stats      — with per-video stats cache (discovered_shorts)
  3.  Channel subscriber lookups   — with per-channel cache (channel_profiles)
  4.  Filter, score, persist, sort

Viral score:
  viral_score = views / max(age_days, 0.5) ^ 0.7

Adjusted viral score (channel-normalised):
  adjusted = viral_score / sqrt(max(channel_subscribers, 100))

Duration note:
  YouTube Shorts can be up to 3 minutes (extended late 2023). Duration ≤ 180s
  is a necessary but NOT sufficient condition for Short classification.
  Duration alone cannot confirm whether YouTube classified the upload as a Short.

Snapshot labelling:
  First discovery = "1st snapshot — lifetime views, growth rate unavailable".
  Subsequent runs (after cache TTL expires) compute views/day since last fetch.
  Single-snapshot records must NOT be described as "growing" or "trending".
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import src.core.database as db_module
from src.core.logger import get_logger
from src.trends.models import DiscoveredShort
from src.trends.youtube_client import YouTubeClient, parse_duration_secs

logger = get_logger(__name__)

SHORTS_MAX_DURATION_SECS = 180   # 3-minute Shorts limit (YouTube, late 2023)


def _utcnow() -> str:
    """Current UTC time in SQLite-compatible format (no microseconds/timezone suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _ensure_schema() -> None:
    with db_module._connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS discovered_shorts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id        TEXT NOT NULL,
                title           TEXT NOT NULL,
                channel_id      TEXT,
                channel_title   TEXT,
                published_at    TEXT,
                view_count      INTEGER DEFAULT 0,
                like_count      INTEGER DEFAULT 0,
                comment_count   INTEGER DEFAULT 0,
                duration_secs   INTEGER DEFAULT 0,
                subscriber_count INTEGER DEFAULT 0,
                viral_score     REAL DEFAULT 0,
                adjusted_viral_score REAL DEFAULT 0,
                age_days        REAL DEFAULT 0,
                search_query    TEXT,
                collected_at    TEXT DEFAULT (datetime('now')),
                raw_json        TEXT,
                snapshot_count  INTEGER DEFAULT 1,
                view_velocity_per_day REAL,
                first_seen_at   TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_discovered_shorts_video_id
                ON discovered_shorts(video_id);

            CREATE TABLE IF NOT EXISTS trend_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id        TEXT NOT NULL,
                title           TEXT,
                channel_title   TEXT,
                view_count      INTEGER,
                like_count      INTEGER,
                comment_count   INTEGER,
                subscriber_count INTEGER,
                snapshot_at     TEXT DEFAULT (datetime('now')),
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS channel_profiles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id      TEXT UNIQUE,
                handle          TEXT,
                title           TEXT,
                subscriber_count INTEGER,
                video_count     INTEGER,
                view_count      INTEGER,
                country         TEXT,
                description_snippet TEXT,
                collected_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_query_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT NOT NULL,
                searched_at TEXT NOT NULL,
                items_json  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sqc_query_time
                ON search_query_cache(query, searched_at);
        """)
        # Migrate older schemas that pre-date snapshot tracking columns
        for ddl in [
            "ALTER TABLE discovered_shorts ADD COLUMN snapshot_count INTEGER DEFAULT 1",
            "ALTER TABLE discovered_shorts ADD COLUMN view_velocity_per_day REAL",
            "ALTER TABLE discovered_shorts ADD COLUMN first_seen_at TEXT",
        ]:
            try:
                conn.execute(ddl)
            except Exception:
                pass


def _age_days(published_at: str) -> float:
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - pub).total_seconds() / 86400, 0.1)
    except Exception:
        return 365.0


def _viral_score(views: int, age_days: float) -> float:
    return views / max(age_days, 0.5) ** 0.7


def _adjusted_viral_score(vs: float, subscribers: int) -> float:
    return vs / math.sqrt(max(subscribers, 100))


# ── Search result cache ───────────────────────────────────────────────────────

def _get_cached_search_items(query: str, ttl_hours: int) -> list[dict] | None:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT items_json FROM search_query_cache
               WHERE query = ?
               AND datetime(searched_at, '+' || ? || ' hours') > datetime('now')
               ORDER BY searched_at DESC LIMIT 1""",
            (query, ttl_hours),
        ).fetchone()
    return json.loads(row[0]) if row else None


def _cache_search_items(query: str, items: list[dict]) -> None:
    with db_module._connect() as conn:
        conn.execute(
            """INSERT INTO search_query_cache (query, searched_at, items_json)
               VALUES (?, datetime('now'), ?)""",
            (query, json.dumps(items)),
        )


# ── Channel stats cache ───────────────────────────────────────────────────────

def _get_cached_channel_subs(channel_id: str, ttl_hours: int) -> int | None:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT subscriber_count FROM channel_profiles
               WHERE channel_id = ?
               AND datetime(collected_at, '+' || ? || ' hours') > datetime('now')
               LIMIT 1""",
            (channel_id, ttl_hours),
        ).fetchone()
    return int(row[0]) if row else None


def _get_cached_channel_by_handle(handle: str, ttl_hours: int) -> dict | None:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT channel_id, title, subscriber_count FROM channel_profiles
               WHERE handle = ?
               AND datetime(collected_at, '+' || ? || ' hours') > datetime('now')
               LIMIT 1""",
            (handle, ttl_hours),
        ).fetchone()
    if row:
        return {
            "id": row[0],
            "snippet": {"title": row[1]},
            "statistics": {"subscriberCount": str(row[2])},
        }
    return None


def _persist_channel_to_cache(channel_id: str, ch_data: dict, handle: str = "") -> None:
    snippet = ch_data.get("snippet", {})
    stats = ch_data.get("statistics", {})
    with db_module._connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO channel_profiles
               (channel_id, handle, title, subscriber_count, video_count,
                view_count, country, description_snippet, collected_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
            (
                channel_id,
                handle,
                snippet.get("title", ""),
                int(stats.get("subscriberCount", 0) or 0),
                int(stats.get("videoCount", 0) or 0),
                int(stats.get("viewCount", 0) or 0),
                snippet.get("country", ""),
                snippet.get("description", "")[:200],
            ),
        )


# ── Video stats cache ─────────────────────────────────────────────────────────

def _get_cached_video_stats(video_id: str, ttl_hours: int) -> dict | None:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT view_count, like_count, comment_count, duration_secs
               FROM discovered_shorts WHERE video_id = ?
               AND datetime(collected_at, '+' || ? || ' hours') > datetime('now')
               LIMIT 1""",
            (video_id, ttl_hours),
        ).fetchone()
    if row:
        view_count, like_count, comment_count, duration_secs = row
        return {
            "id": video_id,
            "statistics": {
                "viewCount": str(view_count),
                "likeCount": str(like_count),
                "commentCount": str(comment_count),
            },
            "contentDetails": {"duration": f"PT{duration_secs}S"},
        }
    return None


# ── Snapshot persistence ──────────────────────────────────────────────────────

def _persist_short(short: DiscoveredShort, query: str, now: str) -> None:
    with db_module._connect() as conn:
        existing = conn.execute(
            """SELECT view_count, collected_at, snapshot_count
               FROM discovered_shorts WHERE video_id = ?""",
            (short.video_id,),
        ).fetchone()

        if existing:
            prev_views, prev_at, prev_count = existing
            try:
                prev_dt = datetime.strptime(prev_at, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
                curr_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
                delta_days = (curr_dt - prev_dt).total_seconds() / 86400
                if delta_days > 0.01:
                    short.view_velocity_per_day = (short.view_count - prev_views) / delta_days
            except Exception:
                pass
            short.snapshot_count = (prev_count or 1) + 1
            short.is_first_snapshot = False
            conn.execute(
                """UPDATE discovered_shorts
                   SET title=?, channel_id=?, channel_title=?, published_at=?,
                       view_count=?, like_count=?, comment_count=?, duration_secs=?,
                       subscriber_count=?, viral_score=?, adjusted_viral_score=?,
                       age_days=?, search_query=?, collected_at=?, raw_json=?,
                       snapshot_count=?, view_velocity_per_day=?
                   WHERE video_id=?""",
                (
                    short.title, short.channel_id, short.channel_title, short.published_at,
                    short.view_count, short.like_count, short.comment_count, short.duration_secs,
                    short.channel_subscriber_count, short.viral_score, short.adjusted_viral_score,
                    short.age_days, query, now,
                    json.dumps({"title": short.title, "url": short.url}),
                    short.snapshot_count, short.view_velocity_per_day,
                    short.video_id,
                ),
            )
        else:
            short.snapshot_count = 1
            short.is_first_snapshot = True
            conn.execute(
                """INSERT INTO discovered_shorts
                   (video_id, title, channel_id, channel_title, published_at,
                    view_count, like_count, comment_count, duration_secs,
                    subscriber_count, viral_score, adjusted_viral_score, age_days,
                    search_query, collected_at, raw_json, snapshot_count, first_seen_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    short.video_id, short.title, short.channel_id, short.channel_title,
                    short.published_at, short.view_count, short.like_count,
                    short.comment_count, short.duration_secs, short.channel_subscriber_count,
                    short.viral_score, short.adjusted_viral_score, short.age_days,
                    query, now, json.dumps({"title": short.title, "url": short.url}),
                    1, now,
                ),
            )

        conn.execute(
            """INSERT INTO trend_snapshots
               (video_id, title, channel_title, view_count, like_count,
                comment_count, subscriber_count, snapshot_at, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                short.video_id, short.title, short.channel_title,
                short.view_count, short.like_count, short.comment_count,
                short.channel_subscriber_count, now,
                f"snapshot #{short.snapshot_count}",
            ),
        )
    short.collected_at = now


def discover_shorts(
    client: YouTubeClient,
    queries: list[str] | None = None,
    max_per_query: int = 50,
    min_views: int = 100_000,
    channel_handles: list[str] | None = None,
    cache_ttl_hours: int = 24,
) -> list[DiscoveredShort]:
    """
    Run the full discovery pipeline. Returns DiscoveredShort sorted by
    adjusted_viral_score descending.

    All caches (search, video stats, channel stats) share the same TTL.
    A re-run within cache_ttl_hours costs 0 quota units.

    Snapshot labelling:
      First run: 'lifetime views — 1st snapshot, growth rate unavailable'.
      Subsequent runs after TTL expire: view velocity computed since last fetch.
    """
    db_module.init_db()
    _ensure_schema()
    now = _utcnow()

    if queries is None:
        queries = _default_queries()

    # ── Step 1a: Search queries (with cache) ──────────────────────────────────
    all_search_items: dict[str, tuple[dict, str]] = {}

    for query in queries:
        cached = _get_cached_search_items(query, cache_ttl_hours)
        if cached is not None:
            logger.info("discovery_search_cache_hit", query=query, count=len(cached))
            items = cached
        else:
            items = client.search_shorts(query=query, max_results=max_per_query)
            if items:
                _cache_search_items(query, items)
        for item in items:
            vid_id = item.get("id", {}).get("videoId", "")
            if vid_id and vid_id not in all_search_items:
                all_search_items[vid_id] = (item, query)

    # ── Step 1b: Channel-handle searches (with cache) ─────────────────────────
    if channel_handles:
        for handle in channel_handles:
            ch = _get_cached_channel_by_handle(handle, cache_ttl_hours)
            if ch:
                logger.info("channel_handle_cache_hit", handle=handle)
            else:
                ch = client.get_channel_by_handle(handle)
                if ch:
                    _persist_channel_to_cache(ch.get("id", ""), ch, handle)

            if not ch:
                continue

            channel_id = ch.get("id", "")
            logger.info("channel_profiled", handle=handle,
                        title=ch.get("snippet", {}).get("title", ""),
                        channel_id=channel_id)

            channel_query_key = f"channelId:{channel_id}"
            cached_ch_items = _get_cached_search_items(channel_query_key, cache_ttl_hours)
            if cached_ch_items is not None:
                logger.info("channel_video_cache_hit", handle=handle,
                            count=len(cached_ch_items))
                ch_items = cached_ch_items
            else:
                ch_items = client.get_channel_videos(
                    channel_id=channel_id,
                    max_results=max_per_query,
                )
                if ch_items:
                    _cache_search_items(channel_query_key, ch_items)

            for item in ch_items:
                vid_id = item.get("id", {}).get("videoId", "")
                if vid_id and vid_id not in all_search_items:
                    all_search_items[vid_id] = (item, f"channel:{handle}")

    logger.info("discovery_search_done", unique_videos=len(all_search_items))
    if not all_search_items:
        return []

    # ── Step 2: Video stats (with per-video cache) ────────────────────────────
    stats_items: list[dict] = []
    ids_to_fetch: list[str] = []

    for vid_id in all_search_items:
        cached_stats = _get_cached_video_stats(vid_id, cache_ttl_hours)
        if cached_stats is not None:
            stats_items.append(cached_stats)
        else:
            ids_to_fetch.append(vid_id)

    if ids_to_fetch:
        logger.info("video_stats_fetch", count=len(ids_to_fetch))
        stats_items.extend(client.get_videos_stats(ids_to_fetch))
    else:
        logger.info("video_stats_all_cached", count=len(stats_items))

    stats_by_id: dict[str, dict] = {item["id"]: item for item in stats_items}

    # ── Step 3: Channel subscriber lookups (with cache) ───────────────────────
    channel_ids: set[str] = set()
    for item, _ in all_search_items.values():
        cid = item.get("snippet", {}).get("channelId", "")
        if cid:
            channel_ids.add(cid)

    channel_subs: dict[str, int] = {}
    for cid in channel_ids:
        cached_subs = _get_cached_channel_subs(cid, cache_ttl_hours)
        if cached_subs is not None:
            channel_subs[cid] = cached_subs
        else:
            ch = client.get_channel(cid)
            if ch:
                subs_str = ch.get("statistics", {}).get("subscriberCount", "0")
                subs = int(subs_str) if subs_str else 0
                channel_subs[cid] = subs
                _persist_channel_to_cache(cid, ch)

    # ── Step 4: Build, filter, score, persist ─────────────────────────────────
    shorts: list[DiscoveredShort] = []

    for vid_id, (search_item, query) in all_search_items.items():
        snippet = search_item.get("snippet", {})
        stat_item = stats_by_id.get(vid_id, {})
        stats = stat_item.get("statistics", {})
        content = stat_item.get("contentDetails", {})

        duration_iso = content.get("duration", "PT0S")
        duration_secs = parse_duration_secs(duration_iso)

        is_compatible = duration_secs <= SHORTS_MAX_DURATION_SECS
        if not is_compatible:
            continue

        view_count = int(stats.get("viewCount", 0))
        if view_count < min_views:
            continue

        published_at = snippet.get("publishedAt", "")
        age = _age_days(published_at)
        channel_id = snippet.get("channelId", "")
        subs = channel_subs.get(channel_id, 0)

        vs = _viral_score(view_count, age)
        avs = _adjusted_viral_score(vs, subs)

        short = DiscoveredShort(
            video_id=vid_id,
            title=snippet.get("title", ""),
            channel_id=channel_id,
            channel_title=snippet.get("channelTitle", ""),
            published_at=published_at,
            view_count=view_count,
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
            duration_iso=duration_iso,
            duration_secs=duration_secs,
            is_duration_compatible_short=is_compatible,
            channel_subscriber_count=subs,
            viral_score=vs,
            adjusted_viral_score=avs,
            age_days=age,
        )
        _persist_short(short, query, now)
        shorts.append(short)

    shorts.sort(key=lambda s: s.adjusted_viral_score, reverse=True)
    logger.info("discovery_complete",
                total_shorts=len(shorts),
                top_views=shorts[0].view_count if shorts else 0)
    return shorts


def _default_queries() -> list[str]:
    return [
        "#Shorts football",
        "#Shorts soccer goal",
        "#Shorts footballer story",
        "football motivation shorts",
    ]
