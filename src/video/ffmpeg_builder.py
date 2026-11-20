"""
FFmpeg pipeline builder.

Assembles per-scene audio WAV files and a stream of PIL Image frames
into a single 1080×1920 H.264/AAC MP4.

Approach:
  1. Concatenate all per-scene WAV files into one combined WAV.
  2. Pipe PIL Image frames as raw RGB bytes into FFmpeg stdin.
  3. FFmpeg reads combined audio from a file simultaneously.
  4. Single encode pass: no temp MP4 files, no quality loss from double-encode.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

from PIL import Image

from src.core.config import get_section
from src.core.logger import get_logger

logger = get_logger(__name__)

W, H = 1080, 1920


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise EnvironmentError("ffmpeg not found on PATH — run: brew install ffmpeg")
    return path


def concatenate_audio(scene_audio_paths: list[Path], output_path: Path) -> None:
    """
    Concatenate WAV files in order using FFmpeg concat demuxer.
    Writes a single PCM WAV to output_path.
    """
    if not scene_audio_paths:
        raise ValueError("scene_audio_paths must not be empty")

    concat_list = output_path.with_suffix(".concat.txt")
    with open(concat_list, "w", encoding="utf-8") as fh:
        for p in scene_audio_paths:
            fh.write(f"file '{p.resolve()}'\n")

    result = subprocess.run(
        [
            _ffmpeg(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:a", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ],
        capture_output=True, text=True,
    )
    concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Audio concat failed:\n{result.stderr[-500:]}")
    logger.info("audio_concat_done", output=output_path.name)


def pipe_frames_to_mp4(
    frame_generator: Generator[Image.Image, None, None],
    total_frames: int,
    fps: int,
    combined_audio_path: Path,
    output_path: Path,
) -> None:
    """
    Pipe PIL Image frames as raw RGB24 to FFmpeg stdin.
    FFmpeg mixes with the combined audio file and writes MP4.
    """
    cfg = get_section("video")
    crf = cfg.get("crf", 23)
    audio_bitrate = cfg.get("audio_bitrate", "128k")

    cmd = [
        _ffmpeg(), "-y",
        # Video input: raw RGB frames from stdin
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{W}x{H}",
        "-framerate", str(fps),
        "-i", "pipe:0",
        # Audio input: pre-combined WAV file
        "-i", str(combined_audio_path),
        # Video encoding
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        # Audio encoding
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        # Container
        "-movflags", "+faststart",
        # Safety: stop when the shorter of the two inputs ends
        "-shortest",
        str(output_path),
    ]

    logger.info("ffmpeg_pipe_start", output=output_path.name, frames=total_frames)

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    frames_written = 0
    try:
        for img in frame_generator:
            proc.stdin.write(img.tobytes())
            frames_written += 1
            if frames_written % 150 == 0:
                logger.info("frames_piped", count=frames_written, total=total_frames)
    finally:
        proc.stdin.close()

    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg pipe failed after {frames_written} frames:\n{stderr.decode()[-600:]}"
        )

    logger.info("ffmpeg_pipe_done", frames=frames_written, output=output_path.name)
