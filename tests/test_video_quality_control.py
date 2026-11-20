"""Tests for the QC module. Uses a real video produced by FFmpeg."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from src.video.quality_control import QCResult, run_qc


def _make_test_video(
    width: int = 1080,
    height: int = 1920,
    duration: float = 5.0,
    with_audio: bool = True,
    out_dir: str | None = None,
) -> Path:
    """Create a minimal test MP4 using FFmpeg lavfi sources."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    tmp = Path(out_dir) if out_dir else Path(tempfile.mkdtemp())
    out = tmp / f"test_{width}x{height}.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s={width}x{height}:r=30",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += [
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


def test_qc_passes_valid_video():
    with tempfile.TemporaryDirectory() as tmp:
        video = _make_test_video(1080, 1920, 10.0, with_audio=True, out_dir=tmp)
        result = run_qc(video, expected_duration_secs=10.0)
        assert result.passed, result.report()
        assert result.measured_width == 1080
        assert result.measured_height == 1920
        assert result.has_audio is True


def test_qc_fails_wrong_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        video = _make_test_video(640, 480, 10.0, with_audio=True, out_dir=tmp)
        result = run_qc(video, expected_duration_secs=10.0)
        assert not result.passed
        assert any("1080" in f for f in result.failures)
        assert any("1920" in f for f in result.failures)


def test_qc_fails_duration_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        video = _make_test_video(1080, 1920, 10.0, with_audio=True, out_dir=tmp)
        result = run_qc(video, expected_duration_secs=25.0)
        assert not result.passed
        assert any("Duration" in f for f in result.failures)


def test_qc_fails_missing_file():
    result = run_qc(Path("/nonexistent/file.mp4"), expected_duration_secs=10.0)
    assert not result.passed
    assert any("does not exist" in f for f in result.failures)


def test_qc_warns_missing_audio_for_mock():
    with tempfile.TemporaryDirectory() as tmp:
        # Create video without audio
        video = _make_test_video(1080, 1920, 10.0, with_audio=False, out_dir=tmp)
        result = run_qc(video, expected_duration_secs=10.0, tts_provider="mock")
        # For mock TTS, missing audio is a warning, not a failure
        assert result.has_audio is False
        assert any("audio" in w.lower() or "silence" in w.lower() for w in result.warnings)


def test_qc_report_string():
    with tempfile.TemporaryDirectory() as tmp:
        video = _make_test_video(1080, 1920, 5.0, with_audio=True, out_dir=tmp)
        result = run_qc(video, expected_duration_secs=5.0)
        report = result.report()
        assert "QC" in report
        assert "1080" in report
        assert "1920" in report
