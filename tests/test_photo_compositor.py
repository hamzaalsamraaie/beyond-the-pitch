"""Tests for the photo compositor (Ken Burns fallback path)."""

import pytest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from src.video.photo_compositor import (
    PhotoCompositor, SceneConfig, _scale_to_cover, _ken_burns_frame,
    _make_gradient_fallback, build_scene_configs,
)


def _dummy_scene(number: int, start: float, end: float, narration: str = "Test narration here for scene."):
    from src.research.models import StoryboardScene
    return StoryboardScene(
        scene_number=number,
        start_time=start,
        end_time=end,
        narration=narration,
        on_screen_text="TEST",
        visual_requirement="photo",
        source_indices=[0],
    )


def _dummy_storyboard():
    """Build a minimal valid Storyboard (3 scenes, 21s total, all required fields)."""
    from src.research.models import ContentType, Storyboard, ResearchItem, SourceCitation
    scenes = [
        _dummy_scene(1, 0.0, 7.0, "Opening narration for scene one right here."),
        _dummy_scene(2, 7.0, 14.0, "Middle part of the story happening here now."),
        _dummy_scene(3, 14.0, 21.0, "Final conclusion and payoff for this story."),
    ]
    research_item = ResearchItem(
        fact="A test fact that is verified and accurate for this story.",
        source=SourceCitation(
            url="https://en.wikipedia.org/wiki/Test",
            title="Test Article",
            publisher="Wikipedia",
            date_published="",
        ),
        reliability="verified",
    )
    return Storyboard.model_validate({
        "title": "Test Football Short",
        "content_type": "football_moments",
        "hook": "Test hook text here",
        "scenes": [s.model_dump() for s in scenes],
        "total_duration": 21.0,
        "proposed_titles": ["Title One Here", "Title Two Here", "Title Three Here"],
        "hashtags": ["#football", "#Shorts", "#soccer", "#goals", "#sport"],
        "research_items": [research_item.model_dump()],
        "generated_by": "test",
        "script_hash": "abc123",
    })


# ── _scale_to_cover ───────────────────────────────────────────────────────────

def test_scale_to_cover_landscape():
    img = Image.new("RGB", (1920, 1080))  # landscape
    result = _scale_to_cover(img, 1080, 1920, margin=1.0)
    assert result.size == (1080, 1920)


def test_scale_to_cover_portrait():
    img = Image.new("RGB", (500, 800))
    result = _scale_to_cover(img, 1080, 1920, margin=1.0)
    assert result.size == (1080, 1920)


def test_scale_to_cover_with_margin():
    img = Image.new("RGB", (1920, 1080))
    result = _scale_to_cover(img, 1080, 1920, margin=1.2)
    assert result.size == (int(1080 * 1.2), int(1920 * 1.2))


# ── _ken_burns_frame ──────────────────────────────────────────────────────────

def _base_img():
    return Image.new("RGB", (int(1080 * 1.22), int(1920 * 1.22)), color=(100, 50, 200))


def test_ken_burns_zoom_in_returns_correct_size():
    base = _base_img()
    result = _ken_burns_frame(base, t=0.0, effect="zoom_in")
    assert result.size == (1080, 1920)


def test_ken_burns_zoom_out_returns_correct_size():
    base = _base_img()
    result = _ken_burns_frame(base, t=1.0, effect="zoom_out")
    assert result.size == (1080, 1920)


def test_ken_burns_pan_right_returns_correct_size():
    base = _base_img()
    result = _ken_burns_frame(base, t=0.5, effect="pan_right")
    assert result.size == (1080, 1920)


def test_ken_burns_slow_push_returns_correct_size():
    base = _base_img()
    result = _ken_burns_frame(base, t=0.3, effect="slow_push")
    assert result.size == (1080, 1920)


# ── gradient fallback ─────────────────────────────────────────────────────────

def test_gradient_fallback_correct_size():
    img = _make_gradient_fallback(0)
    expected_w = int(1080 * 1.22)
    expected_h = int(1920 * 1.22)
    assert img.size == (expected_w, expected_h)


# ── PhotoCompositor ───────────────────────────────────────────────────────────

def test_compositor_total_frames():
    sb = _dummy_storyboard()  # 3 scenes × 7s = 21s
    configs = [SceneConfig(), SceneConfig(), SceneConfig()]
    comp = PhotoCompositor(sb, configs, fps=10)
    assert comp.total_frames() == 210  # 21s × 10fps


def test_compositor_mismatched_configs_raises():
    sb = _dummy_storyboard()
    with pytest.raises(ValueError, match="scene_configs length"):
        PhotoCompositor(sb, [SceneConfig()], fps=30)  # 3 scenes, 1 config


def test_compositor_generates_correct_frame_count():
    sb = _dummy_storyboard()  # 21 seconds
    configs = [SceneConfig(), SceneConfig(), SceneConfig()]
    comp = PhotoCompositor(sb, configs, fps=5)
    comp.prepare()
    frames = list(comp.generate_frames())
    assert len(frames) == 105  # 21s × 5fps


def test_compositor_frames_are_correct_size():
    sb = _dummy_storyboard()
    configs = [SceneConfig(), SceneConfig(), SceneConfig()]
    comp = PhotoCompositor(sb, configs, fps=5)
    comp.prepare()
    for frame in comp.generate_frames():
        assert frame.size == (1080, 1920)
        break  # check just first frame


def test_build_scene_configs_pads_missing():
    sb = _dummy_storyboard()  # 3 scenes
    configs = build_scene_configs(sb, [None])  # only 1 path provided
    assert len(configs) == 3


def test_compositor_uses_fallback_for_missing_photo():
    sb = _dummy_storyboard()
    configs = [
        SceneConfig(photo_path=Path("/nonexistent/photo.jpg")),
        SceneConfig(),
        SceneConfig(),
    ]
    comp = PhotoCompositor(sb, configs, fps=3)
    comp.prepare()
    # Should not raise even with missing photo
    frames = list(comp.generate_frames())
    assert len(frames) == 63  # 21s × 3fps
