"""
Caption style presets for Beyond The Pitch Shorts.

Five research-backed presets covering the dominant YouTube Shorts/football-edit
typography trends. Each preset is a dataclass that fully specifies:

  - font, size, weight, colour
  - outline thickness and shadow
  - vertical position (safe zone)
  - animation type and duration

Safe-zone constants (1080×1920 canvas):
  Top clearance  : 190 px  (YouTube UI: avatar, subscribe, reaction buttons)
  Bottom clear   : 380 px  (YouTube UI: seek bar, sound info)
  Side margins   : 54 px each
  Watermark zone : top 60 px (BEYOND THE PITCH stays here — never overlap)

Animation types:
  POP_SCALE   – appears at 1.25× scale, snaps to 1.0× over pop_frames
  FADE        – opacity 0→1 over fade_frames
  SLIDE_UP    – translates from +slide_px below over slide_frames
  INSTANT     – no transition, appears on exact frame
  WORD_REVEAL – each word fades in sequentially (uses internal per-word timing)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_BEBAS = _FONT_DIR / "BebasNeue-Regular.ttf"
_MONTSERRAT = _FONT_DIR / "Montserrat-ExtraBold.ttf"
_ARIAL_BOLD = Path("/Library/Fonts/Arial Bold.ttf")


def _best_font(*candidates: Path) -> Path:
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"None of {candidates} found — run: make fonts")


# ── Colours ──────────────────────────────────────────────────────────────────

class Color:
    WHITE       = (255, 255, 255)
    GOLD        = (201, 168,  76)   # Beyond The Pitch brand gold #C9A84C
    BLACK       = (  0,   0,   0)
    RED_HOT     = (255,  48,  48)
    CREAM       = (255, 248, 220)
    SHADOW_SEMI = (  0,   0,   0, 160)  # RGBA semi-transparent


# ── Animation types ───────────────────────────────────────────────────────────

class AnimationType(str, Enum):
    INSTANT      = "instant"
    FADE         = "fade"
    POP_SCALE    = "pop_scale"
    SLIDE_UP     = "slide_up"
    WORD_REVEAL  = "word_reveal"


# ── Preset dataclass ──────────────────────────────────────────────────────────

@dataclass
class CaptionPreset:
    name: str

    # Typography
    font_path: Path = field(default_factory=lambda: _best_font(_MONTSERRAT, _ARIAL_BOLD))
    font_size: int = 86                      # px at 1080 wide
    text_color: tuple = field(default_factory=lambda: Color.WHITE)
    highlight_color: tuple = field(default_factory=lambda: Color.GOLD)  # first/last word

    # Outline + shadow
    outline_width: int = 4                   # px
    outline_color: tuple = field(default_factory=lambda: Color.BLACK)
    shadow_offset: tuple = (3, 3)
    shadow_alpha: int = 160                  # 0–255

    # Safe-zone vertical anchor (fraction of frame height, 0=top, 1=bottom)
    # Default places text in lower-middle (55–75% height)
    y_anchor: float = 0.68                   # centre of text block

    # Words per caption event
    words_per_line: int = 4

    # Animation
    anim_type: AnimationType = AnimationType.FADE
    anim_in_frames: int = 6                  # frames for entrance anim
    anim_out_frames: int = 4                 # frames for exit anim

    # Beat-sync: if True, anim_in starts on exact beat boundary
    beat_sync: bool = False

    # Style tag for auto-selector
    tags: list[str] = field(default_factory=list)
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# THE FIVE PRESETS
# ═══════════════════════════════════════════════════════════════════════════════

CINEMATIC_MINIMAL = CaptionPreset(
    name="CINEMATIC_MINIMAL",
    font_path=_best_font(_MONTSERRAT, _ARIAL_BOLD),
    font_size=52,
    text_color=Color.CREAM,
    highlight_color=Color.GOLD,
    outline_width=2,
    shadow_offset=(2, 2),
    shadow_alpha=100,
    y_anchor=0.72,
    words_per_line=5,
    anim_type=AnimationType.FADE,
    anim_in_frames=12,     # slow fade — 0.4s at 30fps
    anim_out_frames=10,
    beat_sync=False,
    tags=["atmospheric", "storytelling", "slow", "cinematic"],
    description=(
        "Small cream/white text, slow fade. For atmospheric B-roll, slow moments, "
        "or poetic storytelling. Never competes with the footage. "
        "Inspired by ESPN 'Detail' and Football Film School aesthetics."
    ),
)

BOLD_IMPACT = CaptionPreset(
    name="BOLD_IMPACT",
    font_path=_best_font(_BEBAS, _MONTSERRAT, _ARIAL_BOLD),
    font_size=116,
    text_color=Color.WHITE,
    highlight_color=Color.GOLD,
    outline_width=5,
    shadow_offset=(4, 4),
    shadow_alpha=180,
    y_anchor=0.65,
    words_per_line=3,
    anim_type=AnimationType.POP_SCALE,
    anim_in_frames=5,      # 0.17s snap
    anim_out_frames=3,
    beat_sync=True,
    tags=["stat", "fact", "goal", "shock", "hook", "hype"],
    description=(
        "Bebas Neue, oversized, with a pop-scale entrance. Used for stat bombs, "
        "goals, shocking facts, and Short hooks. Dominant style on viral football "
        "edit channels. Beat-sync enabled."
    ),
)

BEAT_SYNC_FLASH = CaptionPreset(
    name="BEAT_SYNC_FLASH",
    font_path=_best_font(_BEBAS, _MONTSERRAT, _ARIAL_BOLD),
    font_size=96,
    text_color=Color.GOLD,
    highlight_color=Color.WHITE,
    outline_width=4,
    shadow_offset=(3, 3),
    shadow_alpha=200,
    y_anchor=0.62,
    words_per_line=3,
    anim_type=AnimationType.INSTANT,
    anim_in_frames=2,
    anim_out_frames=2,
    beat_sync=True,
    tags=["phonk", "hype", "fast", "beat_sync", "energetic"],
    description=(
        "Gold text, instant on/off — appears on exact beat and disappears before "
        "next. Best for phonk/drill soundtracks where rhythm drives pacing. "
        "No transition: the cut IS the effect."
    ),
)

KINETIC_SLIDE = CaptionPreset(
    name="KINETIC_SLIDE",
    font_path=_best_font(_MONTSERRAT, _ARIAL_BOLD),
    font_size=80,
    text_color=Color.WHITE,
    highlight_color=Color.GOLD,
    outline_width=3,
    shadow_offset=(3, 4),
    shadow_alpha=150,
    y_anchor=0.68,
    words_per_line=4,
    anim_type=AnimationType.SLIDE_UP,
    anim_in_frames=8,
    anim_out_frames=5,
    beat_sync=False,
    tags=["story", "build", "moderate", "versatile"],
    description=(
        "Montserrat ExtraBold, slides up from below on entrance. Versatile — works "
        "for factual storytelling, mid-video context, and player introductions. "
        "More dynamic than CINEMATIC_MINIMAL, less aggressive than BOLD_IMPACT."
    ),
)

DRAMATIC_REVEAL = CaptionPreset(
    name="DRAMATIC_REVEAL",
    font_path=_best_font(_MONTSERRAT, _ARIAL_BOLD),
    font_size=90,
    text_color=Color.WHITE,
    highlight_color=Color.GOLD,
    outline_width=4,
    shadow_offset=(4, 5),
    shadow_alpha=200,
    y_anchor=0.66,
    words_per_line=3,
    anim_type=AnimationType.WORD_REVEAL,
    anim_in_frames=7,      # per-word fade-in
    anim_out_frames=5,
    beat_sync=False,
    tags=["drama", "climax", "reveal", "emotional", "hook"],
    description=(
        "Words appear one at a time, building tension. Final word or key stat "
        "renders in GOLD. Ideal for Beyond The Pitch hooks and climax moments. "
        "Matches the 'football story you've forgotten' storytelling brand."
    ),
)


ALL_PRESETS: dict[str, CaptionPreset] = {
    p.name: p for p in [
        CINEMATIC_MINIMAL,
        BOLD_IMPACT,
        BEAT_SYNC_FLASH,
        KINETIC_SLIDE,
        DRAMATIC_REVEAL,
    ]
}
