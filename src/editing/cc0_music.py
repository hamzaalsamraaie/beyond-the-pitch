"""
CC0 music selection and embedding for automated production.

Selects a CC0 (public domain) background music track that matches the story
type and embeds it into the video at a safe background level (-20 dBFS).

Tracks are stored locally in assets/music/. If the file is absent, the step
is skipped — the video is still produced, just without background music.
YouTube Shorts recommends adding trending audio via the Shorts picker instead.

Embed policy:
  FREE_EMBED   — CC0/public domain; safe to embed and monetize
  SHORTS_ONLY  — must be added via YouTube Shorts picker post-upload
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_MUSIC_DIR = Path(__file__).resolve().parents[2] / "assets" / "music"


@dataclass(frozen=True)
class CC0Track:
    filename: str           # relative to assets/music/
    title: str
    bpm: float
    story_types: list[str]  # e.g. ["dramatic", "worldcup", "motivation"]
    attribution: str        # "CC0 — no attribution required" or specific text


# Curated CC0 tracks — all public domain / CC0 license
# Actual MP3 files must be placed in assets/music/ before production.
# Download sources listed in attribution field.
_CC0_TRACKS: list[CC0Track] = [
    CC0Track(
        filename="epic_cinematic_cc0.mp3",
        title="Epic Cinematic Background",
        bpm=90,
        story_types=["dramatic", "worldcup", "moments", "player_stories"],
        attribution="CC0 — Pixabay Music (pixabay.com)",
    ),
    CC0Track(
        filename="inspiring_sport_cc0.mp3",
        title="Inspiring Sport",
        bpm=120,
        story_types=["motivation", "comeback", "player_stories"],
        attribution="CC0 — Pixabay Music (pixabay.com)",
    ),
    CC0Track(
        filename="stadium_atmosphere_cc0.mp3",
        title="Stadium Atmosphere",
        bpm=110,
        story_types=["moments", "worldcup", "dramatic"],
        attribution="CC0 — Pixabay Music (pixabay.com)",
    ),
    CC0Track(
        filename="tension_buildup_cc0.mp3",
        title="Tension Buildup",
        bpm=100,
        story_types=["dramatic", "thriller", "moments"],
        attribution="CC0 — Pixabay Music (pixabay.com)",
    ),
]


def select_cc0_track(story_type: str, bpm_hint: float = 100.0) -> CC0Track | None:
    """
    Return the best available CC0 track for the given story_type.
    'Available' means the MP3 file exists in assets/music/.
    Returns None if no suitable track exists locally.
    """
    story_type_lower = story_type.lower()
    matches = [t for t in _CC0_TRACKS if story_type_lower in t.story_types]
    if not matches:
        matches = _CC0_TRACKS  # fall back to all tracks

    available = [t for t in matches if (_MUSIC_DIR / t.filename).exists()]
    if not available:
        return None

    # Prefer track with BPM closest to hint
    return min(available, key=lambda t: abs(t.bpm - bpm_hint))


def embed_cc0_music(
    video_path: Path,
    track: CC0Track,
    output_path: Path,
    music_volume_db: float = -20.0,
) -> bool:
    """
    Mix CC0 music bed into video at music_volume_db relative to -0 dBFS.
    Existing audio (narration, crowd) is preserved; music sits underneath.

    Returns True on success. Never raises — failures are logged and skipped.
    """
    music_path = _MUSIC_DIR / track.filename
    if not music_path.exists():
        logger.warning("cc0_music_missing", filename=track.filename)
        return False

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ff = shutil.which("ffmpeg")
    if not ff:
        logger.error("ffmpeg_not_found")
        return False

    duration_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(duration_result.stdout.strip())
    except ValueError:
        duration = 60.0

    # Probe whether the video has an audio stream
    has_video_audio = False
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", str(video_path)],
            capture_output=True, text=True,
        )
        import json as _json
        streams = _json.loads(probe.stdout).get("streams", [])
        has_video_audio = any(s.get("codec_type") == "audio" for s in streams)
    except Exception:
        pass

    if has_video_audio:
        # Mix music under existing audio
        audio_filter = (
            f"[1:a]volume={music_volume_db}dB,"
            f"atrim=0:{duration:.2f},asetpts=PTS-STARTPTS,"
            f"aresample=48000[music];"
            "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        # No video audio — music becomes the sole audio track (slight boost)
        audio_filter = (
            f"[1:a]volume={music_volume_db + 6:.1f}dB,"
            f"atrim=0:{duration:.2f},asetpts=PTS-STARTPTS,"
            f"aresample=48000[aout]"
        )

    cmd = [
        ff, "-y",
        "-i", str(video_path),
        "-i", str(music_path),
        "-filter_complex", audio_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("cc0_music_embed_failed", error=result.stderr[-200:])
        return False

    logger.info("cc0_music_embedded", track=track.title, output=output_path.name)
    return True
