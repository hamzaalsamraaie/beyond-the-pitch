#!/usr/bin/env python3
"""
Produce the first public Beyond The Pitch Short.

Story: Emiliano Martínez's record 11 saves in the 2026 World Cup Final —
       the goalkeeper who was perfect, and still lost.

Footage: Pexels "Exciting Soccer Match in Packed Stadium" (d437f9d3)
         - real match play, 1440×2560 portrait 9:16, 28s, no audio
Audio:   Crowd atmosphere from Pixabay CC0 (caace90c) mixed at -18 dBFS
Music:   NOT embedded — add "Goals" (Lisa, Anitta, Rema) via YouTube Shorts
         audio picker before publishing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from src.core.database import init_db, insert_render
from src.core.logger import configure_logging, get_logger
from src.clipping.caption_renderer import write_ass_file, burn_captions
from src.clipping.audio_mixer import normalise_audio
from src.clipping.models import WordTimestamp
from src.footage.catalog import FootageCatalog
from src.footage.gate import FootageGate, FootageGateError
from src.video.quality_control import run_qc

configure_logging()
logger = get_logger("produce_first_short")

PEXELS_ID = "d437f9d3-9a6d-4c48-93dd-38a58ee242c8"
PIXABAY_CROWD_ID = "caace90c-8160-42e3-95f1-6a6c0e78f824"
OUTPUT_PATH = _ROOT / "output" / "shorts" / "martinez_world_cup_short.mp4"

# ── Story beats: (start_sec, end_sec, text) ───────────────────────────────────
# Written to hit a 28-second runtime, hook in first 2 seconds.
STORY_BEATS = [
    # HOOK
    (0.0,  2.2,  "11 saves."),
    (2.2,  4.5,  "Still not enough."),
    # CONTEXT
    (4.5,  7.5,  "2026 World Cup Final"),
    (7.5,  11.0, "Argentina vs Spain"),
    # STAT BOMB
    (11.0, 15.0, "Argentina registered ZERO shots"),
    (15.0, 18.5, "in the first 90 minutes."),
    # CLIMAX
    (18.5, 21.5, "Then Torres. 106th minute."),
    (21.5, 24.5, "Spain 1 — 0 Argentina."),
    # PAYOFF
    (24.5, 27.5, "Martínez was perfect."),
    (27.5, 28.0, "Football was not."),
]

# BTP branding runs the full clip
BTP_BRAND = (0.0, 28.0, "BEYOND THE PITCH")


def _probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)


def _transcode_to_1080p(src: Path, dst: Path) -> None:
    """Scale 1440×2560 portrait → 1080×1920, copy or re-encode."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(src),
            "-vf", "scale=1080:1920",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",   # strip non-existent audio stream cleanly
            "-movflags", "+faststart",
            str(dst),
        ],
        capture_output=True, check=True,
    )
    logger.info("transcoded_to_1080p", output=dst.name)


def _add_crowd_audio(video_no_audio: Path, crowd_src: Path, dst: Path) -> None:
    """Mix crowd atmosphere from an external source at -18 dBFS into the video."""
    # Trim crowd audio to exactly match video duration, mix at low volume
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_no_audio),
            "-i", str(crowd_src),
            "-filter_complex",
            "[1:a]volume=-18dB,atrim=0:28,asetpts=PTS-STARTPTS[crowd];"
            "[crowd]aresample=48000[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(dst),
        ],
        capture_output=True, check=True,
    )
    logger.info("crowd_audio_added", output=dst.name)


def _build_story_ass(output_path: Path, beats: list, brand: tuple, duration: float) -> None:
    """Write a hand-crafted ASS file for the story beats."""
    WHITE = "&H00FFFFFF"
    GOLD = "&H004CA8C9"
    BLACK = "&H00000000"
    SHADOW = "&H80000000"
    W, H = 1080, 1920
    MARGIN_CAPTION = 180
    MARGIN_TOP = 60

    def _t(s: float) -> str:
        cs = int(round(s * 100))
        h = cs // 360000; cs %= 360000
        m = cs // 6000;   cs %= 6000
        sec = cs // 100;  cs %= 100
        return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

    lines = [
        "[Script Info]",
        "Title: Beyond The Pitch — Martínez 2026 WC Final",
        "ScriptType: v4.00+",
        "WrapStyle: 1",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: BTP_Hook,Arial,110,{GOLD},{GOLD},{BLACK},{SHADOW},-1,0,0,0,100,100,0,0,1,5,3,2,20,20,{MARGIN_CAPTION + 60},1",
        f"Style: BTP_Caption,Arial,86,{WHITE},{WHITE},{BLACK},{SHADOW},-1,0,0,0,100,100,0,0,1,4,2,2,20,20,{MARGIN_CAPTION},1",
        f"Style: BTP_Stat,Arial,96,{GOLD},{GOLD},{BLACK},{SHADOW},-1,0,0,0,100,100,0,0,1,5,3,2,20,20,{MARGIN_CAPTION + 20},1",
        f"Style: BTP_Brand,Arial,38,{GOLD},{GOLD},{BLACK},{SHADOW},-1,0,0,0,100,100,0,0,1,2,1,8,20,20,{MARGIN_TOP},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    # Hook beats (first 4.5s) in gold
    for i, (start, end, text) in enumerate(beats):
        style = "BTP_Hook" if start < 4.5 else ("BTP_Stat" if any(c.isdigit() for c in text) else "BTP_Caption")
        safe = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},{style},,0,0,0,,{safe}")

    # Branding always on
    s, e, txt = brand
    lines.append(f"Dialogue: 0,{_t(s)},{_t(e)},BTP_Brand,,0,0,0,,{txt}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("story_ass_written", events=len(beats), path=output_path.name)


def main() -> int:
    init_db()

    # Gate check
    catalog = FootageCatalog()
    gate = FootageGate(catalog)
    try:
        gate.check_all([PEXELS_ID])
    except FootageGateError as exc:
        print(f"GATE BLOCKED: {exc}")
        return 1
    print("✓ Footage gate passed")

    pexels_asset = catalog.get_asset(PEXELS_ID)
    pixabay_asset = catalog.get_asset(PIXABAY_CROWD_ID)
    pexels_path = Path(pexels_asset.local_path)
    crowd_path = Path(pixabay_asset.local_path)

    if not pexels_path.exists():
        print(f"ERROR: footage not found at {pexels_path}")
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="btp_first_short_") as tmp:
        tmp = Path(tmp)

        # 1. Transcode to 1080×1920
        print("⟳  Transcoding to 1080×1920…")
        vid_1080 = tmp / "vid_1080.mp4"
        _transcode_to_1080p(pexels_path, vid_1080)

        # 2. Add crowd atmosphere audio
        print("⟳  Adding crowd atmosphere audio…")
        vid_with_audio = tmp / "vid_audio.mp4"
        try:
            _add_crowd_audio(vid_1080, crowd_path, vid_with_audio)
        except subprocess.CalledProcessError as exc:
            print(f"   WARNING: crowd audio failed ({exc.stderr[-200:] if exc.stderr else exc}), using silent audio")
            # Fallback: add silent audio
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(vid_1080),
                 "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
                 str(vid_with_audio)],
                capture_output=True, check=True,
            )

        # 3. Write story captions
        print("⟳  Writing story captions…")
        ass_path = tmp / "story.ass"
        _build_story_ass(ass_path, STORY_BEATS, BTP_BRAND, duration=28.0)

        # 4. Burn captions
        print("⟳  Burning captions…")
        captioned = tmp / "captioned.mp4"
        burn_captions(vid_with_audio, ass_path, captioned)

        # 5. LUFS normalise
        print("⟳  Normalising audio…")
        normalised = tmp / "normalised.mp4"
        normalise_audio(captioned, normalised)

        # 6. Copy to output
        shutil.copy2(str(normalised), str(OUTPUT_PATH))

    # 7. QC
    qc = run_qc(OUTPUT_PATH, expected_duration_secs=28.0, tts_provider="pexels_match")
    print(f"\n{'✓' if qc.passed else '✗'}  QC: {qc.report()}")

    if not qc.passed:
        return 1

    # 8. Record in DB
    render_id = insert_render(
        storyboard_hash="martinez_wc2026_v1",
        local_path=str(OUTPUT_PATH),
        duration_secs=qc.measured_duration_secs or 28.0,
        file_size_bytes=qc.file_size_bytes,
        width=qc.measured_width,
        height=qc.measured_height,
        tts_provider="pexels_match",
        qc_passed=qc.passed,
        qc_report=qc.report(),
    )

    print(f"\n✓  Finished: {OUTPUT_PATH}")
    print(f"   Render DB id: {render_id}")
    print(f"\n   Upload when ready:")
    print(f"   python scripts/pipeline.py upload --render-id {render_id} --visibility private")
    return 0


if __name__ == "__main__":
    sys.exit(main())
