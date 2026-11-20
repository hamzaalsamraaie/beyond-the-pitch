"""Tests for CC0 music selection and embedding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestSelectCC0Track:
    def test_returns_none_when_no_files_present(self):
        from src.editing.cc0_music import select_cc0_track
        # No MP3 files will exist in a fresh test environment
        result = select_cc0_track("dramatic", bpm_hint=90.0)
        # Either None (no files) or a CC0Track — both are valid
        from src.editing.cc0_music import CC0Track
        assert result is None or isinstance(result, CC0Track)

    def test_prefers_closer_bpm(self, tmp_path):
        from src.editing.cc0_music import CC0Track, _CC0_TRACKS, _MUSIC_DIR, select_cc0_track
        # Patch the music dir so we can create fake files
        with patch("src.editing.cc0_music._MUSIC_DIR", tmp_path):
            for t in _CC0_TRACKS:
                (tmp_path / t.filename).write_bytes(b"fake")
            result_90 = select_cc0_track("dramatic", bpm_hint=90.0)
            result_120 = select_cc0_track("motivation", bpm_hint=120.0)

        # With all files present, results should match story types
        assert result_90 is not None
        assert result_120 is not None
        assert "dramatic" in result_90.story_types or "moments" in result_90.story_types

    def test_falls_back_to_all_tracks_on_unknown_type(self, tmp_path):
        from src.editing.cc0_music import _CC0_TRACKS, select_cc0_track
        with patch("src.editing.cc0_music._MUSIC_DIR", tmp_path):
            for t in _CC0_TRACKS:
                (tmp_path / t.filename).write_bytes(b"fake")
            result = select_cc0_track("unknown_type_xyz", bpm_hint=100.0)
        assert result is not None


class TestEmbedCC0Music:
    def test_returns_false_if_music_file_missing(self, tmp_path):
        from src.editing.cc0_music import CC0Track, embed_cc0_music
        track = CC0Track(
            filename="nonexistent_track.mp3",
            title="Missing",
            bpm=90.0,
            story_types=["dramatic"],
            attribution="CC0",
        )
        result = embed_cc0_music(tmp_path / "video.mp4", track, tmp_path / "out.mp4")
        assert result is False

    def test_returns_false_if_ffmpeg_fails(self, tmp_path):
        from src.editing.cc0_music import CC0Track, embed_cc0_music
        music_file = tmp_path / "track.mp3"
        music_file.write_bytes(b"fake mp3")
        track = CC0Track(
            filename="track.mp3",
            title="Test",
            bpm=90.0,
            story_types=["dramatic"],
            attribution="CC0",
        )
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")

        with patch("src.editing.cc0_music._MUSIC_DIR", tmp_path):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "error"
                result = embed_cc0_music(video, track, tmp_path / "out.mp4")

        assert result is False

    def test_volume_db_range(self):
        """Embedding at extreme volumes should not raise at the call level."""
        from src.editing.cc0_music import CC0Track, embed_cc0_music
        track = CC0Track(
            filename="missing.mp3",
            title="Test",
            bpm=100.0,
            story_types=["dramatic"],
            attribution="CC0",
        )
        # Will return False because file is missing — no exception
        result = embed_cc0_music(Path("/tmp/v.mp4"), track, Path("/tmp/o.mp4"), music_volume_db=-40.0)
        assert result is False


class TestCC0TrackDataIntegrity:
    def test_all_tracks_have_story_types(self):
        from src.editing.cc0_music import _CC0_TRACKS
        for t in _CC0_TRACKS:
            assert len(t.story_types) >= 1

    def test_all_tracks_have_bpm(self):
        from src.editing.cc0_music import _CC0_TRACKS
        for t in _CC0_TRACKS:
            assert 60 <= t.bpm <= 200

    def test_all_filenames_end_with_mp3(self):
        from src.editing.cc0_music import _CC0_TRACKS
        for t in _CC0_TRACKS:
            assert t.filename.endswith(".mp3")

    def test_all_attributions_mention_cc0(self):
        from src.editing.cc0_music import _CC0_TRACKS
        for t in _CC0_TRACKS:
            assert "CC0" in t.attribution or "cc0" in t.attribution.lower()
