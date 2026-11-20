"""
Animated caption renderer using PIL frame-pipe.

Replaces the basic caption_renderer.py for styled, animated captions.

Supported animations per CaptionPreset:
  INSTANT      – text appears/disappears on exact frame
  FADE         – opacity 0→1 (in) and 1→0 (out) over N frames
  POP_SCALE    – scale 1.25→1.0 over N frames on entrance
  SLIDE_UP     – translate from +slide_px→0 over N frames on entrance
  WORD_REVEAL  – each word fades in sequentially

Watermark: "BEYOND THE PITCH" always rendered at top using GOLD,
           38px, Montserrat/Arial Bold. Constant opacity — never animated.

Safe-zone enforcement:
  Top clearance 190px, bottom clearance 380px, side margins 54px.
  Captions are clamped to safe zone automatically.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Generator

from src.core.logger import get_logger
from src.editing.caption_presets import (
    AnimationType, CaptionPreset, Color, DRAMATIC_REVEAL,
    _best_font, _MONTSERRAT, _ARIAL_BOLD,
)

logger = get_logger(__name__)

# ── Layout constants ───────────────────────────────────────────────────────────
W, H = 1080, 1920
SAFE_TOP    = 190     # px — YouTube UI clearance
SAFE_BOTTOM = 380     # px — YouTube seek bar + audio info
SAFE_SIDE   = 54      # px — side margins
WATERMARK_Y = 60      # px from top — BEYOND THE PITCH band
SLIDE_DIST  = 50      # px — SLIDE_UP entrance travel distance


# ── Font cache ────────────────────────────────────────────────────────────────

_font_cache: dict[tuple, object] = {}

def _get_font(path: Path, size: int):
    key = (str(path), size)
    if key not in _font_cache:
        from PIL import ImageFont  # noqa: PLC0415
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


# ── Outline/shadow drawing helper ─────────────────────────────────────────────

def _draw_text_with_outline(
    draw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: tuple,
    outline_color: tuple,
    outline_width: int,
    shadow_offset: tuple = (3, 3),
    shadow_alpha: int = 150,
    alpha: float = 1.0,
) -> None:
    """Draw text with outline + drop shadow, respecting alpha for fades."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    # Scale alpha into color components
    def _apply_alpha(color: tuple, a: float) -> tuple:
        r, g, b = color[:3]
        return (r, g, b, int(255 * a))

    x, y = xy

    # Shadow (draw first so it goes behind)
    sx, sy = shadow_offset
    shadow_fill = _apply_alpha((0, 0, 0), alpha * shadow_alpha / 255)
    for offsets in [(sx + dx, sy + dy) for dx in range(-1, 2) for dy in range(-1, 2)]:
        draw.text((x + offsets[0], y + offsets[1]), text, font=font, fill=shadow_fill)

    # Outline
    out_fill = _apply_alpha(outline_color, alpha)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=out_fill)

    # Main fill
    main_fill = _apply_alpha(fill, alpha)
    draw.text(xy, text, font=font, fill=main_fill)


# ── Event: a single timed caption with its animation state ───────────────────

class CaptionEvent:
    """
    One caption line or word-reveal block.
    Knows its style and can render itself into a PIL Image at any frame.
    """

    def __init__(
        self,
        start: float,
        end: float,
        text: str,
        preset: CaptionPreset,
        fps: float = 30.0,
        is_highlight: bool = False,
    ) -> None:
        self.start      = start
        self.end        = end
        self.text       = text
        self.preset     = preset
        self.fps        = fps
        self.is_highlight = is_highlight

        self._in_frames  = preset.anim_in_frames
        self._out_frames = preset.anim_out_frames
        self._duration   = end - start

    def _progress(self, t: float) -> tuple[float, float]:
        """Return (in_progress 0–1, out_progress 0–1) for time t."""
        elapsed = t - self.start
        total   = self._duration
        # in_progress: how far through entrance anim (0 not started, 1 done)
        in_prog  = min(1.0, elapsed / max(1, self._in_frames / self.fps))
        # out_progress: how far through exit anim (0 not started, 1 done)
        time_to_end = self.end - t
        out_prog = 1.0 - min(1.0, time_to_end / max(1, self._out_frames / self.fps))
        out_prog = max(0.0, out_prog)
        return in_prog, out_prog

    def render_onto(self, frame: "Image.Image", t: float) -> None:
        """Draw this caption onto a PIL Image at time t."""
        if t < self.start or t >= self.end:
            return

        from PIL import Image, ImageDraw  # noqa: PLC0415

        preset  = self.preset
        in_p, out_p = self._progress(t)
        anim    = preset.anim_type

        fill_color = preset.highlight_color if self.is_highlight else preset.text_color
        font       = _get_font(preset.font_path, preset.font_size)

        # Measure text
        draw_tmp = ImageDraw.Draw(Image.new("RGBA", (W, H)))
        bbox     = draw_tmp.textbbox((0, 0), self.text, font=font)
        tw       = bbox[2] - bbox[0]
        th       = bbox[3] - bbox[1]

        # Base position (centered, y_anchor)
        x_base = (W - tw) // 2
        y_base = int(H * preset.y_anchor) - th // 2

        # Clamp to safe zone
        y_base = max(SAFE_TOP, min(H - SAFE_BOTTOM - th, y_base))
        x_base = max(SAFE_SIDE, min(W - SAFE_SIDE - tw, x_base))

        # Compute alpha
        if anim == AnimationType.FADE:
            alpha = in_p * (1.0 - out_p)
        elif anim == AnimationType.INSTANT:
            alpha = 1.0
        elif anim == AnimationType.POP_SCALE:
            alpha = min(1.0, in_p * 2)
        elif anim == AnimationType.SLIDE_UP:
            alpha = min(1.0, in_p * 1.5)
        elif anim == AnimationType.WORD_REVEAL:
            alpha = min(1.0, in_p * 1.5)
        else:
            alpha = 1.0

        alpha = max(0.0, min(1.0, alpha))

        if alpha < 0.01:
            return

        # Compute transform
        if anim == AnimationType.POP_SCALE:
            # Scale from 1.25 → 1.0 during entrance
            scale    = 1.25 - 0.25 * in_p
            new_size = int(preset.font_size * scale)
            new_size = max(10, new_size)
            scaled_font = _get_font(preset.font_path, new_size)
            bbox2    = draw_tmp.textbbox((0, 0), self.text, font=scaled_font)
            tw2      = bbox2[2] - bbox2[0]
            x_draw   = max(SAFE_SIDE, (W - tw2) // 2)
            y_draw   = y_base + (th - (bbox2[3] - bbox2[1])) // 2
            draw     = ImageDraw.Draw(frame, "RGBA")
            _draw_text_with_outline(
                draw, (x_draw, y_draw), self.text, scaled_font,
                fill_color, preset.outline_color, max(2, int(preset.outline_width * scale)),
                preset.shadow_offset, preset.shadow_alpha, alpha,
            )
            return

        if anim == AnimationType.SLIDE_UP:
            slide_offset = int(SLIDE_DIST * (1.0 - in_p))
            y_draw = y_base + slide_offset
            y_draw = min(H - SAFE_BOTTOM - th, y_draw)
        else:
            y_draw = y_base

        draw = ImageDraw.Draw(frame, "RGBA")
        _draw_text_with_outline(
            draw, (x_base, y_draw), self.text, font,
            fill_color, preset.outline_color, preset.outline_width,
            preset.shadow_offset, preset.shadow_alpha, alpha,
        )


class WordRevealEvent:
    """
    DRAMATIC_REVEAL: words appear one by one, final word in gold.
    Each word fades in over anim_in_frames.
    """

    def __init__(
        self,
        start: float,
        end: float,
        text: str,
        preset: CaptionPreset,
        fps: float = 30.0,
    ) -> None:
        self.start  = start
        self.end    = end
        self.preset = preset
        self.fps    = fps
        words       = text.strip().split()
        total_dur   = end - start
        word_dur    = total_dur / max(1, len(words))
        self._words: list[tuple[float, float, str, bool]] = []  # start, end, word, is_last
        for i, w in enumerate(words):
            ws = start + i * word_dur
            we = start + (i + 1) * word_dur
            self._words.append((ws, we, w, i == len(words) - 1))

    def render_onto(self, frame: "Image.Image", t: float) -> None:
        if t < self.start or t >= self.end:
            return
        from PIL import Image, ImageDraw  # noqa: PLC0415

        preset = self.preset
        # Collect all words visible at time t
        visible: list[tuple[str, float, bool]] = []
        for ws, we, w, is_last in self._words:
            if t >= ws:
                fade_in = min(1.0, (t - ws) / max(0.01, preset.anim_in_frames / self.fps))
                visible.append((w, fade_in, is_last))

        if not visible:
            return

        full_text = " ".join(v[0] for v in visible)
        font      = _get_font(preset.font_path, preset.font_size)
        draw_tmp  = ImageDraw.Draw(Image.new("RGBA", (W, H)))

        # Render word by word on same line (simple single-line layout)
        draw = ImageDraw.Draw(frame, "RGBA")
        x_cursor = None
        total_bbox = draw_tmp.textbbox((0, 0), full_text, font=font)
        x_start   = max(SAFE_SIDE, (W - (total_bbox[2] - total_bbox[0])) // 2)
        y_base    = int(H * preset.y_anchor) - (total_bbox[3] - total_bbox[1]) // 2
        y_base    = max(SAFE_TOP, min(H - SAFE_BOTTOM - (total_bbox[3] - total_bbox[1]), y_base))

        x_cursor = x_start
        for word, alpha, is_last in visible:
            fill = preset.highlight_color if is_last else preset.text_color
            wb   = draw_tmp.textbbox((0, 0), word + " ", font=font)
            ww   = wb[2] - wb[0]
            _draw_text_with_outline(
                draw, (x_cursor, y_base), word, font,
                fill, preset.outline_color, preset.outline_width,
                preset.shadow_offset, preset.shadow_alpha, alpha,
            )
            x_cursor += ww


# ── Watermark renderer ────────────────────────────────────────────────────────

def _render_watermark(frame: "Image.Image", text: str = "BEYOND THE PITCH") -> None:
    """Render persistent gold brand watermark at the top safe zone."""
    from PIL import ImageDraw  # noqa: PLC0415
    font_path = _best_font(_MONTSERRAT, _ARIAL_BOLD)
    font      = _get_font(font_path, 36)
    draw_tmp  = ImageDraw.Draw(frame)
    bbox      = draw_tmp.textbbox((0, 0), text, font=font)
    tw        = bbox[2] - bbox[0]
    x         = (W - tw) // 2
    y         = WATERMARK_Y - (bbox[3] - bbox[1]) // 2

    draw = ImageDraw.Draw(frame, "RGBA")
    # Outline
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 220))
    draw.text((x, y), text, font=font, fill=(*Color.GOLD, 255))


# ── Main render function ──────────────────────────────────────────────────────

def build_events(
    story_beats: list[tuple[float, float, str]],
    preset: CaptionPreset,
    fps: float = 30.0,
) -> list:
    """
    Convert story beats (start, end, text) into CaptionEvent / WordRevealEvent objects.
    Hook beat (first 2 events) uses DRAMATIC_REVEAL regardless of preset when
    the preset is BOLD_IMPACT or BEAT_SYNC_FLASH — creates a natural mix.
    """
    events = []
    for i, (start, end, text) in enumerate(story_beats):
        if preset.anim_type == AnimationType.WORD_REVEAL:
            events.append(WordRevealEvent(start, end, text, preset, fps))
        else:
            is_highlight = (i == len(story_beats) - 2 or i == len(story_beats) - 1)
            events.append(CaptionEvent(start, end, text, preset, fps, is_highlight))
    return events


def render_video_with_captions(
    video_path: Path,
    story_beats: list[tuple[float, float, str]],
    output_path: Path,
    preset: CaptionPreset,
    fps: float = 30.0,
    width: int = W,
    height: int = H,
) -> Path:
    """
    Render story_beats as animated captions over video_path using PIL frame-pipe.
    Watermark is always preserved. Returns output_path.
    """
    ff      = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ff or not ffprobe:
        raise EnvironmentError("ffmpeg/ffprobe required")

    # Probe actual video streams to determine fps and audio availability.
    # Width/height are always fixed to Short format (1080×1920) regardless of source
    # resolution to ensure consistent output size and manageable intermediate files.
    probe = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)],
        capture_output=True, text=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    vs = next((s for s in streams if s["codec_type"] == "video"), None)
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    if vs:
        fps_str = vs.get("r_frame_rate", f"{fps}/1")
        fps_n, fps_d = fps_str.split("/")
        fps = float(fps_n) / float(fps_d)
        # width/height remain at the Short defaults (1080×1920) even if the source
        # has different dimensions — the scale filter below resamples to match.

    events     = build_events(story_beats, preset, fps)
    frame_size = width * height * 3

    # Scale input to Short format before frame extraction so PIL always receives
    # 1080×1920 RGB24 frames, keeping intermediate files small regardless of source.
    extract = [
        ff, "-v", "quiet", "-i", str(video_path),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]

    # Build encode command — only map audio when the source has an audio stream
    encode = [
        ff, "-y", "-v", "quiet",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
    ]
    if has_audio:
        encode += ["-i", str(video_path), "-map", "0:v", "-map", "1:a"]
    else:
        encode += ["-map", "0:v"]
    encode += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]
    if has_audio:
        encode += ["-c:a", "copy"]
    encode += ["-movflags", "+faststart", str(output_path)]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("animated_caption_render_start",
                preset=preset.name, beats=len(story_beats),
                anim=preset.anim_type.value, has_audio=has_audio)

    from PIL import Image  # noqa: PLC0415
    n = 0
    with (subprocess.Popen(extract, stdout=subprocess.PIPE) as reader,
          subprocess.Popen(encode, stdin=subprocess.PIPE) as writer):
        while True:
            raw = reader.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            t     = n / fps
            frame = Image.frombytes("RGB", (width, height), raw)
            rgba  = frame.convert("RGBA")

            for ev in events:
                ev.render_onto(rgba, t)
            _render_watermark(rgba)

            rgb_out = rgba.convert("RGB")
            try:
                writer.stdin.write(rgb_out.tobytes())
            except BrokenPipeError:
                break
            n += 1
        try:
            writer.stdin.close()
        except Exception:
            pass
        writer.wait()
        if writer.returncode != 0:
            raise RuntimeError(
                f"Renderer encoder exited with code {writer.returncode} "
                f"after {n} frames — check FFmpeg stderr with -v info"
            )

    if not output_path.exists():
        raise RuntimeError(
            f"Renderer encoder produced no output file after {n} frames"
        )

    logger.info("animated_caption_render_done",
                frames=n, preset=preset.name, output=output_path.name)
    return output_path
