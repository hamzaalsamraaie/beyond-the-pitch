"""Tests for src/editing/caption_presets.py"""
import pytest
from pathlib import Path
from unittest.mock import patch

from src.editing.caption_presets import (
    AnimationType, CaptionPreset, Color,
    CINEMATIC_MINIMAL, BOLD_IMPACT, BEAT_SYNC_FLASH, KINETIC_SLIDE, DRAMATIC_REVEAL,
    ALL_PRESETS,
)


class TestColor:
    def test_white_is_rgb(self):
        assert Color.WHITE == (255, 255, 255)

    def test_gold_matches_brand(self):
        r, g, b = Color.GOLD
        assert r == 201 and g == 168 and b == 76

    def test_all_rgb_values_in_range(self):
        for name in ("WHITE", "GOLD", "BLACK", "RED_HOT", "CREAM"):
            color = getattr(Color, name)
            for channel in color:
                assert 0 <= channel <= 255


class TestAnimationType:
    def test_all_types_defined(self):
        types = {at.value for at in AnimationType}
        assert "instant" in types
        assert "fade" in types
        assert "pop_scale" in types
        assert "slide_up" in types
        assert "word_reveal" in types

    def test_string_subclass(self):
        assert AnimationType.FADE == "fade"


class TestCaptionPreset:
    def test_preset_has_required_fields(self):
        p = CINEMATIC_MINIMAL
        assert p.name == "CINEMATIC_MINIMAL"
        assert p.font_size > 0
        assert 0.0 < p.y_anchor < 1.0
        assert p.anim_in_frames > 0
        assert p.anim_out_frames > 0

    def test_all_presets_in_all_presets_dict(self):
        expected = {"CINEMATIC_MINIMAL", "BOLD_IMPACT", "BEAT_SYNC_FLASH", "KINETIC_SLIDE", "DRAMATIC_REVEAL"}
        assert set(ALL_PRESETS.keys()) == expected

    def test_all_presets_dict_values_are_presets(self):
        for name, preset in ALL_PRESETS.items():
            assert isinstance(preset, CaptionPreset)
            assert preset.name == name

    def test_safe_zone_anchors(self):
        # All presets must anchor captions in the lower-middle safe zone
        for preset in ALL_PRESETS.values():
            assert 0.5 <= preset.y_anchor <= 0.85, f"{preset.name} y_anchor out of range"

    def test_bold_impact_uses_bebas_or_montserrat(self):
        # BOLD_IMPACT should use a display font
        assert BOLD_IMPACT.font_path.suffix == ".ttf"

    def test_beat_sync_presets(self):
        assert BOLD_IMPACT.beat_sync is True
        assert BEAT_SYNC_FLASH.beat_sync is True
        assert CINEMATIC_MINIMAL.beat_sync is False
        assert KINETIC_SLIDE.beat_sync is False

    def test_animation_types(self):
        assert CINEMATIC_MINIMAL.anim_type == AnimationType.FADE
        assert BOLD_IMPACT.anim_type == AnimationType.POP_SCALE
        assert BEAT_SYNC_FLASH.anim_type == AnimationType.INSTANT
        assert KINETIC_SLIDE.anim_type == AnimationType.SLIDE_UP
        assert DRAMATIC_REVEAL.anim_type == AnimationType.WORD_REVEAL

    def test_cinematic_minimal_slow_fade(self):
        # Slow fade requires more frames than fast presets
        assert CINEMATIC_MINIMAL.anim_in_frames > BOLD_IMPACT.anim_in_frames

    def test_beat_sync_flash_fastest_anim(self):
        assert BEAT_SYNC_FLASH.anim_in_frames <= 3

    def test_presets_have_tags(self):
        for preset in ALL_PRESETS.values():
            assert len(preset.tags) > 0, f"{preset.name} has no tags"

    def test_presets_have_description(self):
        for preset in ALL_PRESETS.values():
            assert len(preset.description) > 20, f"{preset.name} description too short"

    def test_highlight_color_is_gold(self):
        # All presets except BEAT_SYNC_FLASH use brand gold for highlights.
        # BEAT_SYNC_FLASH inverts: gold text, white highlight (intentional).
        for preset in ALL_PRESETS.values():
            if preset.name == "BEAT_SYNC_FLASH":
                assert preset.text_color == Color.GOLD
                assert preset.highlight_color == Color.WHITE
            else:
                assert preset.highlight_color == Color.GOLD, f"{preset.name} highlight != GOLD"

    def test_font_path_is_path_object(self):
        for preset in ALL_PRESETS.values():
            assert isinstance(preset.font_path, Path)
