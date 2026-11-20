"""Tests for src/editing/style_selector.py"""
import pytest

from src.editing.caption_presets import (
    AnimationType,
    CINEMATIC_MINIMAL, BOLD_IMPACT, BEAT_SYNC_FLASH, KINETIC_SLIDE, DRAMATIC_REVEAL,
)
from src.editing.style_selector import (
    select_caption_preset,
    select_sounds,
    assign_story_beats_to_beats,
)
from src.editing.sound_library import SoundEntry, EmbedPolicy


class TestSelectCaptionPreset:
    def test_hook_returns_dramatic_reveal(self):
        p = select_caption_preset(story_type="hook")
        assert p is DRAMATIC_REVEAL

    def test_dramatic_mood_returns_dramatic_reveal(self):
        p = select_caption_preset(mood="dramatic")
        assert p is DRAMATIC_REVEAL

    def test_stat_returns_bold_impact(self):
        p = select_caption_preset(story_type="stat")
        assert p is BOLD_IMPACT

    def test_fact_returns_bold_impact(self):
        p = select_caption_preset(story_type="fact")
        assert p is BOLD_IMPACT

    def test_fast_bpm_returns_beat_sync_flash(self):
        p = select_caption_preset(estimated_bpm=135.0, beat_count=12)
        assert p is BEAT_SYNC_FLASH

    def test_moderate_bpm_with_speech_returns_kinetic_slide(self):
        p = select_caption_preset(estimated_bpm=115.0, beat_count=5, has_speech=True)
        assert p is KINETIC_SLIDE

    def test_atmospheric_no_speech_returns_cinematic_minimal(self):
        p = select_caption_preset(story_type="atmospheric", has_speech=False)
        assert p is CINEMATIC_MINIMAL

    def test_storytelling_no_speech_returns_cinematic_minimal(self):
        p = select_caption_preset(story_type="storytelling", has_speech=False)
        assert p is CINEMATIC_MINIMAL

    def test_climax_returns_dramatic_reveal(self):
        p = select_caption_preset(story_type="climax")
        assert p is DRAMATIC_REVEAL

    def test_worldcup_returns_dramatic_reveal(self):
        p = select_caption_preset(story_type="worldcup")
        assert p is DRAMATIC_REVEAL

    def test_default_fallback_returns_kinetic_slide(self):
        # Default: storytelling + has_speech=True + no BPM → misses all early rules → KINETIC_SLIDE
        p = select_caption_preset(story_type="storytelling", has_speech=True)
        assert p is KINETIC_SLIDE

    def test_override_forces_preset(self):
        p = select_caption_preset(story_type="hook", override="BOLD_IMPACT")
        assert p is BOLD_IMPACT

    def test_override_case_insensitive(self):
        p = select_caption_preset(override="cinematic_minimal")
        assert p is CINEMATIC_MINIMAL

    def test_invalid_override_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            select_caption_preset(override="NONEXISTENT_PRESET")

    def test_fast_bpm_requires_minimum_beats(self):
        # 135 BPM but only 2 beats — should not trigger BEAT_SYNC_FLASH
        p = select_caption_preset(estimated_bpm=135.0, beat_count=2)
        assert p is not BEAT_SYNC_FLASH


class TestSelectSounds:
    def test_returns_list(self):
        results = select_sounds()
        assert isinstance(results, list)

    def test_returns_sound_entries(self):
        results = select_sounds(story_type="hype", top_n=2)
        for r in results:
            assert isinstance(r, SoundEntry)

    def test_embed_only_filter(self):
        results = select_sounds(embed_only=True, top_n=10)
        for r in results:
            assert r.embed_policy == EmbedPolicy.FREE_EMBED

    def test_override_puts_track_first(self):
        # "Cinematic Build Riser" is a track in the library
        results = select_sounds(override="Cinematic Build Riser", top_n=3)
        assert results[0].name == "Cinematic Build Riser"

    def test_unknown_override_does_not_crash(self):
        results = select_sounds(override="Nonexistent Track XYZ", top_n=2)
        assert isinstance(results, list)

    def test_top_n_respected(self):
        results = select_sounds(top_n=1)
        assert len(results) <= 1


class TestAssignStoryBeatsToBeats:
    def test_snaps_within_window(self):
        story_beats = [(0.0, 2.0, "text"), (2.0, 4.0, "more")]
        detected_beats = [0.0, 0.1, 2.05, 4.0]
        result = assign_story_beats_to_beats(story_beats, detected_beats, snap_window=0.2)
        # Second beat start (2.0) should snap to 2.05
        assert abs(result[1][0] - 2.05) < 1e-9

    def test_preserves_duration(self):
        story_beats = [(1.0, 3.0, "word")]
        detected_beats = [0.9, 2.0, 3.5]
        result = assign_story_beats_to_beats(story_beats, detected_beats, snap_window=0.2)
        orig_dur = story_beats[0][1] - story_beats[0][0]
        new_dur  = result[0][1] - result[0][0]
        assert abs(new_dur - orig_dur) < 1e-9

    def test_no_snap_outside_window(self):
        story_beats = [(0.5, 2.0, "text")]
        detected_beats = [0.0, 1.0, 2.0]
        result = assign_story_beats_to_beats(story_beats, detected_beats, snap_window=0.1)
        # 0.5 is 0.5s from nearest beat — should NOT snap
        assert result[0][0] == 0.5

    def test_empty_beats_no_change(self):
        story_beats = [(1.0, 2.0, "text")]
        result = assign_story_beats_to_beats(story_beats, [], snap_window=0.2)
        assert result[0][0] == 1.0

    def test_preserves_text(self):
        story_beats = [(0.0, 1.0, "HELLO WORLD")]
        result = assign_story_beats_to_beats(story_beats, [0.0], snap_window=0.1)
        assert result[0][2] == "HELLO WORLD"
