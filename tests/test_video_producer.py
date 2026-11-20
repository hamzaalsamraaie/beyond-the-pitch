"""
End-to-end producer tests. All use MockTTSProvider.
Each test gets an isolated DB and temp output directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import src.core.database as db_module
from src.core.kill_switch import arm, disarm
from src.research.models import ContentType, Storyboard
from src.video.assets import AssetManifest
from src.video.producer import ProductionResult, VideoProducer
from src.video.tts import MockTTSProvider
from tests.test_research_models import _item, _scene, _storyboard


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_module.DB_PATH = tmp_path / "test_producer.db"
    db_module.init_db()
    disarm()
    yield


def _make_producer(tmp_path, **kwargs) -> tuple[VideoProducer, Path]:
    manifest = AssetManifest(manifest_path=tmp_path / "manifest.json")
    producer = VideoProducer(
        tts_provider=MockTTSProvider(),
        manifest=manifest,
        bypass_review=True,  # always bypass for tests
        **kwargs,
    )
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return producer, out_dir


def _make_storyboard() -> Storyboard:
    sb = _storyboard(total_duration=30.0)
    return Storyboard.model_validate(
        {**sb.model_dump(), "script_hash": sb.compute_hash()}
    )


# ── Core produce ───────────────────────────────────────────────────────────────

def test_producer_creates_valid_mp4(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"
    result = producer.produce(sb, output_path=out)

    assert result.success, f"Production failed: {result.failure_reason}\n{result.qc and result.qc.report()}"
    assert out.exists()
    assert out.stat().st_size > 0


def test_producer_qc_passes(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"
    result = producer.produce(sb, output_path=out)

    assert result.qc is not None
    assert result.qc.passed, result.qc.report()
    assert result.qc.measured_width == 1080
    assert result.qc.measured_height == 1920


def test_producer_records_in_db(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"
    result = producer.produce(sb, output_path=out)

    assert result.render_id is not None
    assert isinstance(result.render_id, int)

    import sqlite3
    conn = sqlite3.connect(str(db_module.DB_PATH))
    row = conn.execute(
        "SELECT * FROM renders WHERE id = ?", (result.render_id,)
    ).fetchone()
    conn.close()
    assert row is not None


# ── Kill switch ────────────────────────────────────────────────────────────────

def test_producer_respects_kill_switch(tmp_path):
    arm()
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    result = producer.produce(sb, output_path=out_dir / "test.mp4")
    assert not result.success
    assert "ARMED" in result.failure_reason
    disarm()


# ── Duplicate render prevention ───────────────────────────────────────────────

def test_producer_prevents_duplicate_render(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"

    result1 = producer.produce(sb, output_path=out)
    assert result1.success

    # Second attempt with the same storyboard should be rejected
    out2 = out_dir / "test2.mp4"
    result2 = producer.produce(sb, output_path=out2)
    assert not result2.success
    assert "Duplicate" in result2.failure_reason or "duplicate" in result2.failure_reason.lower()


# ── Review gate ────────────────────────────────────────────────────────────────

def test_producer_review_gate_blocks_unapproved(tmp_path):
    """When bypass_review=False and storyboard is not in DB, production is blocked."""
    # Insert storyboard with pending_review status
    sb = _make_storyboard()
    db_module.insert_storyboard(
        topic=sb.title,
        content_type=sb.content_type.value,
        script_hash=sb.script_hash,
        storyboard_json=sb.to_json(),
        total_score=0.75,
        generated_by="mock",
    )

    manifest = AssetManifest(manifest_path=tmp_path / "manifest.json")
    producer = VideoProducer(
        tts_provider=MockTTSProvider(),
        manifest=manifest,
        bypass_review=False,  # enforce review
    )
    result = producer.produce(sb, output_path=tmp_path / "test.mp4")
    assert not result.success
    assert "approved" in result.failure_reason.lower() or "pending" in result.failure_reason.lower()


def test_producer_review_gate_passes_after_approval(tmp_path):
    """After approval, production should succeed."""
    sb = _make_storyboard()
    db_module.insert_storyboard(
        topic=sb.title,
        content_type=sb.content_type.value,
        script_hash=sb.script_hash,
        storyboard_json=sb.to_json(),
        total_score=0.75,
        generated_by="mock",
    )
    db_module.approve_storyboard(sb.script_hash)

    manifest = AssetManifest(manifest_path=tmp_path / "manifest.json")
    producer = VideoProducer(
        tts_provider=MockTTSProvider(),
        manifest=manifest,
        bypass_review=False,
    )
    result = producer.produce(sb, output_path=tmp_path / "approved.mp4")
    assert result.success, f"Expected success after approval: {result.failure_reason}"


# ── Video properties ──────────────────────────────────────────────────────────

def test_produced_video_correct_dimensions(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"
    result = producer.produce(sb, output_path=out)
    assert result.success
    assert result.qc.measured_width == 1080
    assert result.qc.measured_height == 1920


def test_produced_video_correct_duration(tmp_path):
    producer, out_dir = _make_producer(tmp_path)
    sb = _make_storyboard()
    out = out_dir / "test.mp4"
    result = producer.produce(sb, output_path=out)
    assert result.success
    # Duration should be within 2 seconds of storyboard total
    assert abs(result.qc.measured_duration_secs - sb.total_duration) <= 2.0
