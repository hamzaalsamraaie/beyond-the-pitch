"""
Thumbnail generator: extract the most visually compelling frame from a
rendered video and overlay the channel brand + title text.

Frame selection strategy (Phase 5 improvement):
  Instead of always using t=3s, we extract 8 candidate frames spread
  across the video and pick the one with highest "visual energy" —
  measured as the standard deviation of pixel brightness (high variance
  = more contrast = more visually interesting).

Output: 1280×720 JPEG for YouTube thumbnail use.

NOTE on YouTube Shorts thumbnails:
  For Shorts, YouTube auto-selects a thumbnail frame from the video and
  does not reliably show custom thumbnails in the Shorts feed on mobile.
  Setting a custom thumbnail in Studio affects the channel page and
  search results, but not the main Shorts player. The best approach is
  ensuring the video itself opens on a visually strong frame.
"""

from __future__ import annotations

import subprocess
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.core.logger import get_logger

logger = get_logger(__name__)

_THUMB_W = 1280
_THUMB_H = 720
_NAVY = (13, 27, 42)        # #0D1B2A
_GOLD = (201, 168, 76)      # #C9A84C
_WHITE = (255, 255, 255)
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for path in [
        _FONT_DIR / name,
        Path("/Library/Fonts") / name,
        Path("/System/Library/Fonts/Supplemental") / name,
    ]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _extract_frame(video_path: Path, t: float, out_path: Path) -> bool:
    """Extract a single frame at time t (seconds) from video_path."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(t), "-i", str(video_path),
            "-vframes", "1", "-q:v", "2", str(out_path),
        ],
        capture_output=True,
    )
    return result.returncode == 0 and out_path.exists()


def _frame_visual_energy(img_path: Path) -> float:
    """
    Score a frame's visual interest as the std-dev of luma values.
    Higher variance = more contrast = more visually dynamic.
    Returns 0.0 on any error.
    """
    try:
        img = Image.open(str(img_path)).convert("L")  # grayscale
        pixels = list(img.getdata())
        return statistics.stdev(pixels) if len(pixels) > 1 else 0.0
    except Exception:
        return 0.0


def find_best_thumbnail_frame(
    video_path: Path,
    output_dir: Path,
    duration_secs: float = 30.0,
    n_candidates: int = 8,
) -> tuple[float, Path] | None:
    """
    Extract n_candidates frames spread across the video, score each for
    visual energy, and return (best_time_secs, best_frame_path).

    Skips the first 10% and last 5% to avoid fade-in/out frames.
    Returns None if all extractions fail.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start = duration_secs * 0.10
    end = duration_secs * 0.95
    span = end - start

    candidates: list[tuple[float, Path, float]] = []
    for i in range(n_candidates):
        t = start + (span * i / max(n_candidates - 1, 1))
        frame_path = output_dir / f"_thumb_candidate_{i}.jpg"
        if _extract_frame(video_path, t, frame_path):
            energy = _frame_visual_energy(frame_path)
            candidates.append((t, frame_path, energy))

    if not candidates:
        return None

    # Clean up non-winners
    best_t, best_path, best_energy = max(candidates, key=lambda c: c[2])
    for t, path, _ in candidates:
        if path != best_path and path.exists():
            path.unlink()

    logger.debug(
        "thumbnail_frame_selected",
        t=round(best_t, 1),
        energy=round(best_energy, 1),
        n_candidates=len(candidates),
    )
    return best_t, best_path


def generate_thumbnail(
    video_path: Path,
    title: str,
    output_path: Path,
    frame_time: float = 3.0,
    channel_name: str = "BEYOND THE PITCH",
) -> bool:
    """
    Generate a 1280×720 thumbnail from video_path.

    Extracts a frame at frame_time seconds, scales/crops to 1280×720, then
    overlays a navy gradient bar at the bottom with title text in white and
    the channel name in gold.

    Returns True on success.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame_path = output_path.with_suffix(".frame.jpg")

    try:
        ok = _extract_frame(video_path, frame_time, frame_path)
        if not ok:
            logger.warning("thumbnail_frame_extract_failed", video=video_path.name, t=frame_time)
            img = Image.new("RGB", (_THUMB_W, _THUMB_H), _NAVY)
        else:
            img = Image.open(frame_path).convert("RGB")
            # Scale to cover 1280×720, then centre-crop
            src_w, src_h = img.size
            scale = max(_THUMB_W / src_w, _THUMB_H / src_h)
            new_w = int(src_w * scale)
            new_h = int(src_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - _THUMB_W) // 2
            top = (new_h - _THUMB_H) // 2
            img = img.crop((left, top, left + _THUMB_W, top + _THUMB_H))

        draw = ImageDraw.Draw(img)

        # Dark gradient overlay at the bottom third
        overlay = Image.new("RGBA", (_THUMB_W, _THUMB_H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        bar_top = int(_THUMB_H * 0.55)
        for y in range(bar_top, _THUMB_H):
            alpha = int(200 * (y - bar_top) / (_THUMB_H - bar_top))
            ov_draw.line([(0, y), (_THUMB_W, y)], fill=(0, 0, 0, alpha))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Channel name (gold, top-left)
        channel_font = _load_font("Montserrat-ExtraBold.ttf", 28)
        draw.text((40, 32), channel_name, font=channel_font, fill=_GOLD)

        # Main title (white, bottom area)
        title_font = _load_font("Montserrat-ExtraBold.ttf", 72)
        fallback_font = _load_font("BebasNeue-Regular.ttf", 90)

        words = title.upper().split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=title_font)
            if bbox[2] - bbox[0] > _THUMB_W - 80:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        line_height = 90
        total_h = len(lines) * line_height
        y_start = _THUMB_H - total_h - 48

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            # Drop shadow
            draw.text((42, y + 3), line, font=title_font, fill=(0, 0, 0, 180))
            draw.text((40, y), line, font=title_font, fill=_WHITE)

        img.save(str(output_path), "JPEG", quality=90)
        logger.info("thumbnail_saved", path=output_path.name)
        return True

    except Exception as exc:
        logger.error("thumbnail_failed", error=str(exc))
        return False

    finally:
        if frame_path.exists():
            frame_path.unlink()
