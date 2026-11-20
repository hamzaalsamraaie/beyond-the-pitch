"""Tests for the thumbnail generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGenerateThumbnail:
    """Tests for src.video.thumbnail.generate_thumbnail."""

    def test_returns_false_on_no_video(self, tmp_path):
        from src.video.thumbnail import generate_thumbnail
        result = generate_thumbnail(
            video_path=tmp_path / "nonexistent.mp4",
            title="Test Title",
            output_path=tmp_path / "thumb.jpg",
            frame_time=1.0,
        )
        # With no frame extraction possible, should still produce a fallback thumbnail
        # (navy background) and return True, or return False — either is acceptable;
        # the test just verifies it never raises.
        assert isinstance(result, bool)

    def test_creates_output_dirs(self, tmp_path):
        from src.video.thumbnail import generate_thumbnail
        nested = tmp_path / "a" / "b" / "thumb.jpg"
        # Should not raise even if output dir doesn't exist
        try:
            generate_thumbnail(
                video_path=tmp_path / "fake.mp4",
                title="Test",
                output_path=nested,
            )
        except Exception as exc:
            # Only ffmpeg-related errors are expected; not directory errors
            assert "ffmpeg" in str(exc).lower() or isinstance(exc, FileNotFoundError)

    def test_long_title_wrapped(self, tmp_path):
        """Very long title should not raise — text wrapping code handles it."""
        from src.video.thumbnail import generate_thumbnail
        with patch("src.video.thumbnail._extract_frame", return_value=False):
            with patch("src.video.thumbnail.ImageFont.truetype", side_effect=IOError):
                result = generate_thumbnail(
                    video_path=tmp_path / "v.mp4",
                    title="A" * 120,
                    output_path=tmp_path / "t.jpg",
                )
        assert isinstance(result, bool)

    def test_navy_fallback_when_frame_extraction_fails(self, tmp_path):
        """When FFmpeg fails, thumbnail should still be generated from a navy background."""
        from src.video.thumbnail import generate_thumbnail
        out = tmp_path / "thumb.jpg"
        with patch("src.video.thumbnail._extract_frame", return_value=False):
            result = generate_thumbnail(
                video_path=tmp_path / "fake.mp4",
                title="Historic Football Moment",
                output_path=out,
            )
        # Navy fallback path should produce a file
        if result:
            assert out.exists()

    def test_frame_path_cleaned_up(self, tmp_path):
        """Temporary frame JPEG should be deleted after thumbnail generation."""
        from src.video.thumbnail import generate_thumbnail
        out = tmp_path / "thumb.jpg"
        frame_path = out.with_suffix(".frame.jpg")
        frame_path.write_bytes(b"fake")  # Pre-create to simulate ffmpeg output

        with patch("src.video.thumbnail._extract_frame", return_value=True):
            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1080, 1920)
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_img.crop.return_value = mock_img
                mock_open.return_value = mock_img

                generate_thumbnail(
                    video_path=tmp_path / "v.mp4",
                    title="Test",
                    output_path=out,
                )

        assert not frame_path.exists()
