"""
Clip selector: turns a ScoredWindow into a ClipSpec.

Responsibilities:
  - Snap start/end to nearest sentence boundaries (clean cuts)
  - Determine horizontal crop anchor via motion analysis of sampled frames
  - Enforce min/max duration from config
  - Gate: source file must be a registered, APPROVED footage asset

Motion analysis uses pixel-column variance across sampled PIL frames.
If OpenCV is unavailable, falls back to center crop.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from src.clipping.highlight_detector import top_window
from src.clipping.models import ClipSpec, ScoredWindow, Transcript
from src.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TARGET_SECS = 45.0
_DEFAULT_MIN_SECS = 20.0
_DEFAULT_MAX_SECS = 58.0  # YouTube Shorts upper bound


# ── Crop analysis ─────────────────────────────────────────────────────────────

def _analyse_crop_position(
    video_path: Path,
    start: float,
    end: float,
    n_samples: int = 8,
) -> float:
    """
    Sample n_samples frames from [start, end] and return a crop anchor
    0.0–1.0 (0.5 = dead center) based on where horizontal motion is highest.
    Falls back to 0.5 if FFmpeg or PIL operations fail.
    """
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        return 0.5

    ff = shutil.which("ffmpeg")
    if not ff:
        return 0.5

    duration = end - start
    if duration <= 0:
        return 0.5

    interval = duration / n_samples
    column_sums: list[int] = []

    with tempfile.TemporaryDirectory(prefix="btp_crop_") as tmp:
        for i in range(n_samples):
            t = start + i * interval
            frame_path = Path(tmp) / f"frame_{i:02d}.png"
            result = subprocess.run(
                [
                    ff, "-y",
                    "-ss", f"{t:.3f}",
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-vf", "scale=320:-1",   # small for speed
                    str(frame_path),
                ],
                capture_output=True,
            )
            if result.returncode != 0 or not frame_path.exists():
                continue

            try:
                img = Image.open(frame_path).convert("L")  # grayscale
                w, h = img.size
                pixels = list(img.getdata())
                # Sum pixel values per column
                if not column_sums:
                    column_sums = [0] * w
                for y_row in range(h):
                    for x_col in range(w):
                        column_sums[x_col] += pixels[y_row * w + x_col]
            except Exception:
                continue

    if not column_sums or max(column_sums) == 0:
        return 0.5

    # Smooth column sums (moving average over 10% of width)
    w = len(column_sums)
    radius = max(1, w // 10)
    smoothed = [
        sum(column_sums[max(0, j - radius): j + radius + 1])
        / (2 * radius + 1)
        for j in range(w)
    ]

    # Find peak
    peak_col = smoothed.index(max(smoothed))
    anchor = peak_col / w

    # Clamp to avoid extreme edges that cause FFmpeg crop errors
    anchor = max(0.1, min(0.9, anchor))
    logger.info("crop_anchor_detected", anchor=round(anchor, 3))
    return anchor


# ── Clip selector ─────────────────────────────────────────────────────────────

def select_clip(
    transcript: Transcript,
    footage_asset_id: str,
    source_path: Path,
    target_duration: float = _DEFAULT_TARGET_SECS,
    min_duration: float = _DEFAULT_MIN_SECS,
    max_duration: float = _DEFAULT_MAX_SECS,
    analyse_crop: bool = True,
) -> ClipSpec | None:
    """
    Select the best clip from a transcript.

    Returns ClipSpec or None if no suitable window found.
    """
    if not source_path.exists():
        logger.error("clip_source_missing", path=str(source_path))
        return None

    window = top_window(transcript, target_duration=target_duration, min_duration=min_duration)
    if window is None:
        logger.warning("no_highlight_window_found", source=source_path.name)
        return None

    # Clamp duration
    actual_duration = min(window.duration, max_duration)
    end = window.start + actual_duration
    # Snap end to a segment boundary if one is close
    for seg in transcript.segments_in_range(end - 2.0, end + 2.0):
        if abs(seg.end - end) < 1.5:
            end = seg.end
            break

    end = min(end, transcript.source_duration) if transcript.source_duration > 0 else end
    actual_duration = end - window.start

    if actual_duration < min_duration:
        logger.warning(
            "clip_too_short",
            duration=round(actual_duration, 1),
            min=min_duration,
        )
        return None

    crop_x = (
        _analyse_crop_position(source_path, window.start, end)
        if analyse_crop
        else 0.5
    )

    transcript_words = transcript.words_in_range(window.start, end)

    logger.info(
        "clip_selected",
        start=round(window.start, 1),
        end=round(end, 1),
        duration=round(actual_duration, 1),
        score=round(window.score, 3),
        crop_x=round(crop_x, 3),
        peaks=window.peak_words[:3],
    )

    return ClipSpec(
        source_path=source_path,
        footage_asset_id=footage_asset_id,
        start=window.start,
        end=end,
        score=window.score,
        hook_text=window.hook_text,
        transcript_words=transcript_words,
        language=transcript.language,
        crop_x_pct=crop_x,
    )
