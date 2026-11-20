"""Tests for the YouTube uploader (mocked — no real API calls)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.youtube.uploader import (
    VideoMetadata,
    _is_duplicate_local_path,
    _is_duplicate_file_hash,
    video_file_hash,
)
from src.youtube.oauth import credentials_available
from src.core.database import init_db


def test_credentials_available_false_without_env(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    assert credentials_available() is False


def test_credentials_available_true_with_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "fake_id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "fake_secret")
    assert credentials_available() is True


def test_uploader_raises_without_credentials(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    from src.youtube.uploader import YouTubeUploader
    with pytest.raises(EnvironmentError, match="YOUTUBE_CLIENT_ID"):
        YouTubeUploader()


def test_duplicate_detection_negative():
    init_db()
    # A random path that hasn't been uploaded
    assert _is_duplicate_local_path("/tmp/definitely_not_uploaded.mp4") is False


def test_video_metadata_defaults():
    md = VideoMetadata(
        title="Test Video",
        description="A test",
        tags=["Shorts"],
    )
    assert md.visibility == "private"
    assert md.made_for_kids is False
    assert md.contains_ai_generated is False


def test_video_metadata_title_truncation():
    md = VideoMetadata(
        title="x" * 200,
        description="",
        tags=[],
    )
    # Truncation happens at upload time, not in the dataclass
    assert len(md.title) == 200  # stored as-is; uploader truncates


def test_uploader_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "fake_id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "fake_secret")
    from src.youtube.uploader import YouTubeUploader
    # Patch build_youtube_client so it doesn't trigger OAuth
    with patch("src.youtube.uploader.build_youtube_client", return_value=MagicMock()):
        uploader = YouTubeUploader()
        md = VideoMetadata(title="Test", description="", tags=[])
        result = uploader.upload(tmp_path / "nonexistent.mp4", md)
    assert not result.success
    assert "not found" in result.failure_reason.lower()


class TestVideoFileHash:
    def test_produces_64_char_hex(self, tmp_path):
        f = tmp_path / "test.mp4"
        f.write_bytes(b"\x00\x01\x02\x03" * 1000)
        h = video_file_hash(f)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self, tmp_path):
        a = tmp_path / "a.mp4"
        b = tmp_path / "b.mp4"
        a.write_bytes(b"hello world")
        b.write_bytes(b"hello world")
        assert video_file_hash(a) == video_file_hash(b)

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.mp4"
        b = tmp_path / "b.mp4"
        a.write_bytes(b"hello")
        b.write_bytes(b"world")
        assert video_file_hash(a) != video_file_hash(b)


class TestIsDuplicateFileHash:
    def test_no_match_returns_none(self):
        init_db()
        result = _is_duplicate_file_hash("0" * 64)
        assert result is None

    def test_empty_hash_returns_none(self):
        result = _is_duplicate_file_hash("")
        assert result is None

    def test_known_uploaded_hash_returns_youtube_id(self):
        init_db()
        # Render 6 has file_hash and youtube_id from production history
        import sqlite3
        from src.core.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT file_hash, youtube_id FROM renders WHERE youtube_id IS NOT NULL LIMIT 1"
        ).fetchone()
        conn.close()
        if row and row["file_hash"]:
            result = _is_duplicate_file_hash(row["file_hash"])
            assert result == row["youtube_id"]


class TestVideoMetadataPublishAt:
    def test_publish_at_defaults_empty(self):
        md = VideoMetadata(title="Test", description="", tags=[])
        assert md.publish_at == ""

    def test_publish_at_stored(self):
        ts = "2026-11-21T17:00:00.000Z"
        md = VideoMetadata(title="Test", description="", tags=[], publish_at=ts)
        assert md.publish_at == ts
