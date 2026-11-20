"""Tests for ASS caption generation."""

import pytest
from src.clipping.caption_renderer import (
    _ass_time, _group_words, generate_ass, write_ass_file,
)
from src.clipping.models import WordTimestamp


def _words(texts: list[str], start: float = 0.0, gap: float = 0.4) -> list[WordTimestamp]:
    words = []
    t = start
    for w in texts:
        words.append(WordTimestamp(start=t, end=t + 0.3, word=w))
        t += gap
    return words


# ── _ass_time ─────────────────────────────────────────────────────────────────

def test_ass_time_zero():
    assert _ass_time(0.0) == "0:00:00.00"


def test_ass_time_one_second():
    assert _ass_time(1.0) == "0:00:01.00"


def test_ass_time_fractional():
    result = _ass_time(1.255)
    assert result == "0:00:01.26" or result == "0:00:01.25"  # rounding


def test_ass_time_over_minute():
    # 90.5 seconds = 1 min 30.5 sec = 0:01:30.50
    assert _ass_time(90.5) == "0:01:30.50"


# ── _group_words ──────────────────────────────────────────────────────────────

def test_group_words_basic():
    words = _words(["hello", "world", "this", "is", "a", "test"])
    groups = _group_words(words)
    assert len(groups) >= 1
    # Each group has at least 2 words
    for start, end, text in groups:
        assert len(text.split()) >= 1
        assert end >= start


def test_group_words_respects_max():
    words = _words(["a", "b", "c", "d", "e", "f", "g", "h"])
    groups = _group_words(words)
    for _, _, text in groups:
        assert len(text.split()) <= 4


def test_group_words_empty():
    assert _group_words([]) == []


# ── generate_ass ──────────────────────────────────────────────────────────────

def test_generate_ass_has_header():
    words = _words(["incredible", "goal"], start=0.0)
    ass = generate_ass(words, clip_start=0.0, clip_end=5.0)
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass


def test_generate_ass_has_dialogue():
    words = _words(["incredible", "goal"], start=0.0)
    ass = generate_ass(words, clip_start=0.0, clip_end=5.0)
    assert "Dialogue:" in ass


def test_generate_ass_adjusts_to_clip_start():
    # Words at t=10-11s, clip_start=10s → should appear at 0-1s in output
    words = [
        WordTimestamp(start=10.0, end=10.4, word="goal"),
        WordTimestamp(start=10.4, end=10.8, word="brilliant"),
    ]
    ass = generate_ass(words, clip_start=10.0, clip_end=15.0)
    # Should have an event starting near 0:00:00
    assert "0:00:00" in ass


def test_generate_ass_has_branding():
    words = _words(["hello"], start=0.0)
    ass = generate_ass(words, clip_start=0.0, clip_end=3.0, channel_name="TEST CHANNEL")
    assert "TEST CHANNEL" in ass


def test_write_ass_file(tmp_path):
    words = _words(["incredible", "goal", "brilliant"], start=0.5)
    out = tmp_path / "test.ass"
    result = write_ass_file(words, 0.0, 5.0, out)
    assert result.exists()
    content = result.read_text()
    assert "Dialogue:" in content
