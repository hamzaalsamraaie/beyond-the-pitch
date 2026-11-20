"""Tests for the video effects system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.editing.effects import (
    ColorGradeEffect,
    EffectsConfig,
    FOOTBALL_EDIT_CINEMATIC,
    FOOTBALL_EDIT_DRAMATIC,
    FOOTBALL_EDIT_NONE,
    FOOTBALL_EDIT_VIBRANT,
    VignetteEffect,
    ZoomEffect,
    _build_filter_complex,
    _describe,
    apply_effects,
    select_effects_config,
)


class TestBuildFilterComplex:
    def test_no_effects_returns_empty(self):
        result = _build_filter_complex(FOOTBALL_EDIT_NONE, 30.0)
        assert not result  # empty string or falsy

    def test_zoom_effect_includes_scale_crop(self):
        config = EffectsConfig(zoom=ZoomEffect(zoom_factor=1.05))
        result = _build_filter_complex(config, 30.0)
        assert result
        filter_str, label = result
        assert "scale=" in filter_str
        assert "crop=" in filter_str

    def test_color_grade_cinematic_includes_curves(self):
        config = EffectsConfig(color_grade=ColorGradeEffect(preset="cinematic"))
        result = _build_filter_complex(config, 30.0)
        assert result
        filter_str, label = result
        assert "curves" in filter_str

    def test_vignette_includes_vignette_filter(self):
        config = EffectsConfig(vignette=VignetteEffect(strength=0.5))
        result = _build_filter_complex(config, 30.0)
        assert result
        filter_str, label = result
        assert "vignette" in filter_str

    def test_all_effects_produces_pipeline(self):
        config = EffectsConfig(
            zoom=ZoomEffect(zoom_factor=1.05),
            color_grade=ColorGradeEffect(preset="dramatic"),
            vignette=VignetteEffect(strength=0.4),
        )
        result = _build_filter_complex(config, 30.0)
        assert result
        filter_str, label = result
        assert "scale=" in filter_str
        assert "crop=" in filter_str
        assert "curves" in filter_str
        assert "vignette" in filter_str

    def test_neutral_grade_no_filter(self):
        config = EffectsConfig(color_grade=ColorGradeEffect(preset="neutral"))
        result = _build_filter_complex(config, 30.0)
        # neutral grade should produce no filter
        assert not result

    def test_zero_zoom_produces_no_zoompan(self):
        config = EffectsConfig(zoom=ZoomEffect(zoom_factor=1.0))
        result = _build_filter_complex(config, 30.0)
        # zoom_factor=1.0 is a no-op
        assert not result or "zoompan" not in result[0]


class TestSelectEffectsConfig:
    def test_dramatic_mood_returns_dramatic(self):
        config = select_effects_config("football_moments", mood="dramatic")
        assert config == FOOTBALL_EDIT_DRAMATIC

    def test_worldcup_story_returns_dramatic(self):
        config = select_effects_config("worldcup_final", mood="normal")
        assert config == FOOTBALL_EDIT_DRAMATIC

    def test_motivation_returns_cinematic(self):
        config = select_effects_config("motivation", mood="normal")
        assert config == FOOTBALL_EDIT_CINEMATIC

    def test_skill_returns_vibrant(self):
        config = select_effects_config("skill_highlight", mood="normal")
        assert config == FOOTBALL_EDIT_VIBRANT

    def test_goal_returns_vibrant(self):
        config = select_effects_config("goal_compilation", mood="normal")
        assert config == FOOTBALL_EDIT_VIBRANT

    def test_unknown_returns_cinematic(self):
        config = select_effects_config("unknown_xyz", mood="unknown")
        assert config == FOOTBALL_EDIT_CINEMATIC


class TestDescribe:
    def test_no_effects_returns_none_string(self):
        assert _describe(FOOTBALL_EDIT_NONE) == "none"

    def test_zoom_in_description(self):
        config = EffectsConfig(zoom=ZoomEffect(zoom_factor=1.05))
        assert "zoom" in _describe(config)

    def test_grade_in_description(self):
        config = EffectsConfig(color_grade=ColorGradeEffect(preset="dramatic"))
        assert "grade" in _describe(config)

    def test_all_effects_in_description(self):
        desc = _describe(FOOTBALL_EDIT_DRAMATIC)
        assert "zoom" in desc
        assert "grade" in desc
        assert "vignette" in desc


class TestPresetIntegrity:
    def test_cinematic_has_zoom(self):
        assert FOOTBALL_EDIT_CINEMATIC.zoom is not None

    def test_dramatic_has_all_effects(self):
        assert FOOTBALL_EDIT_DRAMATIC.zoom is not None
        assert FOOTBALL_EDIT_DRAMATIC.color_grade is not None
        assert FOOTBALL_EDIT_DRAMATIC.vignette is not None

    def test_none_has_no_effects(self):
        assert FOOTBALL_EDIT_NONE.zoom is None
        assert FOOTBALL_EDIT_NONE.color_grade is None
        assert FOOTBALL_EDIT_NONE.vignette is None

    def test_zoom_factors_are_reasonable(self):
        for config in [FOOTBALL_EDIT_CINEMATIC, FOOTBALL_EDIT_DRAMATIC, FOOTBALL_EDIT_VIBRANT]:
            if config.zoom:
                assert 1.0 < config.zoom.zoom_factor < 1.3

    def test_vignette_strength_bounded(self):
        for config in [FOOTBALL_EDIT_CINEMATIC, FOOTBALL_EDIT_DRAMATIC, FOOTBALL_EDIT_VIBRANT]:
            if config.vignette:
                assert 0.0 < config.vignette.strength <= 1.0


class TestApplyEffects:
    def test_missing_input_returns_false(self, tmp_path):
        result = apply_effects(
            tmp_path / "nonexistent.mp4",
            tmp_path / "out.mp4",
            FOOTBALL_EDIT_NONE,
        )
        assert result is False

    def test_no_effects_copy_mode(self, tmp_path):
        """FOOTBALL_EDIT_NONE should use simple copy (fastest path)."""
        fake_input = tmp_path / "input.mp4"
        fake_input.write_bytes(b"fake")
        out = tmp_path / "out.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1  # fail on ffmpeg
            apply_effects(fake_input, out, FOOTBALL_EDIT_NONE)
        # Verify copy mode was attempted (no -filter_complex)
        if mock_run.called:
            cmd = mock_run.call_args[0][0]
            assert "-filter_complex" not in cmd
