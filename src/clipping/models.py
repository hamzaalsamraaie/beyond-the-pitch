"""
Data models for the clipping pipeline.

WordTimestamp    — single timed word from Whisper
TranscriptSegment — timed text chunk
Transcript       — full transcript with helpers
ScoredWindow     — a clip window with a highlight score
ClipSpec         — ready-to-render clip specification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WordTimestamp:
    start: float   # seconds from start of media
    end: float
    word: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def clean(self) -> str:
        return self.word.strip().lower().rstrip(".,!?;:")


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Transcript:
    segments: list[TranscriptSegment]
    language: str = "en"
    source_duration: float = 0.0  # total media duration in seconds

    @property
    def all_words(self) -> list[WordTimestamp]:
        words: list[WordTimestamp] = []
        for seg in self.segments:
            words.extend(seg.words)
        return words

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)

    def segments_in_range(self, start: float, end: float) -> list[TranscriptSegment]:
        return [s for s in self.segments if s.end > start and s.start < end]

    def words_in_range(self, start: float, end: float) -> list[WordTimestamp]:
        return [w for w in self.all_words if w.end > start and w.start < end]

    def text_in_range(self, start: float, end: float) -> str:
        return " ".join(
            w.word for w in self.words_in_range(start, end)
        ).strip()


@dataclass
class ScoredWindow:
    start: float
    end: float
    score: float
    peak_words: list[str] = field(default_factory=list)
    hook_text: str = ""   # narration in first 5s, used for hook quality bonus

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class ClipSpec:
    """Everything needed to render a final Short from one approved footage asset."""
    source_path: Path
    footage_asset_id: str         # FK into footage_assets table
    start: float                  # clip start in seconds
    end: float                    # clip end in seconds
    score: float
    hook_text: str = ""
    transcript_words: list[WordTimestamp] = field(default_factory=list)
    language: str = "en"
    crop_x_pct: float = 0.5       # horizontal crop anchor: 0.0=left … 1.0=right

    @property
    def duration(self) -> float:
        return self.end - self.start
