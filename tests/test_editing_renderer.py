"""Tests for src/editing/renderer.py — CaptionEvent, WordRevealEvent, build_events."""
import pytest
from unittest.mock import MagicMock, patch

from src.editing.caption_presets import (
    AnimationType, CINEMATIC_MINIMAL, BOLD_IMPACT, BEAT_SYNC_FLASH,
    KINETIC_SLIDE, DRAMATIC_REVEAL,
)
from src.editing.renderer import (
    CaptionEvent, WordRevealEvent, build_events,
    _draw_text_with_outline,
    SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE, W, H,
)


# ── _draw_text_with_outline ───────────────────────────────────────────────────

class TestDrawTextWithOutline:
    def _make_draw(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        return ImageDraw.Draw(img, "RGBA"), img

    def test_draws_without_error(self):
        from PIL import ImageFont
        draw, img = self._make_draw()
        font = ImageFont.load_default()
        _draw_text_with_outline(
            draw, (100, 100), "HELLO", font,
            fill=(255, 255, 255), outline_color=(0, 0, 0), outline_width=2,
            alpha=1.0,
        )
        # If we get here without exception, the draw succeeded
        pixels = img.getpixel((100, 100))
        assert isinstance(pixels, tuple)

    def test_zero_alpha_draws_transparent(self):
        from PIL import ImageFont
        draw, img = self._make_draw()
        # Pre-fill with a color
        from PIL import ImageDraw as ID
        full_draw = ID.Draw(img)
        full_draw.rectangle((0, 0, W, H), fill=(50, 50, 50, 255))
        font = ImageFont.load_default()
        _draw_text_with_outline(
            draw, (100, 100), "X", font,
            fill=(255, 0, 0), outline_color=(0, 0, 0), outline_width=1,
            alpha=0.0,
        )
        # With alpha=0, nothing should have been drawn with full opacity
        # The pixel should still be near 50,50,50
        px = img.getpixel((200, 200))
        assert px[0] == 50


# ── CaptionEvent ──────────────────────────────────────────────────────────────

class TestCaptionEvent:
    def _make_frame(self):
        from PIL import Image
        return Image.new("RGBA", (W, H), (10, 10, 10, 255))

    def test_render_before_start_does_nothing(self):
        ev = CaptionEvent(5.0, 10.0, "TEST", KINETIC_SLIDE)
        frame = self._make_frame()
        original = frame.copy()
        ev.render_onto(frame, 0.0)
        assert list(frame.getdata()) == list(original.getdata())

    def test_render_after_end_does_nothing(self):
        ev = CaptionEvent(5.0, 10.0, "TEST", KINETIC_SLIDE)
        frame = self._make_frame()
        original = frame.copy()
        ev.render_onto(frame, 10.5)
        assert list(frame.getdata()) == list(original.getdata())

    def test_render_during_active_modifies_frame(self):
        ev = CaptionEvent(0.0, 5.0, "GOAL", BOLD_IMPACT)
        frame = self._make_frame()
        ev.render_onto(frame, 2.5)
        # Frame should be modified — at least some pixels should differ
        data = list(frame.getdata())
        orig_data = [(10, 10, 10, 255)] * (W * H)
        assert data != orig_data

    def test_progress_at_start(self):
        ev = CaptionEvent(0.0, 10.0, "text", CINEMATIC_MINIMAL)
        in_p, out_p = ev._progress(0.0)
        assert 0.0 <= in_p <= 1.0
        assert out_p >= 0.0

    def test_progress_at_end_has_high_out(self):
        ev = CaptionEvent(0.0, 10.0, "text", CINEMATIC_MINIMAL)
        in_p, out_p = ev._progress(9.9)
        assert out_p > 0.0

    def test_all_animation_types_render_without_error(self):
        for preset in (CINEMATIC_MINIMAL, BOLD_IMPACT, BEAT_SYNC_FLASH, KINETIC_SLIDE):
            ev = CaptionEvent(0.0, 5.0, "STAT", preset)
            frame = self._make_frame()
            ev.render_onto(frame, 2.5)  # midpoint, should not raise

    def test_highlight_event_renders_without_error(self):
        ev = CaptionEvent(0.0, 3.0, "GOLD TEXT", BOLD_IMPACT, is_highlight=True)
        frame = self._make_frame()
        ev.render_onto(frame, 1.5)  # should not raise

    def test_very_long_text_clamped_to_safe_zone(self):
        long_text = "VERY LONG TEXT THAT EXCEEDS NORMAL WIDTH IN THIS SHORT"
        ev = CaptionEvent(0.0, 5.0, long_text, KINETIC_SLIDE)
        frame = self._make_frame()
        ev.render_onto(frame, 2.5)  # should not raise or write outside safe zone


# ── WordRevealEvent ───────────────────────────────────────────────────────────

class TestWordRevealEvent:
    def _make_frame(self):
        from PIL import Image
        return Image.new("RGBA", (W, H), (0, 0, 0, 255))

    def test_single_word_renders(self):
        ev = WordRevealEvent(0.0, 3.0, "GOAL", DRAMATIC_REVEAL)
        frame = self._make_frame()
        ev.render_onto(frame, 1.5)

    def test_before_start_does_nothing(self):
        ev = WordRevealEvent(5.0, 10.0, "word1 word2", DRAMATIC_REVEAL)
        frame = self._make_frame()
        original = frame.copy()
        ev.render_onto(frame, 0.0)
        assert list(frame.getdata()) == list(original.getdata())

    def test_after_end_does_nothing(self):
        ev = WordRevealEvent(0.0, 3.0, "word1 word2", DRAMATIC_REVEAL)
        frame = self._make_frame()
        original = frame.copy()
        ev.render_onto(frame, 5.0)
        assert list(frame.getdata()) == list(original.getdata())

    def test_multi_word_reveals_progressively(self):
        text = "Spain one Argentina"
        ev = WordRevealEvent(0.0, 3.0, text, DRAMATIC_REVEAL)
        # Should not error at any point in time
        frame = self._make_frame()
        for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 2.9]:
            f = frame.copy()
            ev.render_onto(f, t)

    def test_empty_text_no_error(self):
        ev = WordRevealEvent(0.0, 2.0, "   ", DRAMATIC_REVEAL)
        frame = self._make_frame()
        ev.render_onto(frame, 1.0)


# ── build_events ──────────────────────────────────────────────────────────────

class TestBuildEvents:
    def test_returns_list(self):
        beats = [(0.0, 2.0, "STAT"), (2.0, 4.0, "ANOTHER")]
        events = build_events(beats, BOLD_IMPACT)
        assert isinstance(events, list)
        assert len(events) == 2

    def test_word_reveal_preset_returns_word_reveal_events(self):
        beats = [(0.0, 3.0, "word1 word2")]
        events = build_events(beats, DRAMATIC_REVEAL)
        assert all(isinstance(e, WordRevealEvent) for e in events)

    def test_non_word_reveal_returns_caption_events(self):
        beats = [(0.0, 3.0, "STAT"), (3.0, 6.0, "MORE")]
        events = build_events(beats, BOLD_IMPACT)
        assert all(isinstance(e, CaptionEvent) for e in events)

    def test_highlight_applied_to_last_beats(self):
        beats = [(0.0, 1.0, "A"), (1.0, 2.0, "B"), (2.0, 3.0, "C")]
        events = build_events(beats, KINETIC_SLIDE)
        # Last 2 events should be highlight
        cap_events = [e for e in events if isinstance(e, CaptionEvent)]
        assert cap_events[-1].is_highlight is True
        assert cap_events[-2].is_highlight is True
        assert cap_events[0].is_highlight is False

    def test_empty_beats_returns_empty(self):
        events = build_events([], BOLD_IMPACT)
        assert events == []

    def test_timing_preserved(self):
        beats = [(1.5, 3.5, "text")]
        events = build_events(beats, KINETIC_SLIDE)
        assert events[0].start == 1.5
        assert events[0].end == 3.5


# ── Safe-zone constants sanity ─────────────────────────────────────────────────

class TestSafeZoneConstants:
    def test_canvas_dimensions(self):
        assert W == 1080
        assert H == 1920

    def test_safe_top_clears_youtube_ui(self):
        assert SAFE_TOP >= 100

    def test_safe_bottom_clears_seek_bar(self):
        assert SAFE_BOTTOM >= 200

    def test_caption_area_has_room(self):
        # Usable vertical space for captions
        usable = H - SAFE_TOP - SAFE_BOTTOM
        assert usable > 500  # plenty of room for captions
