"""
9:16 reframer: converts any source resolution to 1080×1920 vertical video.

Strategy:
  1. Scale source so height = 1920 (keeps aspect ratio)
  2. The scaled width will be wider than 1080 (for 16:9 source: ~3413px)
  3. Crop 1080px from the horizontal anchor position (0.0=left … 1.0=right)
  4. Result: 1080×1920 at correct pixel aspect ratio

The crop anchor comes from ClipSpec.crop_x_pct (0.5 = dead center).
Clamp logic ensures the crop window never exceeds the scaled frame width.

FFmpeg filter used:
  scale=-2:1920,crop=1080:1920:CROP_X:0

where CROP_X = max(0, min(scaled_width - 1080, (scaled_width - 1080) * crop_x_pct))
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from src.clipping.models import ClipSpec
from src.core.logger import get_logger

logger = get_logger(__name__)

TARGET_W = 1080
TARGET_H = 1920


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise EnvironmentError("ffmpeg not found on PATH")
    return path


def _ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise EnvironmentError("ffprobe not found on PATH")
    return path


def _probe_dimensions(video_path: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = subprocess.run(
        [
            _ffprobe(), "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(video_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-300:]}")
    parts = result.stdout.strip().split(",")
    if len(parts) < 2:
        raise RuntimeError(f"Unexpected ffprobe output: {result.stdout!r}")
    return int(parts[0]), int(parts[1])


def _build_scale_crop_filter(src_w: int, src_h: int, crop_x_pct: float) -> str:
    """
    Return the FFmpeg video filter string that scales to 1920 height then
    crops 1080 wide at the given horizontal anchor.
    """
    scale_factor = TARGET_H / src_h
    scaled_w = int(src_w * scale_factor)

    # Round scaled_w to nearest even (required by libx264)
    if scaled_w % 2 != 0:
        scaled_w += 1

    max_crop_x = scaled_w - TARGET_W
    if max_crop_x <= 0:
        # Source is narrower than 1080 after scaling — force centre
        crop_x = 0
    else:
        crop_x = int(max_crop_x * crop_x_pct)
        crop_x = max(0, min(max_crop_x, crop_x))
        # Ensure even (libx264 requirement)
        if crop_x % 2 != 0:
            crop_x = max(0, crop_x - 1)

    return f"scale={scaled_w}:{TARGET_H},crop={TARGET_W}:{TARGET_H}:{crop_x}:0"


def reframe_clip(
    clip: ClipSpec,
    output_path: Path,
) -> Path:
    """
    Extract the clip from its source, reframe to 1080×1920, and write to output_path.

    Returns output_path.
    Raises RuntimeError on FFmpeg failure.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    src_w, src_h = _probe_dimensions(clip.source_path)
    vf = _build_scale_crop_filter(src_w, src_h, clip.crop_x_pct)

    duration = clip.duration
    ff = _ffmpeg()

    cmd = [
        ff, "-y",
        "-ss", f"{clip.start:.3f}",
        "-i", str(clip.source_path),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info(
        "reframe_start",
        source=clip.source_path.name,
        t_start=round(clip.start, 2),
        duration=round(duration, 2),
        vf=vf,
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg reframe failed:\n{result.stderr[-600:]}"
        )

    logger.info("reframe_done", output=output_path.name)
    return output_path
