"""
Audio mixer: normalises commentary loudness and optionally adds a music bed.

LUFS target: -16 LUFS integrated loudness (YouTube recommendation).
True Peak:   -1.5 dBTP

Music bed (optional):
  - Mixed at -20 dBFS under the commentary
  - Loops if shorter than the clip
  - Must be a rights-cleared audio file (YouTube Audio Library or CC BY)

FFmpeg loudnorm filter is used for two-pass normalisation:
  Pass 1: measure current LUFS/TP/LRA
  Pass 2: apply the corrective offset
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_TARGET_LUFS = -16.0
_TARGET_TP = -1.5
_TARGET_LRA = 11.0
_MUSIC_BED_GAIN_DB = -20.0   # dB gain for music under commentary


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise EnvironmentError("ffmpeg not found on PATH")
    return path


# ── Single-pass normalise (fast, slight inaccuracy acceptable) ────────────────

def normalise_audio(
    input_path: Path,
    output_path: Path,
) -> Path:
    """
    Apply loudnorm in single-pass linear mode.
    Fast but less accurate than two-pass. Suitable for V1.
    Returns output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ff = _ffmpeg()

    cmd = [
        ff, "-y",
        "-i", str(input_path),
        "-af",
        (
            f"loudnorm=I={_TARGET_LUFS}:TP={_TARGET_TP}:LRA={_TARGET_LRA}"
            ":linear=true:print_format=json"
        ),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("audio_normalise_start", input=input_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"loudnorm failed:\n{result.stderr[-500:]}")

    logger.info("audio_normalise_done", output=output_path.name)
    return output_path


# ── Music bed mixer ───────────────────────────────────────────────────────────

def mix_music_bed(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    music_gain_db: float = _MUSIC_BED_GAIN_DB,
) -> Path:
    """
    Mix a music bed under the existing audio.

    The music is looped (if shorter than the video) and reduced by music_gain_db.
    Commentary (input audio) is kept at its current level.
    Both are normalised in the final output.

    Returns output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ff = _ffmpeg()

    # Stream 0: video + commentary, Stream 1: music
    # -stream_loop -1 loops the music
    # amix with weights gives us commentary dominance
    gain_linear = 10 ** (music_gain_db / 20.0)

    cmd = [
        ff, "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        (
            f"[1:a]volume={gain_linear:.4f}[music];"
            "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        ),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("music_mix_start", video=video_path.name, music=music_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Music mix failed:\n{result.stderr[-500:]}")

    logger.info("music_mix_done", output=output_path.name)
    return output_path
