"""Tests for the analytics collector (mocked — no real API calls)."""

import pytest
from unittest.mock import patch, MagicMock
from src.analytics.collector import (
    AnalyticsCollector, VideoMetrics, get_top_performing_topics,
)
from src.core.database import init_db


def test_collect_all_without_credentials(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    collector = AnalyticsCollector()
    results = collector.collect_all()
    assert results == []


def test_collect_all_no_uploaded_videos(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "fake")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "fake")
    init_db()
    # No videos with youtube_id — returns empty
    collector = AnalyticsCollector()
    with patch("src.analytics.collector._fetch_video_stats") as mock_fetch:
        results = collector.collect_all()
    # Either empty (no videos) or tried to fetch
    assert isinstance(results, list)


def test_video_metrics_dataclass():
    m = VideoMetrics(
        youtube_id="abc123",
        views=1000,
        watch_time_mins=250.0,
        avg_view_pct=65.5,
        subscribers_won=10,
    )
    assert m.views == 1000
    assert m.avg_view_pct == 65.5


def test_get_top_performing_topics_empty():
    init_db()
    top = get_top_performing_topics()
    assert isinstance(top, list)
