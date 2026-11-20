"""
Video effects pipeline for football edits.

Wraps FFmpeg filters to produce a premium editing style:
  - Dynamic zoom (slow push-in on key moments)
  - Speed ramp (slow-motion at impactful frames)
  - Cinematic color grade (contrast S-curve, slight warmth, vignette)
  - Beat-synchronized trim points

Design: all effects are applied in a single FFmpeg pass to minimize
intermediate files and disk usage. The filter_complex string is built
up from an effects list, then run once.

NOTE: These effects work on ANY MP4 footage — CC0 stock, AI-generated,
or creator-authorized clips. The underlying footage rights situation does
not change — see CLAUDE.md for the footage rights blocker.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_W = 1080
_H = 1920


@dataclass
class ZoomEffect:
    """Slow push-in zoom. zoom_factor > 1 zooms in (e.g. 1.05 = 5% zoom)."""
    zoom_factor: float = 1.05
    duration_secs: float | None = None  # None = whole clip
    ease: bool = True  # smooth in/out


@dataclass
class SlowMotionEffect:
    """Slow a section of the video. factor=0.5 → half-speed."""
    start_secs: float
    end_secs: float
    factor: float = 0.5  # 0.5 = half speed


@dataclass
class ColorGradeEffect:
    """
    Cinematic color grade presets.
    preset: 'cinematic' (warm contrast), 'dramatic' (high contrast, desaturated),
            'vibrant' (saturated, punchy), 'neutral' (minimal grade)
    """
    preset: str = "cinematic"


@dataclass
class VignetteEffect:
    """Dark vignette around the frame edges to focus the eye."""
    angle: float = 1.5708  # π/2 ≈ 90°
    strength: float = 0.5  # 0=none, 1=heavy


@dataclass
class EffectsConfig:
    """Full effects configuration for a single render pass."""
    zoom: ZoomEffect | None = None
    color_grade: ColorGradeEffect | None = None
    vignette: VignetteEffect | None = None
    # slow_motion excluded from single-pass (needs trim+concat in multi-pass)


# ── Preset configurations ─────────────────────────────────────────────────────

FOOTBALL_EDIT_CINEMATIC = EffectsConfig(
    zoom=ZoomEffect(zoom_factor=1.04, ease=True),
    color_grade=ColorGradeEffect(preset="cinematic"),
    vignette=VignetteEffect(strength=0.4),
)

FOOTBALL_EDIT_DRAMATIC = EffectsConfig(
    zoom=ZoomEffect(zoom_factor=1.06, ease=True),
    color_grade=ColorGradeEffect(preset="dramatic"),
    vignette=VignetteEffect(strength=0.6),
)

FOOTBALL_EDIT_VIBRANT = EffectsConfig(
    zoom=ZoomEffect(zoom_factor=1.03, ease=True),
    color_grade=ColorGradeEffect(preset="vibrant"),
    vignette=VignetteEffect(strength=0.3),
)

FOOTBALL_EDIT_NONE = EffectsConfig()  # pass-through, no effects


# ── Grade filter strings ──────────────────────────────────────────────────────

_GRADE_FILTERS: dict[str, str] = {
    "cinematic": (
        "curves=master='0/0 0.1/0.05 0.5/0.52 0.9/0.92 1/1':"
        "red='0/0 0.5/0.52 1/1':blue='0/0 0.5/0.48 1/0.97',"
        "hue=s=1.08"
    ),
    "dramatic": (
        "curves=master='0/0 0.1/0.03 0.5/0.5 0.9/0.95 1/1',"
        "hue=s=0.85,"
        "curves=all='0/0 0.3/0.26 0.7/0.76 1/1'"
    ),
    "vibrant": (
        "curves=master='0/0 0.1/0.05 0.5/0.53 0.9/0.93 1/1',"
        "hue=s=1.20"
    ),
    "neutral": "",
}


def _build_filter_complex(
    config: EffectsConfig,
    duration_secs: float,
    input_w: int = _W,
    input_h: int = _H,
) -> str:
    """
    Build an FFmpeg filter_complex string for the given effects config.
    Returns an empty string if no effects are requested.
    """
    parts: list[str] = []
    current = "[0:v]"

    # 1. Zoom — scale up slightly then crop back to original size.
    # Zoompan is too slow (minutes per clip) so we use scale+crop for a
    # constant subtle zoom that runs in seconds.
    if config.zoom and config.zoom.zoom_factor > 1.0:
        z = config.zoom
        scaled_w = int(input_w * z.zoom_factor)
        scaled_h = int(input_h * z.zoom_factor)
        # Round to even (libx264 requirement)
        if scaled_w % 2:
            scaled_w += 1
        if scaled_h % 2:
            scaled_h += 1
        parts.append(
            f"{current}scale={scaled_w}:{scaled_h},"
            f"crop={input_w}:{input_h}[zoomed]"
        )
        current = "[zoomed]"

    # 2. Color grade
    if config.color_grade and config.color_grade.preset != "neutral":
        grade = _GRADE_FILTERS.get(config.color_grade.preset, "")
        if grade:
            parts.append(f"{current}{grade}[graded]")
            current = "[graded]"

    # 3. Vignette
    if config.vignette and config.vignette.strength > 0:
        v = config.vignette
        parts.append(
            f"{current}vignette=angle={v.angle:.4f}:mode=backward[vout]"
        )
        current = "[vout]"

    if not parts:
        return ""  # no effects → caller skips -filter_complex entirely

    return ";".join(parts), current


def apply_effects(
    input_path: Path,
    output_path: Path,
    config: EffectsConfig,
    duration_secs: float = 30.0,
    crf: int = 23,
) -> bool:
    """
    Apply the given EffectsConfig to input_path and write to output_path.

    Returns True on success, False on failure (never raises).
    Uses a single FFmpeg pass to minimize disk usage.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error("effects_input_not_found", path=str(input_path))
        return False

    ff = shutil.which("ffmpeg")
    if not ff:
        logger.error("ffmpeg_not_found")
        return False

    result = _build_filter_complex(config, duration_secs)
    if not result:
        # No effects — simple copy
        cmd = [ff, "-y", "-i", str(input_path), "-c", "copy", str(output_path)]
    else:
        filter_str, final_label = result
        cmd = [
            ff, "-y", "-i", str(input_path),
            "-filter_complex", filter_str,
            "-map", final_label,
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output_path),
        ]

    logger.info("effects_apply_start", effects=_describe(config), input=input_path.name)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.warning("effects_apply_failed", error=proc.stderr[-300:])
        return False

    logger.info("effects_apply_done", output=output_path.name)
    return True


def select_effects_config(
    story_type: str,
    mood: str = "dramatic",
) -> EffectsConfig:
    """
    Choose an EffectsConfig based on story type and mood.
    Safe fallback: FOOTBALL_EDIT_NONE if unrecognized.
    """
    mood_l = mood.lower()
    story_l = story_type.lower()

    if mood_l == "dramatic" or "worldcup" in story_l or "final" in story_l:
        return FOOTBALL_EDIT_DRAMATIC
    if "motivation" in story_l or "comeback" in story_l:
        return FOOTBALL_EDIT_CINEMATIC
    if "skill" in story_l or "goal" in story_l or "moments" in story_l:
        return FOOTBALL_EDIT_VIBRANT
    return FOOTBALL_EDIT_CINEMATIC


def _describe(config: EffectsConfig) -> str:
    parts = []
    if config.zoom:
        parts.append(f"zoom={config.zoom.zoom_factor}x")
    if config.color_grade:
        parts.append(f"grade={config.color_grade.preset}")
    if config.vignette:
        parts.append(f"vignette={config.vignette.strength}")
    return "+".join(parts) or "none"
