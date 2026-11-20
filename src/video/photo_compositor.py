"""
Photo compositor: renders Storyboard scenes as cinematic 1080×1920 frames
using real photographs with Ken Burns motion effects.

Each scene:
  1. Scales the assigned photo to cover-fill 1080×1920 with 20% extra margin
  2. Applies Ken Burns zoom/pan animation across the scene duration
  3. Composites a vignette + channel branding bar (top) + caption bar (bottom)
  4. Draws the narration text as styled captions

Falls back to a gradient if no photo is assigned for a scene.

Branding colours: Navy #0D1B2A / Gold #C9A84C
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from PIL import Image, ImageDraw, ImageFont

from src.research.models import Storyboard, StoryboardScene

W, H = 1080, 1920
FPS = 30

# ── Brand colours ──────────────────────────────────────────────────────────────
_GOLD = (201, 168, 76)
_NAVY = (13, 27, 42)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)

# ── Layout constants (pixels from top) ────────────────────────────────────────
_BRAND_H = 88          # channel branding bar height
_BRAND_ACCENT_Y = 90   # gold accent line below branding
_CAPTION_BAR_TOP = H - 360   # 1560 — dark gradient starts here
_CAPTION_CENTER_Y = H - 170  # 1750 — center of caption text block
_PROGRESS_Y = H - 28         # 1892 — progress bar
_PROGRESS_H = 8

# ── Ken Burns effect specs ─────────────────────────────────────────────────────
# margin: how much larger than 1080×1920 the base photo is scaled to
_MARGIN = 1.22  # 22% extra for zoom/pan headroom


@dataclass
class SceneConfig:
    """Per-scene configuration injected by the caller."""
    photo_path: Path | None = None
    effect: str = "zoom_in"   # zoom_in | zoom_out | pan_right | pan_left | slow_push
    show_hook_text: bool = False   # show large centered hook text (first scene)


# ── Font loader ────────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        if bold else
        [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ── Photo scaling ──────────────────────────────────────────────────────────────

def _scale_to_cover(img: Image.Image, target_w: int, target_h: int, margin: float) -> Image.Image:
    """
    Scale img so it covers (target_w * margin) × (target_h * margin) in cover mode,
    then center-crop to that exact size.
    """
    dest_w = int(target_w * margin)
    dest_h = int(target_h * margin)
    scale = max(dest_w / img.width, dest_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    scaled = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - dest_w) // 2
    top = (new_h - dest_h) // 2
    return scaled.crop((left, top, left + dest_w, top + dest_h))


def _make_gradient_fallback(scene_index: int) -> Image.Image:
    """Dark gradient fallback when no photo is available."""
    shift = scene_index * 12
    top_c = (max(0, 8 - shift), max(0, 20 - shift), min(60 + shift, 100))
    bot_c = (5, 10, 40)
    img = Image.new("RGB", (int(W * _MARGIN), int(H * _MARGIN)))
    pix = img.load()
    bw, bh = img.size
    for y in range(bh):
        t = y / (bh - 1)
        r = int(top_c[0] + (bot_c[0] - top_c[0]) * t)
        g = int(top_c[1] + (bot_c[1] - top_c[1]) * t)
        b = int(top_c[2] + (bot_c[2] - top_c[2]) * t)
        for x in range(bw):
            pix[x, y] = (r, g, b)
    return img


# ── Ken Burns crop calculator ──────────────────────────────────────────────────

def _ken_burns_frame(
    base: Image.Image,  # pre-scaled to W*_MARGIN × H*_MARGIN
    t: float,           # 0.0 → 1.0 within the scene
    effect: str,
) -> Image.Image:
    """Return one 1080×1920 frame with Ken Burns motion applied."""
    bw, bh = base.size

    if effect == "zoom_in":
        # Crop starts large (distant) → ends tight (close)
        crop_w = int(W + (bw - W) * (1.0 - t * 0.85))
        crop_h = int(H + (bh - H) * (1.0 - t * 0.85))
        left = (bw - crop_w) // 2
        top = (bh - crop_h) // 2

    elif effect == "zoom_out":
        # Crop starts tight → ends large
        crop_w = int(W + (bw - W) * (t * 0.85))
        crop_h = int(H + (bh - H) * (t * 0.85))
        left = (bw - crop_w) // 2
        top = (bh - crop_h) // 2

    elif effect == "pan_right":
        # Slide right; slight zoom
        zoom = 0.90
        crop_w = int(W * (1 + (1 - zoom) * 0.5 + 0.05))
        crop_h = int(H * (1 + (1 - zoom) * 0.5 + 0.05))
        crop_w = min(crop_w, bw)
        crop_h = min(crop_h, bh)
        max_left = bw - crop_w
        left = int(max_left * t)
        top = (bh - crop_h) // 2

    elif effect == "pan_left":
        crop_w = int(min(W * 1.08, bw))
        crop_h = int(min(H * 1.08, bh))
        max_left = bw - crop_w
        left = int(max_left * (1.0 - t))
        top = (bh - crop_h) // 2

    else:  # slow_push — subtle zoom in
        crop_w = int(W + (bw - W) * (1.0 - t * 0.5))
        crop_h = int(H + (bh - H) * (1.0 - t * 0.5))
        left = (bw - crop_w) // 2
        top = (bh - crop_h) // 2

    left = max(0, min(left, bw - crop_w))
    top = max(0, min(top, bh - crop_h))
    crop_w = max(1, crop_w)
    crop_h = max(1, crop_h)

    cropped = base.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((W, H), Image.LANCZOS)


# ── Vignette overlay ───────────────────────────────────────────────────────────

def _add_vignette(img: Image.Image) -> Image.Image:
    """Add a subtle dark vignette (darkens edges) for cinematic depth."""
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    # Top dark bar gradient
    for y in range(160):
        alpha = int(180 * (1 - y / 160))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    # Bottom dark gradient (caption area)
    for y in range(_CAPTION_BAR_TOP, H):
        progress = (y - _CAPTION_BAR_TOP) / (H - _CAPTION_BAR_TOP)
        alpha = int(210 * min(progress * 1.5, 1.0))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    result = img.convert("RGBA")
    result = Image.alpha_composite(result, vignette)
    return result.convert("RGB")


# ── Text utilities ─────────────────────────────────────────────────────────────

def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple,
    max_width: int = 940,
    line_spacing: int = 16,
    shadow: bool = True,
    shadow_offset: int = 3,
) -> int:
    """Draw word-wrapped centered text; return y below last line."""
    lines = _wrap_text(text, font, max_width)
    if not lines:
        return center_y

    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)
    heights = [dd.textbbox((0, 0), ln, font=font)[3] - dd.textbbox((0, 0), ln, font=font)[1]
               for ln in lines]
    total_h = sum(heights) + line_spacing * (len(lines) - 1)
    y = center_y - total_h // 2

    for ln, lh in zip(lines, heights):
        bbox = dd.textbbox((0, 0), ln, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2
        if shadow:
            draw.text((x + shadow_offset, y + shadow_offset), ln, font=font,
                      fill=(0, 0, 0, 200) if isinstance(fill, tuple) and len(fill) == 4
                      else _BLACK)
        draw.text((x, y), ln, font=font, fill=fill)
        y += lh + line_spacing
    return y


# ── Frame overlay builder ──────────────────────────────────────────────────────

def _add_overlays(
    photo: Image.Image,
    scene: StoryboardScene,
    storyboard: Storyboard,
    global_progress: float,    # 0.0–1.0 across full video
    is_first_scene: bool,
) -> Image.Image:
    """
    Composite all overlays onto the photo frame:
    branding bar, caption text, hook text (first scene), progress bar.
    """
    img = _add_vignette(photo)
    draw = ImageDraw.Draw(img)

    # ── Channel branding bar (top) ─────────────────────────────────────────────
    channel_name = "BEYOND THE PITCH"
    brand_font = _load_font(36)
    bbox = draw.textbbox((0, 0), channel_name, font=brand_font)
    bw = bbox[2] - bbox[0]
    bx = (W - bw) // 2
    # Shadow
    draw.text((bx + 2, 32), channel_name, font=brand_font, fill=_BLACK)
    # Text
    draw.text((bx, 30), channel_name, font=brand_font, fill=_GOLD)

    # Gold accent line under branding
    draw.rectangle([60, _BRAND_ACCENT_Y, W - 60, _BRAND_ACCENT_Y + 3], fill=_GOLD)

    # ── Hook overlay (first scene only) ───────────────────────────────────────
    if is_first_scene:
        hook_text = storyboard.hook.upper()
        hook_font = _load_font(110, bold=True)
        _draw_centered_text(
            draw, hook_text, center_y=750,
            font=hook_font, fill=_WHITE,
            max_width=960, line_spacing=20, shadow_offset=5,
        )

    # ── Caption text (scene narration) ────────────────────────────────────────
    cap_font = _load_font(54, bold=True)
    _draw_centered_text(
        draw, scene.narration, center_y=_CAPTION_CENTER_Y,
        font=cap_font, fill=_WHITE,
        max_width=940, line_spacing=18, shadow_offset=3,
    )

    # ── Scene counter dot row (top right) ────────────────────────────────────
    total_scenes = len(storyboard.scenes)
    for i in range(total_scenes):
        cx = W - 68 - (total_scenes - 1 - i) * 26
        cy = 50
        is_active = (i == getattr(_add_overlays, "_current_scene_index", 0))
        fill = _GOLD if is_active else (80, 70, 40)
        r = 7 if is_active else 5
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    # ── Progress bar ──────────────────────────────────────────────────────────
    bar_x1 = int(60 + (W - 120) * global_progress)
    # Track
    draw.rectangle([60, _PROGRESS_Y, W - 60, _PROGRESS_Y + _PROGRESS_H],
                   fill=(40, 35, 20))
    # Fill
    draw.rectangle([60, _PROGRESS_Y, bar_x1, _PROGRESS_Y + _PROGRESS_H],
                   fill=_GOLD)
    # Dot at current position
    r = _PROGRESS_H + 2
    draw.ellipse([bar_x1 - r, _PROGRESS_Y - 2, bar_x1 + r, _PROGRESS_Y + _PROGRESS_H + 2],
                 fill=_GOLD)

    return img


# ── Main compositor ────────────────────────────────────────────────────────────

class PhotoCompositor:
    """
    Renders a Storyboard using CC-BY photos with Ken Burns motion effects.

    Pass scene_configs as a list[SceneConfig] aligned with storyboard.scenes.
    If a SceneConfig has no photo_path, or the path does not exist, a dark
    gradient is used for that scene.
    """

    def __init__(
        self,
        storyboard: Storyboard,
        scene_configs: list[SceneConfig],
        fps: int = FPS,
    ) -> None:
        if len(scene_configs) != len(storyboard.scenes):
            raise ValueError(
                f"scene_configs length ({len(scene_configs)}) must match "
                f"storyboard scenes ({len(storyboard.scenes)})"
            )
        self.storyboard = storyboard
        self.scene_configs = scene_configs
        self.fps = fps
        self._base_images: list[Image.Image] = []

    def prepare(self) -> None:
        """Pre-scale photos once. Must be called before generate_frames()."""
        self._base_images = []
        for i, cfg in enumerate(self.scene_configs):
            if cfg.photo_path and Path(cfg.photo_path).exists():
                try:
                    img = Image.open(cfg.photo_path).convert("RGB")
                    base = _scale_to_cover(img, W, H, _MARGIN)
                    self._base_images.append(base)
                except Exception:
                    self._base_images.append(_make_gradient_fallback(i))
            else:
                self._base_images.append(_make_gradient_fallback(i))

    def total_frames(self) -> int:
        return sum(int(s.duration * self.fps) for s in self.storyboard.scenes)

    def generate_frames(self) -> Generator[Image.Image, None, None]:
        """Yield 1080×1920 PIL Images, one per frame at the configured FPS."""
        if not self._base_images:
            self.prepare()

        total = self.total_frames()
        global_frame = 0

        for scene_idx, (scene, cfg, base) in enumerate(
            zip(self.storyboard.scenes, self.scene_configs, self._base_images)
        ):
            # Patch scene index into overlay helper (simple approach)
            _add_overlays._current_scene_index = scene_idx  # type: ignore[attr-defined]

            scene_frames = int(scene.duration * self.fps)
            is_first = scene_idx == 0

            for fi in range(scene_frames):
                t = fi / max(scene_frames - 1, 1)
                g_progress = global_frame / max(total - 1, 1)

                photo = _ken_burns_frame(base, t, cfg.effect)
                frame = _add_overlays(photo, scene, self.storyboard, g_progress, is_first)
                yield frame
                global_frame += 1


# ── Convenience factory ────────────────────────────────────────────────────────

_DEFAULT_EFFECTS = ["zoom_in", "pan_right", "zoom_in", "zoom_out", "slow_push", "zoom_out"]


def build_scene_configs(
    storyboard: Storyboard,
    photo_paths: list[Path | None],
    effects: list[str] | None = None,
) -> list[SceneConfig]:
    """
    Build a list[SceneConfig] from parallel lists of photo paths and effects.
    Lists are zero-padded to match the number of scenes.
    """
    n = len(storyboard.scenes)
    photos = list(photo_paths) + [None] * max(0, n - len(photo_paths))
    effs = (list(effects) if effects else []) + [
        _DEFAULT_EFFECTS[i % len(_DEFAULT_EFFECTS)] for i in range(n)
    ]
    effs = effs[:n]

    return [
        SceneConfig(
            photo_path=photos[i],
            effect=effs[i],
            show_hook_text=(i == 0),
        )
        for i in range(n)
    ]
