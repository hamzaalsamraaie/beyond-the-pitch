"""
Phase 1 — Test video generator.

Produces a self-contained 1080×1920 vertical Short using only Pillow and FFmpeg.
No external footage, music, or API calls required.

Usage:
    python -m src.video.test_generator
    python -m src.video.test_generator --title "Messi's Greatest Goal" --duration 30
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from src.core.database import init_db, insert_video, script_hash_exists
from src.core.kill_switch import require_clear
from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 1080, 1920
FPS = 30
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


@dataclass
class Scene:
    text: str
    subtitle: str
    duration_secs: float
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    accent: tuple[int, int, int] = field(default=(255, 200, 0))


# ── Colour palette ─────────────────────────────────────────────────────────────
SCENES: list[Scene] = [
    Scene(
        text="THE STORY\nBEGINS",
        subtitle="Football. Passion. Legacy.",
        duration_secs=5.0,
        bg_top=(10, 10, 40),
        bg_bottom=(30, 60, 120),
        accent=(100, 160, 255),
    ),
    Scene(
        text="FROM\nNOTHING",
        subtitle="A kid with a dream and a battered ball.",
        duration_secs=7.0,
        bg_top=(20, 10, 10),
        bg_bottom=(100, 30, 20),
        accent=(255, 100, 60),
    ),
    Scene(
        text="TO THE\nWORLD\nSTAGE",
        subtitle="One moment that changed everything.",
        duration_secs=8.0,
        bg_top=(5, 30, 10),
        bg_bottom=(10, 90, 40),
        accent=(80, 220, 120),
    ),
    Scene(
        text="THE\nLEGACY\nLIVES",
        subtitle="Subscribe for more football stories.",
        duration_secs=10.0,
        bg_top=(20, 10, 40),
        bg_bottom=(60, 20, 80),
        accent=(200, 120, 255),
    ),
]


# ── Frame rendering ────────────────────────────────────────────────────────────

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Try a few system fonts available on macOS; fall back to default.
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _vertical_gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    pixels = img.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(W):
            pixels[x, y] = (r, g, b)
    return img


def _draw_scene_frame(
    scene: Scene,
    frame_idx: int,
    total_frames: int,
) -> Image.Image:
    img = _vertical_gradient(scene.bg_top, scene.bg_bottom)
    draw = ImageDraw.Draw(img)

    # Animated accent bar — slides up over the scene duration
    progress = frame_idx / max(total_frames - 1, 1)
    bar_height = int(H * 0.006)
    bar_y = int(H * 0.85 - H * 0.1 * progress)
    bar_x0 = int(W * 0.08)
    bar_x1 = int(W * 0.08 + W * 0.84 * progress)
    draw.rectangle([bar_x0, bar_y, bar_x1, bar_y + bar_height], fill=scene.accent)

    # Main headline
    font_main = _load_font(130)
    lines = scene.text.split("\n")
    total_text_h = len(lines) * 150
    start_y = H // 2 - total_text_h // 2 - 60
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2
        y = start_y + i * 155
        # Shadow
        draw.text((x + 4, y + 4), line, font=font_main, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font_main, fill=(255, 255, 255))

    # Accent line under headline
    underline_y = start_y + len(lines) * 155 + 10
    draw.rectangle(
        [W // 2 - 160, underline_y, W // 2 + 160, underline_y + 7],
        fill=scene.accent,
    )

    # Subtitle
    font_sub = _load_font(52)
    sub_bbox = draw.textbbox((0, 0), scene.subtitle, font=font_sub)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_x = (W - sub_w) // 2
    sub_y = underline_y + 36
    draw.text((sub_x + 2, sub_y + 2), scene.subtitle, font=font_sub, fill=(0, 0, 0, 120))
    draw.text((sub_x, sub_y), scene.subtitle, font=font_sub, fill=(220, 220, 220))

    # Watermark / channel label
    font_wm = _load_font(36)
    wm = "⚽  FOOTBALL STORIES"
    wm_bbox = draw.textbbox((0, 0), wm, font=font_wm)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        ((W - wm_w) // 2, H - 110),
        wm,
        font=font_wm,
        fill=(*scene.accent, 200),
    )

    # Frame counter (dev overlay, bottom-left)
    font_dev = _load_font(28)
    draw.text((30, H - 68), f"frame {frame_idx + 1}", font=font_dev, fill=(180, 180, 180))

    return img


def render_frames(scenes: list[Scene], frame_dir: Path) -> int:
    frame_dir.mkdir(parents=True, exist_ok=True)
    global_frame = 0
    for scene_idx, scene in enumerate(scenes):
        total = int(scene.duration_secs * FPS)
        logger.info("rendering_scene", scene=scene_idx + 1, frames=total, text=scene.text[:20])
        for f in range(total):
            img = _draw_scene_frame(scene, f, total)
            img.save(frame_dir / f"frame_{global_frame:06d}.png")
            global_frame += 1
    return global_frame


# ── FFmpeg assembly ────────────────────────────────────────────────────────────

def assemble_video(frame_dir: Path, output_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise EnvironmentError("ffmpeg not found on PATH — run: brew install ffmpeg")

    cmd = [
        ffmpeg,
        "-y",
        "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%06d.png"),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info("ffmpeg_start", output=str(output_path))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg_failed", stderr=result.stderr[-800:])
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-800:]}")
    logger.info("ffmpeg_done", output=str(output_path))


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_test_short(
    title: str = "Football Stories — Test Short",
    topic: str = "test",
    scenes: Sequence[Scene] | None = None,
) -> Path:
    require_clear("generate_test_short")
    configure_logging()
    init_db()

    active_scenes = list(scenes) if scenes else SCENES
    duration = sum(s.duration_secs for s in active_scenes)

    # Dedup check: hash the scene text as a lightweight "script fingerprint"
    fingerprint = hashlib.sha256(
        "|".join(s.text + s.subtitle for s in active_scenes).encode()
    ).hexdigest()
    if script_hash_exists(fingerprint):
        raise ValueError(
            f"A video with this script already exists (hash {fingerprint[:12]}). "
            "Change the scene content to avoid duplicates."
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = title.lower().replace(" ", "_")[:40]
    output_path = OUTPUT_DIR / f"{slug}.mp4"

    with tempfile.TemporaryDirectory(prefix="fs_frames_") as tmp:
        frame_dir = Path(tmp)
        total_frames = render_frames(active_scenes, frame_dir)
        logger.info("frames_rendered", total=total_frames)
        assemble_video(frame_dir, output_path)

    video_id = insert_video(
        title=title,
        topic=topic,
        script_hash=fingerprint,
        local_path=str(output_path),
        duration_secs=duration,
        status="ready_for_review",
    )
    logger.info("video_saved", video_id=video_id, path=str(output_path))
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a Phase 1 test Short")
    p.add_argument("--title", default="Football Stories — Test Short")
    p.add_argument("--topic", default="test")
    p.add_argument("--duration", type=float, default=None,
                   help="Override total duration by scaling scene lengths")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    scenes = SCENES
    if args.duration:
        total = sum(s.duration_secs for s in scenes)
        ratio = args.duration / total
        scenes = [
            Scene(
                text=s.text,
                subtitle=s.subtitle,
                duration_secs=round(s.duration_secs * ratio, 2),
                bg_top=s.bg_top,
                bg_bottom=s.bg_bottom,
                accent=s.accent,
            )
            for s in scenes
        ]
    path = generate_test_short(title=args.title, topic=args.topic, scenes=scenes)
    print(f"\nTest Short written to: {path}")
    print("Open it in QuickTime to verify 1080×1920 vertical format.")
