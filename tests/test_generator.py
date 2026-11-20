"""
Smoke tests for the test video generator.
These tests do NOT call FFmpeg; they only verify frame rendering and DB integration.
Run the full end-to-end test manually with: python -m src.video.test_generator
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.video.test_generator import SCENES, _draw_scene_frame, render_frames


def test_draw_scene_frame_produces_correct_size():
    img = _draw_scene_frame(SCENES[0], frame_idx=0, total_frames=30)
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1920)
    assert img.mode == "RGB"


def test_draw_all_scenes_produce_correct_size():
    for scene in SCENES:
        img = _draw_scene_frame(scene, frame_idx=5, total_frames=30)
        assert img.size == (1080, 1920)


def test_render_frames_writes_png_files():
    with tempfile.TemporaryDirectory() as tmp:
        frame_dir = Path(tmp)
        # Use only the first scene to keep the test fast
        single_scene = [SCENES[0]]
        total = render_frames(single_scene, frame_dir)
        pngs = sorted(frame_dir.glob("frame_*.png"))
        assert len(pngs) == total
        assert total == int(SCENES[0].duration_secs * 30)
        # Verify the first frame is a valid image of the right dimensions
        with Image.open(pngs[0]) as img:
            assert img.size == (1080, 1920)
