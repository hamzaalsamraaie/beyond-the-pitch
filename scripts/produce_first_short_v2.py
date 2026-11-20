#!/usr/bin/env python3
"""
Produce the revised Beyond The Pitch Short using the new animated caption system.

Changes from v1:
  - ASS subtitle burn replaced by animated PIL frame-pipe renderer
  - DRAMATIC_REVEAL preset (word-by-word fade, final word in gold)
  - Beat detection → story beats snapped to crowd-noise pulse grid
  - Auto-selected via style_selector (worldcup / dramatic)
  - Watermark: "BEYOND THE PITCH" in gold at top, constant opacity

Disk strategy: writes large intermediates to output/shorts/_work/ and deletes
each after the next step succeeds — avoids saturating the small /tmp volume.

Output: output/shorts/martinez_world_cup_v2.mp4
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
from src.editing.beat_detector import detect_beats
from src.editing.renderer import render_video_with_captions
from src.editing.style_selector import select_caption_preset, assign_story_beats_to_beats
from src.footage.catalog import FootageCatalog
from src.footage.gate import FootageGate, FootageGateError
from src.video.quality_control import run_qc

configure_logging()
logger = get_logger("produce_first_short_v2")

PEXELS_ID        = "d437f9d3-9a6d-4c48-93dd-38a58ee242c8"
PIXABAY_CROWD_ID = "caace90c-8160-42e3-95f1-6a6c0e78f824"
OUTPUT_PATH      = _ROOT / "output" / "shorts" / "martinez_world_cup_v2.mp4"
WORK_DIR         = _ROOT / "output" / "shorts" / "_work"
DURATION_SECS    = 28.0

STORY_BEATS = [
    # Hook — record fact first (confirmed: Wikipedia, Sofascore)
    (0.0,  2.2,  "11 saves."),
    (2.2,  4.5,  "Still not enough."),
    # Context
    (4.5,  7.5,  "2026 World Cup Final"),
    (7.5,  10.5, "Argentina vs Spain"),
    # Stat bomb — Wikipedia: "Argentina failed to register a single shot in regulation
    #              time, a first for a World Cup final."
    (10.5, 14.5, "Argentina. Zero shots."),
    (14.5, 17.5, "In all of regulation."),
    # Climax — Torres 106' confirmed by Wikipedia, ESPN, BBC
    (17.5, 21.0, "Torres. 106th minute."),
    # Result
    (21.0, 24.5, "Spain 1 — Argentina 0."),
    # Payoff (two quick beats for punchy close)
    (24.5, 26.5, "Martínez was perfect."),
    (26.5, 28.0, "Football was not."),
]


def _probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)


def _transcode_to_1080p(src: Path, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", "scale=1080:1920",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            str(dst),
        ],
        capture_output=True, check=True,
    )
    logger.info("transcoded_to_1080p", output=dst.name)


def _add_crowd_audio(video: Path, crowd_src: Path, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video), "-i", str(crowd_src),
            "-filter_complex",
            f"[1:a]volume=-18dB,atrim=0:{DURATION_SECS},asetpts=PTS-STARTPTS[crowd];"
            "[crowd]aresample=48000[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(dst),
        ],
        capture_output=True, check=True,
    )
    logger.info("crowd_audio_added", output=dst.name)


def _normalise_in_place(path: Path) -> None:
    """Apply loudnorm in single-pass linear mode; replace path atomically."""
    tmp = path.with_suffix(".norm_tmp.mp4")
    ff = shutil.which("ffmpeg")
    cmd = [
        ff, "-y", "-i", str(path),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        str(tmp),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"loudnorm failed: {result.stderr[-300:]}")
    path.unlink()
    tmp.rename(path)
    logger.info("audio_normalise_done", output=path.name)


def main() -> int:
    init_db()

    # ── 1. Footage gate ───────────────────────────────────────────────────────
    catalog = FootageCatalog()
    gate    = FootageGate(catalog)
    try:
        gate.check_all([PEXELS_ID])
    except FootageGateError as exc:
        print(f"GATE BLOCKED: {exc}")
        return 1
    print("✓ Footage gate passed")

    pexels_asset  = catalog.get_asset(PEXELS_ID)
    pixabay_asset = catalog.get_asset(PIXABAY_CROWD_ID)
    pexels_path   = Path(pexels_asset.local_path)
    crowd_path    = Path(pixabay_asset.local_path)

    if not pexels_path.exists():
        print(f"ERROR: footage not found at {pexels_path}")
        return 1

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── 2. Auto-select caption preset ────────────────────────────────────────
    preset = select_caption_preset(
        story_type="worldcup",
        mood="dramatic",
        has_speech=False,
        duration_secs=DURATION_SECS,
    )
    print(f"✓ Caption preset selected: {preset.name}")

    # ── 3. Transcode to 1080×1920 ─────────────────────────────────────────
    print("⟳  Transcoding to 1080×1920…")
    vid_1080 = WORK_DIR / "vid_1080.mp4"
    _transcode_to_1080p(pexels_path, vid_1080)

    # ── 4. Add crowd atmosphere audio (then delete the silent copy) ───────
    print("⟳  Adding crowd atmosphere…")
    vid_audio = WORK_DIR / "vid_audio.mp4"
    try:
        _add_crowd_audio(vid_1080, crowd_path, vid_audio)
    except subprocess.CalledProcessError:
        print("   WARNING: crowd audio failed — using silent audio")
        ff = shutil.which("ffmpeg")
        subprocess.run(
            [ff, "-y", "-i", str(vid_1080),
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
             str(vid_audio)],
            capture_output=True, check=True,
        )
    vid_1080.unlink()   # free space immediately

    # ── 5. Beat-sync story beats to crowd rhythm ───────────────────────────
    print("⟳  Detecting beats and snapping story timing…")
    beats, bpm = detect_beats(vid_audio)
    print(f"   Detected BPM: {bpm:.1f}, beats: {len(beats)}")
    snapped_beats = assign_story_beats_to_beats(STORY_BEATS, beats, snap_window=0.15)

    # ── 6. Render animated captions via PIL frame-pipe ─────────────────────
    print(f"⟳  Rendering animated captions ({preset.name}) + watermark…")
    render_video_with_captions(
        video_path  = vid_audio,
        story_beats = snapped_beats,
        output_path = OUTPUT_PATH,
        preset      = preset,
    )
    vid_audio.unlink()  # free space immediately

    # ── 7. LUFS normalise in-place ─────────────────────────────────────────
    print("⟳  Normalising audio…")
    _normalise_in_place(OUTPUT_PATH)

    # ── 8. QC ─────────────────────────────────────────────────────────────
    qc = run_qc(OUTPUT_PATH, expected_duration_secs=DURATION_SECS, tts_provider="pexels_match")
    print(f"\n{'✓' if qc.passed else '✗'}  QC: {qc.report()}")

    # Clean up work dir
    shutil.rmtree(WORK_DIR, ignore_errors=True)

    if not qc.passed:
        return 1

    # ── 9. Record in DB ────────────────────────────────────────────────────
    stat = OUTPUT_PATH.stat()
    render_id = insert_render(
        storyboard_hash = "martinez_wc2026_v2_dramatic_reveal",
        local_path      = str(OUTPUT_PATH),
        duration_secs   = DURATION_SECS,
        file_size_bytes = stat.st_size,
        width           = 1080,
        height          = 1920,
        tts_provider    = "none",
        qc_passed       = True,
        qc_report       = qc.report(),
    )
    print(f"✓ Render recorded (id={render_id})")
    print(f"\nOutput: {OUTPUT_PATH}")
    print("\n── Sound recommendation ──────────────────────────────────────")
    print('Add "Goals" (Lisa, Anitta & Rema) or "NO BATIDÃO" via YouTube')
    print("Shorts audio picker before publishing. Do NOT embed externally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
