"""
Contact sheet generator.

Extracts frames from an MP4 at specified timestamps and arranges them
in a grid image for visual design review.

Usage:
    from src.video.contact_sheet import make_contact_sheet
    path = make_contact_sheet(video, [0.5, 3.5, 7.5, 13.5, 21.0, 27.0], out)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def make_contact_sheet(
    video_path: Path,
    timestamps: list[float],
    output_path: Path,
    thumb_w: int = 360,
    thumb_h: int = 640,
    cols: int = 3,
    padding: int = 12,
    label_height: int = 24,
    bg_color: tuple = (18, 18, 28),
    label_color: tuple = (190, 190, 210),
) -> Path:
    """
    Extract frames at given timestamps and lay them out in a grid.

    Args:
        video_path:   Source MP4 file.
        timestamps:   Timestamps in seconds at which to extract frames.
        output_path:  Where to write the JPEG contact sheet.
        thumb_w/h:    Thumbnail dimensions (pixels). Defaults give 1:2.67 aspect.
        cols:         Columns in the grid.
        padding:      Gap (pixels) between cells and around the border.
        label_height: Height reserved below each thumbnail for timestamp label.
        bg_color:     Background color (R, G, B).
        label_color:  Timestamp text color.

    Returns:
        output_path (for chaining).
    """
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("ffmpeg not found on PATH")

    frames: list[tuple[float, Image.Image]] = []

    with tempfile.TemporaryDirectory(prefix="btp_contact_") as tmp:
        for ts in timestamps:
            frame_file = Path(tmp) / f"frame_{ts:.2f}.jpg"
            result = subprocess.run(
                [
                    shutil.which("ffmpeg"), "-y",
                    "-ss", f"{ts:.3f}",
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-vf", f"scale={thumb_w}:{thumb_h}",
                    str(frame_file),
                ],
                capture_output=True,
            )
            if result.returncode != 0 or not frame_file.exists():
                # Insert a blank placeholder so grid alignment is preserved
                blank = Image.new("RGB", (thumb_w, thumb_h), (40, 40, 60))
                _draw_placeholder(blank, f"[{ts:.1f}s — no frame]")
                frames.append((ts, blank))
            else:
                frames.append((ts, Image.open(frame_file).convert("RGB")))

    rows = (len(frames) + cols - 1) // cols
    cell_h = thumb_h + label_height
    sheet_w = cols * thumb_w + (cols + 1) * padding
    sheet_h = rows * cell_h + (rows + 1) * padding

    sheet = Image.new("RGB", (sheet_w, sheet_h), bg_color)
    draw = ImageDraw.Draw(sheet)
    font = _small_font(label_height - 6)

    for idx, (ts, frame) in enumerate(frames):
        row = idx // cols
        col = idx % cols
        x = padding + col * (thumb_w + padding)
        y = padding + row * (cell_h + padding)
        sheet.paste(frame, (x, y))
        label = f"  {ts:.1f}s"
        draw.text((x, y + thumb_h + 3), label, font=font, fill=label_color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(output_path), format="JPEG", quality=90)
    return output_path


def _draw_placeholder(img: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(img)
    draw.text((10, img.height // 2 - 10), text, fill=(120, 120, 140))


def _small_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()
