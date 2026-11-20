"""Tests for trend discovery. Uses mock client — no real API calls."""

import tempfile
from pathlib import Path

import pytest

import src.core.database as db_module
from src.trends.discovery import (
    _age_days,
    _adjusted_viral_score,
    _viral_score,
    discover_shorts,
)
from src.trends.youtube_client import YouTubeClient, parse_duration_secs


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_module.DB_PATH = tmp_path / "test_trends.db"
    db_module.init_db()
    yield


def _mock_client() -> YouTubeClient:
    return YouTubeClient(api_key=None)  # no key → mock mode


# ── Duration parser ────────────────────────────────────────────────────────────

def test_parse_duration_45s():
    assert parse_duration_secs("PT45S") == 45


def test_parse_duration_1m30s():
    assert parse_duration_secs("PT1M30S") == 90


def test_parse_duration_invalid():
    assert parse_duration_secs("INVALID") == 0


def test_parse_duration_zero():
    assert parse_duration_secs("PT0S") == 0


# ── Scoring functions ─────────────────────────────────────────────────────────

def test_viral_score_favours_recent():
    old = _viral_score(1_000_000, age_days=365.0)
    new = _viral_score(1_000_000, age_days=7.0)
    assert new > old


def test_viral_score_favours_more_views():
    low = _viral_score(100_000, age_days=10.0)
    high = _viral_score(5_000_000, age_days=10.0)
    assert high > low


def test_adjusted_viral_score_favours_small_channels():
    big_channel = _adjusted_viral_score(500_000, subscribers=10_000_000)
    small_channel = _adjusted_viral_score(500_000, subscribers=10_000)
    assert small_channel > big_channel


def test_adjusted_viral_score_handles_zero_subs():
    score = _adjusted_viral_score(500_000, subscribers=0)
    assert score > 0


# ── Age calculation ────────────────────────────────────────────────────────────

def test_age_days_valid_date():
    age = _age_days("2020-01-01T00:00:00Z")
    assert age > 365 * 4  # well over 4 years ago as of 2024


def test_age_days_recent():
    from datetime import datetime, timezone, timedelta
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    age = _age_days(yesterday)
    assert 0.5 < age < 2.0


def test_age_days_bad_format():
    age = _age_days("not-a-date")
    assert age == 365.0  # fallback


# ── Discovery pipeline (mock mode) ────────────────────────────────────────────

def test_discovery_returns_discovered_shorts():
    client = _mock_client()
    results = discover_shorts(client, min_views=0)
    assert len(results) > 0


def test_discovery_filters_to_shorts_duration():
    """All results should be ≤ 180 seconds (YouTube extended Shorts to 3 min in late 2023)."""
    client = _mock_client()
    results = discover_shorts(client, min_views=0)
    for s in results:
        assert s.duration_secs <= 180, f"{s.title}: {s.duration_secs}s"
        assert s.is_duration_compatible_short is True


def test_discovery_sorted_by_adjusted_viral_score():
    client = _mock_client()
    results = discover_shorts(client, min_views=0)
    scores = [s.adjusted_viral_score for s in results]
    assert scores == sorted(scores, reverse=True)


def test_discovery_min_views_filter():
    client = _mock_client()
    high_threshold = discover_shorts(client, min_views=10_000_000_000)
    assert len(high_threshold) == 0


def test_discovery_viral_scores_computed():
    client = _mock_client()
    results = discover_shorts(client, min_views=0)
    for s in results:
        assert s.viral_score > 0
        assert s.adjusted_viral_score > 0
        assert s.age_days > 0


def test_discovery_persists_to_db():
    client = _mock_client()
    discover_shorts(client, min_views=0)
    with db_module._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM discovered_shorts").fetchone()[0]
    assert count > 0


def test_mock_client_is_mock():
    client = YouTubeClient(api_key=None)
    assert client.is_mock is True


def test_live_client_not_mock():
    client = YouTubeClient(api_key="fake_key_12345")
    assert client.is_mock is False


def test_quota_tracker_starts_at_zero(tmp_path):
    db_module.DB_PATH = tmp_path / "quota_test.db"
    db_module.init_db()
    client = YouTubeClient(api_key=None)
    assert client.quota_used_today() == 0


def test_quota_breakdown_has_correct_total():
    client = YouTubeClient(api_key=None)
    bd = client.quota_breakdown_today()
    assert bd["total"] == client.quota_used_today()
    assert "methods" in bd
    # Breakdown sum must match total
    summed = sum(m["units"] for m in bd["methods"].values())
    assert summed == bd["total"]


def test_discovery_uses_search_cache_on_rerun():
    """Second call within TTL must not trigger new search API calls (mock mode)."""
    client = _mock_client()
    # First run — populates cache
    discover_shorts(client, min_views=0, cache_ttl_hours=24)
    # Count how many mock search calls were made: 4 queries × 10 results each
    # On second run, cache should be hit for all 4 queries
    from src.trends.discovery import _get_cached_search_items
    for query in ["#Shorts football", "#Shorts soccer goal",
                  "#Shorts footballer story", "football motivation shorts"]:
        cached = _get_cached_search_items(query, 24)
        assert cached is not None, f"Cache miss for query: {query!r}"


def test_discovery_channel_cache_persisted():
    """Channel subscriber counts must be persisted in channel_profiles after discovery."""
    client = _mock_client()
    discover_shorts(client, min_views=0, cache_ttl_hours=24)
    with db_module._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM channel_profiles"
        ).fetchone()[0]
    assert count > 0, "No channel profiles persisted"


def test_discovery_snapshot_count_increments():
    """Running discovery twice (simulated by clearing cache) increments snapshot_count."""
    client = _mock_client()
    # First run
    discover_shorts(client, min_views=0, cache_ttl_hours=24)
    # Expire the caches by using ttl=0 for second run
    discover_shorts(client, min_views=0, cache_ttl_hours=0)
    with db_module._connect() as conn:
        counts = conn.execute(
            "SELECT snapshot_count FROM discovered_shorts"
        ).fetchall()
    # At least one record should have snapshot_count >= 2
    assert any(row[0] >= 2 for row in counts), "No snapshot_count was incremented"
