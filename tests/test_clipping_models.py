"""Tests for clipping data models."""

from pathlib import Path
from src.clipping.models import WordTimestamp, TranscriptSegment, Transcript, ClipSpec


def test_word_timestamp_duration():
    w = WordTimestamp(start=1.0, end=1.5, word="goal")
    assert w.duration == 0.5


def test_word_clean():
    # clean strips surrounding whitespace, lowercases, and strips trailing punctuation
    w = WordTimestamp(start=0, end=1, word="  Goal!  ")
    assert w.clean == "goal"  # trailing ! stripped by rstrip(".,!?;:")


def test_transcript_all_words():
    segs = [
        TranscriptSegment(0, 2, "hello world",
                          words=[WordTimestamp(0, 1, "hello"), WordTimestamp(1, 2, "world")]),
        TranscriptSegment(2, 4, "foo bar",
                          words=[WordTimestamp(2, 3, "foo"), WordTimestamp(3, 4, "bar")]),
    ]
    t = Transcript(segments=segs, source_duration=4.0)
    assert len(t.all_words) == 4


def test_transcript_words_in_range():
    words = [
        WordTimestamp(0.0, 0.5, "one"),
        WordTimestamp(0.5, 1.0, "two"),
        WordTimestamp(1.0, 1.5, "three"),
        WordTimestamp(1.5, 2.0, "four"),
    ]
    seg = TranscriptSegment(0, 2, "one two three four", words=words)
    t = Transcript(segments=[seg], source_duration=2.0)
    in_range = t.words_in_range(0.5, 1.5)
    assert [w.word for w in in_range] == ["two", "three"]


def test_transcript_text_in_range():
    words = [WordTimestamp(0, 1, "great"), WordTimestamp(1, 2, "goal")]
    seg = TranscriptSegment(0, 2, "great goal", words=words)
    t = Transcript(segments=[seg], source_duration=2.0)
    assert t.text_in_range(0, 2) == "great goal"


def test_clip_spec_duration():
    clip = ClipSpec(
        source_path=Path("/tmp/test.mp4"),
        footage_asset_id="abc",
        start=10.0,
        end=50.0,
        score=0.8,
    )
    assert clip.duration == 40.0
