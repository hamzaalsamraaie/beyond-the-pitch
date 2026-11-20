"""
Video/audio transcription with word-level timestamps.

BaseTranscriber (ABC)
  └─ FasterWhisperTranscriber  — local CPU inference, word timestamps
                                  requires: pip install faster-whisper
  └─ MockTranscriber            — deterministic fixture output, zero cost

FasterWhisperTranscriber automatically downloads a Whisper model on first use
and caches it in ~/.cache/huggingface. No API key required.

Recommended model for speed/quality on Mac CPU: "base.en" or "small.en".
For highest quality: "medium.en" (slower, ~2-3 min for 10-min video on M2).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path

from src.clipping.models import Transcript, TranscriptSegment, WordTimestamp
from src.core.logger import get_logger

logger = get_logger(__name__)

_WHISPER_DEFAULT_MODEL = "base.en"


# ── Helper: extract audio ─────────────────────────────────────────────────────

def _extract_audio(video_path: Path, out_wav: Path) -> None:
    """Extract mono 16 kHz WAV from a video file — Whisper's preferred format."""
    ff = shutil.which("ffmpeg")
    if not ff:
        raise EnvironmentError("ffmpeg not found on PATH")
    result = subprocess.run(
        [
            ff, "-y", "-i", str(video_path),
            "-vn",                    # no video
            "-ac", "1",               # mono
            "-ar", "16000",           # 16 kHz
            "-c:a", "pcm_s16le",
            str(out_wav),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed:\n{result.stderr[-400:]}")


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseTranscriber(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def transcribe(self, video_path: Path) -> Transcript:
        """
        Transcribe a video or audio file.
        Returns a Transcript with word-level timestamps.
        """
        ...


# ── faster-whisper transcriber ────────────────────────────────────────────────

class FasterWhisperTranscriber(BaseTranscriber):
    """
    Local transcription using faster-whisper (CTranslate2-optimised Whisper).
    Downloads model on first use (~150 MB for base.en).

    Installation: pip install faster-whisper
    """

    def __init__(self, model_size: str = _WHISPER_DEFAULT_MODEL) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
        except ImportError as exc:
            raise EnvironmentError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper  "
                "BLOCKER: transcription unavailable without this package."
            ) from exc

        self._model_size = model_size
        logger.info("whisper_model_load", model=model_size, device="cpu")
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("whisper_model_ready", model=model_size)

    @property
    def name(self) -> str:
        return f"faster_whisper_{self._model_size}"

    def transcribe(self, video_path: Path) -> Transcript:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        with tempfile.TemporaryDirectory(prefix="btp_transcribe_") as tmp:
            audio_path = Path(tmp) / "audio.wav"
            logger.info("transcribe_extract_audio", source=video_path.name)
            _extract_audio(video_path, audio_path)

            logger.info("transcribe_start", model=self._model_size, audio=audio_path.name)
            # Load WAV as numpy float32 to bypass av.open() API changes.
            import numpy as np  # noqa: PLC0415
            with wave.open(str(audio_path), "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            audio_array = (
                np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            )
            segments_iter, info = self._model.transcribe(
                audio_array,
                word_timestamps=True,
                language="en",
                beam_size=5,
            )
            language = info.language
            source_duration = info.duration

            transcript_segments: list[TranscriptSegment] = []
            for seg in segments_iter:
                words: list[WordTimestamp] = []
                if seg.words:
                    for w in seg.words:
                        words.append(WordTimestamp(
                            start=round(w.start, 3),
                            end=round(w.end, 3),
                            word=w.word,
                        ))
                transcript_segments.append(TranscriptSegment(
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=seg.text.strip(),
                    words=words,
                ))

        logger.info(
            "transcribe_done",
            segments=len(transcript_segments),
            language=language,
            duration=round(source_duration, 1),
        )
        return Transcript(
            segments=transcript_segments,
            language=language,
            source_duration=source_duration,
        )


# ── Mock transcriber ──────────────────────────────────────────────────────────

_MOCK_TEXT_FOOTBALL = (
    "What an incredible moment here at the stadium. "
    "The crowd is on its feet as the player drives forward. "
    "An unbelievable run through the defence. "
    "He shoots and it hits the back of the net! "
    "What a goal! Absolutely sensational. "
    "The goalkeeper had no chance. "
    "This is the stuff of legends. "
    "Brilliant skill from start to finish. "
    "The world class finishing we have come to expect. "
    "History is being made tonight."
)


def _build_mock_words(text: str, start_offset: float = 0.0) -> list[WordTimestamp]:
    """Build plausible word timestamps from text at ~3 wps."""
    words: list[WordTimestamp] = []
    t = start_offset
    for word in text.split():
        duration = max(0.15, len(word) * 0.065 + 0.12)
        words.append(WordTimestamp(start=round(t, 3), end=round(t + duration, 3), word=word))
        t += duration + 0.05
    return words


class MockTranscriber(BaseTranscriber):
    """
    Returns deterministic fixture transcript for testing.
    No audio extraction, no network, zero cost.
    """

    def __init__(self, mock_text: str | None = None, mock_duration: float = 60.0) -> None:
        self._text = mock_text or _MOCK_TEXT_FOOTBALL
        self._duration = mock_duration

    @property
    def name(self) -> str:
        return "mock"

    def transcribe(self, video_path: Path) -> Transcript:
        words = _build_mock_words(self._text)
        end_t = words[-1].end if words else self._duration

        # Split into ~4-word segments
        segments: list[TranscriptSegment] = []
        chunk: list[WordTimestamp] = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 4 or w.word.endswith((".", "!", "?")):
                segments.append(TranscriptSegment(
                    start=chunk[0].start,
                    end=chunk[-1].end,
                    text=" ".join(cw.word for cw in chunk).strip(),
                    words=list(chunk),
                ))
                chunk = []
        if chunk:
            segments.append(TranscriptSegment(
                start=chunk[0].start,
                end=chunk[-1].end,
                text=" ".join(cw.word for cw in chunk).strip(),
                words=list(chunk),
            ))

        return Transcript(
            segments=segments,
            language="en",
            source_duration=max(end_t, self._duration),
        )


# ── Factory ───────────────────────────────────────────────────────────────────

def get_transcriber(override: str | None = None) -> BaseTranscriber:
    """
    Return the best available transcriber.
    Falls back: faster_whisper → mock (logs a blocker warning).
    """
    name = override or "faster_whisper"
    if name == "mock":
        return MockTranscriber()
    try:
        return FasterWhisperTranscriber()
    except EnvironmentError as exc:
        logger.warning(
            "transcriber_unavailable",
            reason=str(exc),
            fallback="mock",
            blocker=(
                "BLOCKER: Install faster-whisper to enable real transcription. "
                "pip install faster-whisper"
            ),
        )
        return MockTranscriber()
