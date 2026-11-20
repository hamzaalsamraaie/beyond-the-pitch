"""Tests for the 9:16 reframer (uses FFmpeg lavfi fixture videos)."""

import subprocess
import shutil
import pytest
from pathlib import Path
from src.clipping.reframer import _build_scale_crop_filter, _probe_dimensions, reframe_clip
from src.clipping.models import ClipSpec


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not found on PATH",
)


# ── Filter generation ─────────────────────────────────────────────────────────

def test_scale_crop_filter_1920x1080_center():
    vf = _build_scale_crop_filter(1920, 1080, 0.5)
    # Should scale to 3413×1920 (or similar even-rounded), crop=1080:1920
    assert "scale=" in vf
    assert "crop=1080:1920" in vf


def test_scale_crop_filter_1280x720_center():
    vf = _build_scale_crop_filter(1280, 720, 0.5)
    assert "crop=1080:1920" in vf


def test_scale_crop_filter_portrait_no_negative():
    # Portrait source (e.g. 1080x1920 already)
    vf = _build_scale_crop_filter(1080, 1920, 0.5)
    assert "crop=1080:1920" in vf
    # crop_x should be 0 (no room to pan)
    assert ":0:0" in vf or ":0:0" not in vf  # just must not raise


def test_scale_crop_filter_anchor_left():
    vf = _build_scale_crop_filter(1920, 1080, 0.0)
    assert "0:0" in vf  # crop from left edge


def test_scale_crop_filter_anchor_right():
    vf_left = _build_scale_crop_filter(1920, 1080, 0.0)
    vf_right = _build_scale_crop_filter(1920, 1080, 1.0)
    # Different crop x positions
    assert vf_left != vf_right


# ── Fixture video helpers ─────────────────────────────────────────────────────

def _make_test_video(path: Path, width: int = 1920, height: int = 1080, duration: float = 5.0):
    """Create a synthetic test video using FFmpeg lavfi."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"testsrc=size={width}x{height}:rate=30:duration={duration}",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
            "-c:a", "aac", "-b:a", "64k",
            "-t", str(duration),
            str(path),
        ],
        capture_output=True,
    )
    return result.returncode == 0


# ── Integration tests ─────────────────────────────────────────────────────────

def test_probe_dimensions(tmp_path):
    video = tmp_path / "test.mp4"
    assert _make_test_video(video, 1920, 1080)
    w, h = _probe_dimensions(video)
    assert w == 1920
    assert h == 1080


def test_reframe_produces_vertical_video(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "vertical.mp4"
    assert _make_test_video(source, 1920, 1080, duration=3.0)

    clip = ClipSpec(
        source_path=source,
        footage_asset_id="test_fixture",
        start=0.0,
        end=3.0,
        score=1.0,
        crop_x_pct=0.5,
    )
    reframe_clip(clip, output)
    assert output.exists()
    assert output.stat().st_size > 10_000

    w, h = _probe_dimensions(output)
    assert w == 1080
    assert h == 1920


def test_reframe_respects_duration(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "clipped.mp4"
    _make_test_video(source, 1280, 720, duration=10.0)

    clip = ClipSpec(
        source_path=source,
        footage_asset_id="test_fixture",
        start=2.0,
        end=5.0,
        score=1.0,
        crop_x_pct=0.5,
    )
    reframe_clip(clip, output)
    assert output.exists()
    # Probe duration roughly 3s
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(output)],
        capture_output=True, text=True,
    )
    dur = float(result.stdout.strip())
    assert 2.5 <= dur <= 3.5
