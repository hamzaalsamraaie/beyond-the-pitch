"""
Scene compositor: renders Storyboard scenes into PIL Image frames.

Design for speed:
  - Gradient background is pre-computed ONCE per scene as a PIL Image.
  - Per-scene text overlay is pre-rendered ONCE as an RGBA layer.
  - Both are composited into a single cached `scene_base` image.
  - Each frame only needs to copy scene_base + draw the progress bar.
  - Frames are yielded as PIL Images to be piped directly to FFmpeg
    (no PNG files written to disk).

YouTube Shorts safe zones:
  - Avoid bottom 180px (YouTube controls/title overlay)
  - Avoid right 160px (Shorts action buttons in portrait mode)
  - Headline text: vertically centred in upper-mid zone (rows 300–900)
  - Subtitle text: rows 1050–1250 (clear of bottom UI)
  - Progress bar: row 1660 (safe, inside content area)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from PIL import Image, ImageDraw, ImageFont

from src.research.models import ContentType, Storyboard, StoryboardScene
from src.video.assets import AssetManifest

W, H = 1080, 1920
FPS = 30

# ── Safe-zone constants (pixels from top) ──────────────────────────────────────
_SAFE_TOP = 80
_SAFE_BOTTOM_LIMIT = H - 180      # 1740 — do not place content below this
_PROGRESS_BAR_Y = 1660
_ATTRIBUTION_Y = 1700
_HEADLINE_CENTER_Y = 700          # center of main text block
_SUBTITLE_Y = 1200                # center of subtitle/narration block (below headline)

# ── Color palettes by content type ────────────────────────────────────────────
_PALETTES = {
    ContentType.FOOTBALL_MOMENTS: {
        "bg_top": (5, 5, 25),
        "bg_bottom": (10, 25, 70),
        "accent": (30, 140, 255),
        "headline": (255, 255, 255),
        "subtitle": (200, 220, 255),
        "dim": (100, 120, 180),
        "progress": (30, 140, 255),
    },
    ContentType.PLAYER_STORIES: {
        "bg_top": (15, 5, 25),
        "bg_bottom": (50, 10, 65),
        "accent": (220, 80, 180),
        "headline": (255, 255, 255),
        "subtitle": (255, 200, 240),
        "dim": (140, 100, 150),
        "progress": (220, 80, 180),
    },
    ContentType.FOOTBALL_MOTIVATION: {
        "bg_top": (5, 15, 5),
        "bg_bottom": (10, 48, 10),
        "accent": (255, 200, 0),
        "headline": (255, 255, 255),
        "subtitle": (255, 245, 180),
        "dim": (120, 150, 80),
        "progress": (255, 200, 0),
    },
}
_DEFAULT_PALETTE = _PALETTES[ContentType.FOOTBALL_MOMENTS]


@dataclass
class _SceneCache:
    """Pre-computed static image for one storyboard scene."""
    base: Image.Image    # composited gradient + text, RGB
    scene_index: int


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


# ── Gradient builder ──────────────────────────────────────────────────────────

def _make_gradient(top: tuple, bottom: tuple) -> Image.Image:
    """Build a 1080×1920 vertical gradient image."""
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


# ── Text utilities ─────────────────────────────────────────────────────────────

def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
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


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple,
    max_width: int = 920,
    line_spacing: int = 20,
    shadow_offset: int = 4,
    shadow_fill: tuple = (0, 0, 0),
) -> int:
    """
    Draw word-wrapped centered text. Returns the y coordinate below the last line.
    """
    lines = _wrap_text(text, font, max_width)
    if not lines:
        return center_y

    dummy = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy)
    line_heights = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    y = center_y - total_h // 2

    for line, lh in zip(lines, line_heights):
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2
        # Shadow
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=shadow_fill)
        # Main text
        draw.text((x, y), line, font=font, fill=fill)
        y += lh + line_spacing

    return y


# ── Scene pre-renderer ─────────────────────────────────────────────────────────

def _build_scene_base(
    scene: StoryboardScene,
    scene_index: int,
    storyboard: Storyboard,
    palette: dict,
    manifest: AssetManifest,
    is_first_scene: bool,
) -> Image.Image:
    """
    Build the static base image for one scene (gradient + text, no progress bar).
    Returned image is RGB, 1080×1920.
    """
    # Slight per-scene color variation to signal scene changes
    shift = scene_index * 8
    bg_top = tuple(min(c + shift, 40) for c in palette["bg_top"])
    bg_bottom = tuple(min(c + shift, 100) for c in palette["bg_bottom"])
    img = _make_gradient(bg_top, bg_bottom)
    draw = ImageDraw.Draw(img)

    accent = palette["accent"]
    dim = palette["dim"]

    # ── Channel branding (top center) ──────────────────────────────────────────
    brand_font = _load_font(34)
    brand_text = "BEYOND THE PITCH"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    bw = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2 + 2, 54), brand_text, font=brand_font, fill=(0, 0, 0))
    draw.text(((W - bw) // 2, 52), brand_text, font=brand_font, fill=(*dim, ))

    # ── Top accent line ────────────────────────────────────────────────────────
    draw.rectangle([80, 115, W - 80, 118], fill=accent)

    # ── Main headline (hook for first scene, on_screen_text for others) ────────
    if is_first_scene:
        headline = storyboard.hook.upper()
    else:
        headline = scene.on_screen_text.upper()

    headline_font = _load_font(130, bold=True)
    bottom_of_headline = _draw_text_centered(
        draw, headline, _HEADLINE_CENTER_Y,
        font=headline_font, fill=palette["headline"],
        max_width=920, line_spacing=24, shadow_offset=5,
    )

    # ── Accent line under headline ─────────────────────────────────────────────
    accent_line_y = bottom_of_headline + 24
    draw.rectangle([W // 2 - 180, accent_line_y, W // 2 + 180, accent_line_y + 6], fill=accent)

    # ── Narration subtitle (full text, word-wrapped — no truncation) ──────────
    # Always shows scene.narration so the on-screen text matches the spoken words.
    sub_font = _load_font(52, bold=False)
    _draw_text_centered(
        draw, scene.narration, _SUBTITLE_Y,
        font=sub_font, fill=palette["subtitle"],
        max_width=860, line_spacing=18, shadow_offset=3,
    )

    # ── Scene dot indicator (top right) ───────────────────────────────────────
    for i in range(len(storyboard.scenes)):
        cx = W - 80 - (len(storyboard.scenes) - 1 - i) * 28
        cy = 55
        fill = accent if i == scene_index else dim
        r = 7 if i == scene_index else 5
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    # ── Attribution (very small, bottom area but above safe limit) ────────────
    if scene.source_indices and storyboard.research_items:
        idx = scene.source_indices[0]
        if 0 <= idx < len(storyboard.research_items):
            source_title = storyboard.research_items[idx].source.title
            attr_font = _load_font(26)
            attr_text = f"Source: {source_title}"
            bbox = draw.textbbox((0, 0), attr_text, font=attr_font)
            aw = bbox[2] - bbox[0]
            draw.text(((W - aw) // 2, _ATTRIBUTION_Y), attr_text, font=attr_font, fill=dim)

    return img


# ── Main compositor class ──────────────────────────────────────────────────────

class VideoCompositor:
    def __init__(
        self,
        storyboard: Storyboard,
        fps: int = FPS,
        manifest: AssetManifest | None = None,
    ) -> None:
        self.storyboard = storyboard
        self.fps = fps
        self._manifest = manifest or AssetManifest()
        self._palette = _PALETTES.get(storyboard.content_type, _DEFAULT_PALETTE)
        self._scene_caches: list[_SceneCache] | None = None

    def prepare(self) -> None:
        """Pre-compute one base image per scene. Call once before generate_frames."""
        self._scene_caches = []
        for i, scene in enumerate(self.storyboard.scenes):
            base = _build_scene_base(
                scene=scene,
                scene_index=i,
                storyboard=self.storyboard,
                palette=self._palette,
                manifest=self._manifest,
                is_first_scene=(i == 0),
            )
            self._scene_caches.append(_SceneCache(base=base, scene_index=i))

    def total_frames(self) -> int:
        return sum(
            int(scene.duration * self.fps)
            for scene in self.storyboard.scenes
        )

    def generate_frames(self) -> Generator[Image.Image, None, None]:
        """
        Yield PIL Image frames for the entire storyboard.
        Call prepare() first.
        """
        if self._scene_caches is None:
            self.prepare()

        total = self.total_frames()
        global_frame = 0
        accent = self._palette["progress"]

        for cache, scene in zip(self._scene_caches, self.storyboard.scenes):
            scene_frames = int(scene.duration * self.fps)
            for _ in range(scene_frames):
                frame = cache.base.copy()
                # Progress bar: fills left→right across the whole video
                progress = global_frame / max(total - 1, 1)
                draw = ImageDraw.Draw(frame)
                bar_x1 = int(80 + (W - 160) * progress)
                draw.rectangle([80, _PROGRESS_BAR_Y, W - 80, _PROGRESS_BAR_Y + 7], fill=(30, 30, 50))
                draw.rectangle([80, _PROGRESS_BAR_Y, bar_x1, _PROGRESS_BAR_Y + 7], fill=accent)
                yield frame
                global_frame += 1
