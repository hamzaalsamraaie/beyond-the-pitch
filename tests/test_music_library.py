"""Tests for src/editing/music_library.py."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from src.editing.music_library import (
    EmbedPolicy,
    LicenseType,
    MusicTrack,
    TRACKS,
    all_tracks_are_placeholders,
    get_track,
    is_placeholder,
    verify_library,
    licensing_manifest,
)


class TestTrackRegistry:
    def test_all_tracks_have_filenames(self):
        for t in TRACKS:
            assert t.filename.endswith(".mp3")

    def test_all_tracks_have_story_types(self):
        for t in TRACKS:
            assert len(t.story_types) > 0

    def test_all_tracks_are_placeholders(self):
        assert all_tracks_are_placeholders() is True

    def test_placeholder_embed_policy(self):
        for t in TRACKS:
            assert t.embed_policy == EmbedPolicy.PLACEHOLDER

    def test_track_bpm_positive(self):
        for t in TRACKS:
            assert t.bpm > 0

    def test_track_platforms_empty_for_placeholders(self):
        for t in TRACKS:
            if t.license_type == LicenseType.PLACEHOLDER:
                assert t.platforms_allowed == []


class TestIsPlaceholder:
    def test_placeholder_track_returns_true(self):
        t = TRACKS[0]
        assert is_placeholder(t) is True

    def test_free_track_returns_false(self):
        t = MusicTrack(
            filename="real.mp3",
            title="Real Track",
            artist="Artist",
            bpm=120.0,
            genre="cinematic",
            license_type=LicenseType.CC0,
            license_url="https://example.com/license",
            source_url="https://example.com/track",
            file_hash_sha256="abc123",
            embed_policy=EmbedPolicy.FREE_EMBED,
            platforms_allowed=["youtube", "tiktok"],
            story_types=["dramatic"],
        )
        assert is_placeholder(t) is False


class TestGetTrack:
    def test_returns_none_when_no_files_exist(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        result = get_track("dramatic")
        assert result is None

    def test_returns_track_when_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        (tmp_path / "epic_cinematic_cc0.mp3").write_bytes(b"\xff\xfb" * 100)
        result = get_track("dramatic")
        assert result is not None
        assert result.filename == "epic_cinematic_cc0.mp3"

    def test_returns_closest_bpm(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        # All placeholders have bpm=110; requesting 95 should still return one
        (tmp_path / "epic_cinematic_cc0.mp3").write_bytes(b"\xff\xfb" * 100)
        result = get_track("dramatic", bpm_hint=95.0)
        assert result is not None

    def test_fallback_to_all_tracks_on_unknown_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        (tmp_path / "inspiring_sport_cc0.mp3").write_bytes(b"\xff\xfb" * 100)
        result = get_track("completely_unknown_type")
        assert result is not None

    def test_placeholder_track_returned_on_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        (tmp_path / "epic_cinematic_cc0.mp3").write_bytes(b"\xff\xfb" * 100)
        result = get_track("dramatic")
        assert result is not None
        assert is_placeholder(result) is True


class TestVerifyLibrary:
    def test_missing_files_return_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        result = verify_library()
        for status in result.values():
            assert status == "missing"

    def test_placeholder_files_return_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        (tmp_path / "epic_cinematic_cc0.mp3").write_bytes(b"\xff\xfb" * 100)
        result = verify_library()
        assert result.get("epic_cinematic_cc0.mp3") == "placeholder"

    def test_hash_mismatch_detected(self, tmp_path, monkeypatch):
        from src.editing.music_library import TRACKS, LicenseType, EmbedPolicy, MusicTrack
        # Patch TRACKS with a non-placeholder track that has wrong hash
        real_track = MusicTrack(
            filename="test_real.mp3",
            title="Real Track",
            artist="Artist",
            bpm=120.0,
            genre="cinematic",
            license_type=LicenseType.CC0,
            license_url="https://example.com/lic",
            source_url="https://example.com/src",
            file_hash_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            embed_policy=EmbedPolicy.FREE_EMBED,
            platforms_allowed=["youtube"],
            story_types=["dramatic"],
        )
        (tmp_path / "test_real.mp3").write_bytes(b"\xff\xfb" * 100)
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        monkeypatch.setattr("src.editing.music_library.TRACKS", [real_track])
        result = verify_library()
        assert "hash_mismatch" in result.get("test_real.mp3", "")


class TestLicensingManifest:
    def test_returns_one_entry_per_track(self):
        manifest = licensing_manifest()
        assert len(manifest) == len(TRACKS)

    def test_each_entry_has_required_fields(self):
        for entry in licensing_manifest():
            assert "filename" in entry
            assert "license_type" in entry
            assert "embed_policy" in entry
            assert "hash_verified" in entry

    def test_missing_file_shows_as_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.editing.music_library._MUSIC_DIR", tmp_path)
        manifest = licensing_manifest()
        for entry in manifest:
            assert entry["actual_hash"] == "(missing)"
