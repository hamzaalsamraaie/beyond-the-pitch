"""
Text-to-speech providers.

BaseTTSProvider (ABC)
  └─ MockTTSProvider     — silent WAV at exact duration; zero cost, offline, used in all tests
  └─ MacOSTTSProvider    — macOS built-in `say` command; free, offline, natural voice
  └─ OpenAITTSProvider   — OpenAI tts-1-hd; high quality, commercially licensed on paid plans
                           Requires OPENAI_API_KEY in environment.

TTS output is always a WAV at 44100 Hz stereo.
Duration of the output is guaranteed to match target_duration_secs (padded or trimmed).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from src.core.config import get_section
from src.core.logger import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2


@dataclass
class TTSResult:
    audio_path: Path
    duration_secs: float
    provider: str
    word_count: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise EnvironmentError("ffmpeg not found on PATH")
    return path


def _ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise EnvironmentError("ffprobe not found on PATH")
    return path


def _probe_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    result = _run([
        _ffprobe(), "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(audio_path),
    ])
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    return 0.0


def measure_natural_tts_duration(text: str, voice: str = "Samantha") -> float:
    """
    Synthesize text with macOS 'say' and return the natural spoken duration in seconds.
    Returns 0.0 if 'say' is unavailable. Does not write any persistent file.
    """
    if not shutil.which("say"):
        return 0.0
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "measure.aiff"
        result = subprocess.run(
            ["say", "-v", voice, "-o", str(aiff), text],
            capture_output=True,
        )
        if result.returncode != 0 or not aiff.exists():
            return 0.0
        return _probe_duration(aiff)


def _pad_or_trim(audio_path: Path, target: float, out_path: Path) -> None:
    """
    Pad with silence or trim audio to exactly `target` seconds.
    Overwrites out_path.
    """
    actual = _probe_duration(audio_path)
    if abs(actual - target) < 0.05:
        if audio_path != out_path:
            shutil.copy(audio_path, out_path)
        return

    ff = _ffmpeg()
    if actual < target:
        # Pad: use apad filter to reach exactly target seconds
        result = _run([
            ff, "-y", "-i", str(audio_path),
            "-filter_complex",
            f"apad=pad_dur={target - actual}",
            "-t", str(target),
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-c:a", "pcm_s16le",
            str(out_path),
        ])
    else:
        # Trim
        result = _run([
            ff, "-y", "-i", str(audio_path),
            "-t", str(target),
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-c:a", "pcm_s16le",
            str(out_path),
        ])
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg pad/trim failed: {result.stderr[-400:]}")


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseTTSProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def synthesize(
        self,
        text: str,
        target_duration_secs: float,
        output_path: Path,
    ) -> TTSResult:
        """
        Synthesize `text` as speech and write a WAV to `output_path`.
        The output must be exactly `target_duration_secs` long (padded or trimmed).
        """
        ...


# ── Mock provider ─────────────────────────────────────────────────────────────

class MockTTSProvider(BaseTTSProvider):
    """
    Generates silent WAV audio of exactly target_duration_secs.
    Zero cost, no network, no install required.
    Used in all automated tests.
    """

    @property
    def name(self) -> str:
        return "mock"

    def synthesize(
        self,
        text: str,
        target_duration_secs: float,
        output_path: Path,
    ) -> TTSResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = _run([
            _ffmpeg(), "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo",
            "-t", str(target_duration_secs),
            "-c:a", "pcm_s16le",
            str(output_path),
        ])
        if result.returncode != 0:
            raise RuntimeError(f"MockTTS ffmpeg failed: {result.stderr[-300:]}")
        word_count = len(text.split())
        logger.info(
            "tts_mock",
            duration=target_duration_secs,
            words=word_count,
            output=output_path.name,
        )
        return TTSResult(
            audio_path=output_path,
            duration_secs=target_duration_secs,
            provider="mock",
            word_count=word_count,
        )


# ── macOS provider ─────────────────────────────────────────────────────────────

class MacOSTTSProvider(BaseTTSProvider):
    """
    Uses the macOS built-in `say` command to generate speech.
    Free, offline, no API key required.
    Default voice is Samantha (configure in settings.yaml production.macos_tts_voice).

    Note on commercial use: Apple's TTS is intended for personal/educational use.
    Verify Apple's terms before using macOS TTS audio in monetized content.
    """

    def __init__(self) -> None:
        if not shutil.which("say"):
            raise EnvironmentError(
                "macOS 'say' command not found. MacOSTTSProvider requires macOS."
            )
        cfg = get_section("production")
        self._voice: str = cfg.get("macos_tts_voice", "Samantha")

    @property
    def name(self) -> str:
        return "macos"

    def synthesize(
        self,
        text: str,
        target_duration_secs: float,
        output_path: Path,
    ) -> TTSResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        aiff_path = output_path.with_suffix(".aiff")
        raw_wav = output_path.with_stem(output_path.stem + "_raw")

        # 1. macOS say → AIFF
        result = subprocess.run(
            ["say", "-v", self._voice, "-o", str(aiff_path), text],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"macOS say failed: {result.stderr[:300]}")

        # 2. AIFF → WAV
        result = _run([
            _ffmpeg(), "-y", "-i", str(aiff_path),
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-c:a", "pcm_s16le",
            str(raw_wav),
        ])
        if result.returncode != 0:
            raise RuntimeError(f"AIFF→WAV conversion failed: {result.stderr[-300:]}")

        # 3. Report fit quality before pad/trim so callers can audit narration length
        natural = _probe_duration(raw_wav)
        fit_ratio = natural / target_duration_secs if target_duration_secs > 0 else 1.0
        if fit_ratio > 1.10:
            logger.warning(
                "tts_macos_narration_too_long",
                natural_secs=round(natural, 2),
                target_secs=target_duration_secs,
                overshoot_pct=round((fit_ratio - 1) * 100, 1),
                note="Audio will be trimmed — words at the end may be cut off",
            )
        elif fit_ratio < 0.60:
            logger.info(
                "tts_macos_narration_short",
                natural_secs=round(natural, 2),
                target_secs=target_duration_secs,
                undershoot_pct=round((1 - fit_ratio) * 100, 1),
                note="Silence padding will fill remaining scene time",
            )
        else:
            logger.info(
                "tts_macos_fit_ok",
                natural_secs=round(natural, 2),
                target_secs=target_duration_secs,
                padding_secs=round(target_duration_secs - natural, 2),
            )

        # 4. Pad or trim to exact target duration
        _pad_or_trim(raw_wav, target_duration_secs, output_path)

        # Cleanup intermediates
        aiff_path.unlink(missing_ok=True)
        if raw_wav != output_path:
            raw_wav.unlink(missing_ok=True)

        word_count = len(text.split())
        logger.info(
            "tts_macos",
            voice=self._voice,
            duration=target_duration_secs,
            words=word_count,
            output=output_path.name,
        )
        return TTSResult(
            audio_path=output_path,
            duration_secs=target_duration_secs,
            provider="macos",
            word_count=word_count,
        )


# ── OpenAI TTS provider ───────────────────────────────────────────────────────

class OpenAITTSProvider(BaseTTSProvider):
    """
    Uses the OpenAI tts-1-hd model for high-quality speech synthesis.
    Output is commercially licensed on paid OpenAI API plans.
    Requires OPENAI_API_KEY in environment.

    Voices: alloy, echo, fable, onyx, nova, shimmer
    Recommended for Beyond The Pitch: onyx (deep, authoritative).
    """

    def __init__(self, voice: str = "onyx") -> None:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Add it to .env, or use MacOSTTSProvider / MockTTSProvider."
            )
        self._client = openai.OpenAI(api_key=api_key)
        self._voice = voice

    @property
    def name(self) -> str:
        return f"openai_{self._voice}"

    def synthesize(
        self,
        text: str,
        target_duration_secs: float,
        output_path: Path,
    ) -> TTSResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # OpenAI TTS → MP3 stream
        mp3_path = output_path.with_suffix(".mp3")
        with self._client.audio.speech.with_streaming_response.create(
            model="tts-1-hd",
            voice=self._voice,
            input=text,
        ) as response:
            response.stream_to_file(mp3_path)

        # MP3 → WAV
        raw_wav = output_path.with_stem(output_path.stem + "_raw")
        result = _run([
            _ffmpeg(), "-y", "-i", str(mp3_path),
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-c:a", "pcm_s16le",
            str(raw_wav),
        ])
        mp3_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(f"OpenAI TTS MP3→WAV failed: {result.stderr[-300:]}")

        # Pad/trim to exact target duration
        _pad_or_trim(raw_wav, target_duration_secs, output_path)
        if raw_wav.resolve() != output_path.resolve():
            raw_wav.unlink(missing_ok=True)

        word_count = len(text.split())
        logger.info(
            "tts_openai",
            voice=self._voice,
            duration=target_duration_secs,
            words=word_count,
            output=output_path.name,
        )
        return TTSResult(
            audio_path=output_path,
            duration_secs=target_duration_secs,
            provider=self.name,
            word_count=word_count,
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_tts_provider(override: str | None = None) -> BaseTTSProvider:
    """
    Return a TTS provider based on settings or override string.
    Falls back gracefully: openai → macos → mock.
    """
    provider_name = override or get_section("production").get("tts_provider", "mock")

    if provider_name == "openai":
        try:
            return OpenAITTSProvider()
        except EnvironmentError as exc:
            logger.warning("tts_openai_unavailable", reason=str(exc), fallback="macos")
            provider_name = "macos"

    if provider_name == "macos":
        try:
            return MacOSTTSProvider()
        except EnvironmentError as exc:
            logger.warning("tts_macos_unavailable", reason=str(exc), fallback="mock")
            return MockTTSProvider()

    return MockTTSProvider()
