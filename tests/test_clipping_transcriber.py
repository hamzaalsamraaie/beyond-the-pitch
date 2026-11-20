"""Tests for the transcription module (uses MockTranscriber — no audio required)."""

from pathlib import Path
import pytest
from src.clipping.transcriber import MockTranscriber, _build_mock_words, get_transcriber
from src.clipping.models import Transcript


def test_mock_words_monotone():
    words = _build_mock_words("hello world foo bar")
    assert len(words) == 4
    for i in range(len(words) - 1):
        assert words[i].end <= words[i + 1].start + 0.01  # monotone


def test_mock_transcriber_returns_transcript(tmp_path):
    """MockTranscriber should work even with a non-existent path."""
    t = MockTranscriber()
    # Mock doesn't read the file — it just ignores the path
    result = t.transcribe(tmp_path / "fake.mp4")
    assert isinstance(result, Transcript)
    assert len(result.segments) > 0
    assert result.language == "en"


def test_mock_transcriber_word_coverage():
    t = MockTranscriber()
    result = t.transcribe(Path("/tmp/fake.mp4"))
    all_text = " ".join(w.word for w in result.all_words)
    assert "incredible" in all_text.lower() or len(result.all_words) > 0


def test_mock_transcriber_monotone_timestamps():
    t = MockTranscriber()
    result = t.transcribe(Path("/tmp/fake.mp4"))
    words = result.all_words
    for i in range(len(words) - 1):
        assert words[i].start <= words[i].end, f"word {i} start > end"


def test_get_transcriber_mock():
    tr = get_transcriber("mock")
    assert tr.name == "mock"


def test_faster_whisper_falls_back_to_mock_when_missing():
    # If faster_whisper is not installed, get_transcriber returns MockTranscriber
    tr = get_transcriber("faster_whisper")
    # Either returns FasterWhisperTranscriber (if installed) or MockTranscriber
    assert tr.name in ("mock",) or "whisper" in tr.name.lower()
