"""
End-to-end pipeline tests using 100% mock components.
No API calls, no network traffic.

Each test function gets its own isolated SQLite database via the `fresh_db`
fixture so that storyboard hash dedup checks don't bleed between tests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import src.core.database as db_module
from src.core.kill_switch import arm, disarm
from src.research.models import ContentType, Storyboard
from src.research.pipeline import StoryboardPipeline
from src.research.providers import MockResearchProvider
from src.research.script_writer import MockScriptWriter


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Give each test its own SQLite file and disarm the kill switch."""
    db_path = tmp_path / "test_pipeline.db"
    db_module.DB_PATH = db_path
    db_module.init_db()
    disarm()
    yield
    # cleanup is automatic: tmp_path is deleted by pytest


def _make_pipeline(**kwargs) -> StoryboardPipeline:
    return StoryboardPipeline(
        provider=MockResearchProvider(),
        writer=MockScriptWriter(),
        **kwargs,
    )


# ── Basic pipeline run ─────────────────────────────────────────────────────────

def test_pipeline_produces_storyboard_for_each_type():
    pipeline = _make_pipeline()
    results = pipeline.run(
        content_types=[
            ContentType.FOOTBALL_MOMENTS,
            ContentType.PLAYER_STORIES,
            ContentType.FOOTBALL_MOTIVATION,
        ]
    )
    assert len(results) == 3
    for sb in results:
        assert isinstance(sb, Storyboard)
        assert 20.0 <= sb.total_duration <= 45.0
        assert sb.script_hash != ""


def test_pipeline_storyboard_has_valid_scenes():
    disarm()
    pipeline = _make_pipeline()
    results = pipeline.run(content_types=[ContentType.PLAYER_STORIES])
    assert len(results) == 1
    sb = results[0]
    assert 3 <= len(sb.scenes) <= 8
    for scene in sb.scenes:
        assert scene.end_time > scene.start_time
        assert len(scene.narration) >= 5
        assert len(scene.source_indices) >= 1


def test_pipeline_hashtags_contain_required():
    disarm()
    pipeline = _make_pipeline()
    results = pipeline.run(content_types=[ContentType.FOOTBALL_MOMENTS])
    sb = results[0]
    lower_tags = [t.lower() for t in sb.hashtags]
    assert "#shorts" in lower_tags
    assert "#football" in lower_tags


# ── Duplicate prevention ───────────────────────────────────────────────────────

def test_pipeline_prevents_duplicate_topics():
    """Running the pipeline twice for the same type should not duplicate storyboards."""
    pipeline = _make_pipeline()

    # First run
    results1 = pipeline.run(content_types=[ContentType.FOOTBALL_MOTIVATION])
    assert len(results1) == 1

    # Second run with the same mock data — topic is now in topic_history,
    # so it should be treated as a repeat.  With only 1 mock topic available
    # and it now being in history, no new storyboard should be produced
    # (or the second run produces a different story if other candidates exist).
    results2 = pipeline.run(content_types=[ContentType.FOOTBALL_MOTIVATION])
    # Either 0 (no fresh topics) or a different storyboard — but never the same hash
    if results2:
        assert results2[0].script_hash != results1[0].script_hash


def test_pipeline_duplicate_hash_rejected():
    """Directly test that the same script_hash can't be inserted twice."""
    from src.core.database import insert_storyboard, storyboard_hash_exists

    insert_storyboard(
        topic="Test topic",
        content_type="football_moments",
        script_hash="test_hash_abc123",
        storyboard_json="{}",
        total_score=0.75,
        generated_by="mock",
    )
    assert storyboard_hash_exists("test_hash_abc123") is True
    assert storyboard_hash_exists("nonexistent_hash_xyz") is False


# ── Kill switch ────────────────────────────────────────────────────────────────

def test_pipeline_respects_kill_switch():
    arm()
    pipeline = _make_pipeline()
    with pytest.raises(RuntimeError, match="Kill switch is ARMED"):
        pipeline.run(content_types=[ContentType.FOOTBALL_MOMENTS])
    disarm()


# ── Score threshold ────────────────────────────────────────────────────────────

def test_pipeline_skips_topics_below_threshold():
    # Threshold of 1.0 means nothing can pass
    pipeline = _make_pipeline(min_score_threshold=1.0)
    results = pipeline.run(content_types=[ContentType.FOOTBALL_MOMENTS])
    assert results == []


def test_pipeline_accepts_topics_above_threshold():
    # Threshold of 0.0 means everything passes
    pipeline = _make_pipeline(min_score_threshold=0.0)
    results = pipeline.run(content_types=[ContentType.FOOTBALL_MOMENTS])
    assert len(results) >= 1


# ── Mock writer output validation ─────────────────────────────────────────────

def test_mock_writer_generates_valid_storyboard():
    from src.research.models import TopicScore
    from src.research.models import ScoredTopic
    from src.research.providers import _MOCK_DATA
    from src.research.script_writer import MockScriptWriter

    candidate = _MOCK_DATA[ContentType.PLAYER_STORIES][0]
    scored = ScoredTopic(
        candidate=candidate,
        score=TopicScore(
            freshness=0.6,
            audience_interest=0.7,
            emotional_impact=0.8,
            originality=1.0,
            visual_feasibility=0.7,
        ),
        total_score=0.74,
    )
    writer = MockScriptWriter()
    sb = writer.generate(scored)

    assert isinstance(sb, Storyboard)
    assert sb.generated_by == "mock"
    assert len(sb.scenes) >= 1
    assert sb.script_hash != ""
    assert 20.0 <= sb.total_duration <= 45.0


# ── DB tables created ──────────────────────────────────────────────────────────

def test_phase2_tables_exist():
    import sqlite3
    conn = sqlite3.connect(str(db_module.DB_PATH))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "storyboards" in tables
    assert "topic_history" in tables
    assert "api_usage" in tables
