"""Tests for the highlight scorer."""

import pytest
from src.clipping.highlight_detector import score_windows, top_window, _score_words
from src.clipping.models import Transcript, TranscriptSegment, WordTimestamp
from src.clipping.transcriber import MockTranscriber


def _make_transcript(text: str, source_duration: float = 120.0) -> Transcript:
    """Build a simple transcript from a string of space-separated words."""
    t = MockTranscriber(mock_text=text, mock_duration=source_duration)
    return t.transcribe(None)


def test_score_words_tier1():
    score, peaks = _score_words(["goal", "incredible"])
    assert score >= 6.0  # 3+3
    assert "goal" in peaks
    assert "incredible" in peaks


def test_score_words_tier2():
    score, peaks = _score_words(["penalty", "save"])
    assert score >= 4.0


def test_score_words_density_bonus():
    # 4 tier-1 words → 3+3+3+3 + density = 12 + 1.0
    score, peaks = _score_words(["goal", "incredible", "unbelievable", "sensational"])
    assert score > 12.0


def test_score_windows_empty():
    t = Transcript(segments=[], source_duration=0)
    windows = score_windows(t)
    assert windows == []


def test_score_windows_ranks_excited_text_higher():
    boring = "the player passes the ball and the defender clears it again slowly"
    excited = "goal incredible unbelievable brilliant sensational screamer"

    # Build a transcript: boring in [0..60s], excited in [120..130s]
    boring_words: list[WordTimestamp] = []
    t = 0.0
    for w in boring.split():
        boring_words.append(WordTimestamp(start=t, end=t + 0.4, word=w))
        t += 0.5

    excited_words: list[WordTimestamp] = []
    t2 = 120.0
    for w in excited.split():
        excited_words.append(WordTimestamp(start=t2, end=t2 + 0.4, word=w))
        t2 += 0.5

    all_words = boring_words + excited_words
    seg = TranscriptSegment(0, t2, "...", words=all_words)
    transcript = Transcript(segments=[seg], source_duration=t2)

    # Use a 15s window; total duration = ~130s, so many windows
    windows = score_windows(transcript, window_secs=15.0, step_secs=5.0, min_words=3)
    assert len(windows) > 0
    # The top window should have a positive score
    top = windows[0]
    assert top.score > 0
    # The window containing the excited words should have a higher score
    excited_windows = [w for w in windows if w.start >= 118.0]
    boring_windows = [w for w in windows if w.end <= 10.0]
    if excited_windows and boring_windows:
        assert max(w.score for w in excited_windows) > max(w.score for w in boring_windows)


def test_top_window_returns_something():
    t = MockTranscriber()
    transcript = t.transcribe(None)
    window = top_window(transcript, target_duration=30.0)
    if transcript.source_duration >= 30.0:
        assert window is not None
        assert window.duration <= 30.0 + 2.0  # slight overshoot allowed
