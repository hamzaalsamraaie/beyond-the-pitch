"""
Automatic style selector: chooses the best caption preset and sound
recommendations for a given Short based on observable metadata.

Override either selection by passing explicit names to the functions.
"""

from __future__ import annotations

from src.editing.caption_presets import (
    CaptionPreset, ALL_PRESETS,
    CINEMATIC_MINIMAL, BOLD_IMPACT, BEAT_SYNC_FLASH, KINETIC_SLIDE, DRAMATIC_REVEAL,
)
from src.editing.sound_library import SoundEntry, recommend_sounds
from src.core.logger import get_logger

logger = get_logger(__name__)


def select_caption_preset(
    story_type: str = "storytelling",
    estimated_bpm: float = 0.0,
    beat_count: int = 0,
    has_speech: bool = False,
    duration_secs: float = 28.0,
    mood: str = "",
    override: str | None = None,
) -> CaptionPreset:
    """
    Select the most appropriate caption preset.

    Parameters
    ----------
    story_type : "hook" | "stat" | "storytelling" | "tribute" | "hype" | "climax"
    estimated_bpm : BPM detected from audio (0 = unknown / no music)
    beat_count : number of beat markers detected
    has_speech : True if transcript has spoken words to caption
    duration_secs : clip duration
    mood : freeform mood hint (e.g. "dramatic", "celebratory")
    override : preset name to force (bypasses all logic)

    Returns
    -------
    CaptionPreset
    """
    if override:
        preset = ALL_PRESETS.get(override.upper())
        if preset is None:
            raise ValueError(f"Unknown preset {override!r}. Choose from: {list(ALL_PRESETS)}")
        logger.info("style_selector_override", preset=preset.name)
        return preset

    # Decision rules (ordered by priority)
    # 1. Pure hook short (<= 5s worth of content) → DRAMATIC_REVEAL
    if story_type == "hook" or mood in ("dramatic", "reveal"):
        logger.info("style_selector_chosen", preset="DRAMATIC_REVEAL", reason="story_type_hook")
        return DRAMATIC_REVEAL

    # 2. Stat / shocking fact → BOLD_IMPACT
    if story_type in ("stat", "fact", "goal"):
        logger.info("style_selector_chosen", preset="BOLD_IMPACT", reason="stat_or_fact")
        return BOLD_IMPACT

    # 3. Fast music (phonk > 130 BPM) → BEAT_SYNC_FLASH
    if estimated_bpm >= 130 and beat_count >= 10:
        logger.info("style_selector_chosen", preset="BEAT_SYNC_FLASH", reason="fast_bpm")
        return BEAT_SYNC_FLASH

    # 4. Moderate tempo (100–130) with speech → KINETIC_SLIDE
    if 100 <= estimated_bpm < 130 and has_speech:
        logger.info("style_selector_chosen", preset="KINETIC_SLIDE", reason="moderate_bpm_speech")
        return KINETIC_SLIDE

    # 5. Atmospheric / no speech / slow → CINEMATIC_MINIMAL
    if not has_speech and story_type in ("storytelling", "atmospheric"):
        logger.info("style_selector_chosen", preset="CINEMATIC_MINIMAL", reason="atmospheric_no_speech")
        return CINEMATIC_MINIMAL

    # 6. World Cup / climax → DRAMATIC_REVEAL
    if story_type in ("climax", "worldcup"):
        logger.info("style_selector_chosen", preset="DRAMATIC_REVEAL", reason="climax")
        return DRAMATIC_REVEAL

    # Default fallback
    logger.info("style_selector_chosen", preset="KINETIC_SLIDE", reason="default_fallback")
    return KINETIC_SLIDE


def select_sounds(
    story_type: str = "storytelling",
    estimated_bpm: float = 0.0,
    embed_only: bool = False,
    override: str | None = None,
    top_n: int = 3,
) -> list[SoundEntry]:
    """
    Recommend sounds for a given story type.

    override: exact track name to force first in the list.
    """
    if override:
        from src.editing.sound_library import SOUND_LIBRARY  # noqa: PLC0415
        forced = next((s for s in SOUND_LIBRARY if s.name.lower() == override.lower()), None)
        if forced:
            rest = recommend_sounds(story_type, int(estimated_bpm), embed_only=embed_only,
                                    top_n=top_n - 1)
            return [forced] + [s for s in rest if s.name != forced.name]

    return recommend_sounds(
        story_type=story_type,
        bpm_target=int(estimated_bpm),
        embed_only=embed_only,
        top_n=top_n,
    )


# ── Segment-level beat assignment ─────────────────────────────────────────────

def assign_story_beats_to_beats(
    story_beats: list[tuple[float, float, str]],
    detected_beats: list[float],
    snap_window: float = 0.15,
) -> list[tuple[float, float, str]]:
    """
    Optionally snap story beat start times to detected music beats.

    Only snaps if a beat falls within snap_window seconds.
    Returns updated beats list (original preserved if no snap).
    """
    from src.editing.beat_detector import snap_to_beat  # noqa: PLC0415
    snapped = []
    for start, end, text in story_beats:
        new_start = snap_to_beat(start, detected_beats, snap_window)
        duration = end - start
        snapped.append((new_start, new_start + duration, text))
    return snapped
