"""Tests for TTS providers. All tests use MockTTSProvider — zero cost, offline."""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.video.tts import MockTTSProvider, TTSResult, _probe_duration, measure_natural_tts_duration

_HAS_SAY = shutil.which("say") is not None


def test_mock_tts_creates_wav_file():
    provider = MockTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.wav"
        result = provider.synthesize("Hello world", 5.0, out)
        assert out.exists()
        assert out.stat().st_size > 0
        assert isinstance(result, TTSResult)
        assert result.provider == "mock"


def test_mock_tts_duration_matches_target():
    provider = MockTTSProvider()
    for target_secs in [3.0, 7.5, 15.0, 20.0]:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            result = provider.synthesize("Some text here", target_secs, out)
            assert result.duration_secs == target_secs
            measured = _probe_duration(out)
            assert abs(measured - target_secs) < 0.1, (
                f"Target {target_secs}s but measured {measured:.3f}s"
            )


def test_mock_tts_word_count():
    provider = MockTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.wav"
        result = provider.synthesize("One two three four five", 5.0, out)
        assert result.word_count == 5


def test_mock_tts_creates_parent_dirs():
    provider = MockTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "nested" / "dirs" / "out.wav"
        provider.synthesize("Test", 2.0, out)
        assert out.exists()


def test_mock_tts_stereo_audio():
    """Verify mock output is stereo (2 channels) at 44100 Hz."""
    import json, subprocess
    provider = MockTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.wav"
        provider.synthesize("Test audio", 3.0, out)
        ffprobe = shutil.which("ffprobe")
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", str(out)],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        audio = next(s for s in data["streams"] if s["codec_type"] == "audio")
        assert int(audio["channels"]) == 2
        assert int(audio["sample_rate"]) == 44100


# ── macOS TTS tests (skipped when 'say' is unavailable) ───────────────────────

@pytest.mark.skipif(not _HAS_SAY, reason="macOS 'say' command not available")
def test_macos_tts_creates_wav_file():
    from src.video.tts import MacOSTTSProvider
    provider = MacOSTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.wav"
        result = provider.synthesize("Hello world.", 5.0, out)
        assert out.exists()
        assert out.stat().st_size > 0
        assert result.provider == "macos"
        assert result.duration_secs == 5.0


@pytest.mark.skipif(not _HAS_SAY, reason="macOS 'say' command not available")
def test_macos_tts_duration_matches_target():
    from src.video.tts import MacOSTTSProvider
    provider = MacOSTTSProvider()
    for target in [5.0, 10.0]:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            provider.synthesize("One two three four five.", target, out)
            measured = _probe_duration(out)
            assert abs(measured - target) < 0.1, (
                f"Target {target}s but measured {measured:.3f}s"
            )


@pytest.mark.skipif(not _HAS_SAY, reason="macOS 'say' command not available")
def test_macos_tts_natural_duration_is_shorter_than_generous_budget():
    """Natural speech for a short sentence should be well under a 30s budget."""
    duration = measure_natural_tts_duration("Hello. This is a test sentence.", voice="Samantha")
    assert 0.5 < duration < 10.0, f"Unexpected natural duration: {duration}s"


@pytest.mark.skipif(not _HAS_SAY, reason="macOS 'say' command not available")
def test_macos_tts_stereo_44100():
    import json, subprocess
    from src.video.tts import MacOSTTSProvider
    provider = MacOSTTSProvider()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.wav"
        provider.synthesize("Football is beautiful.", 4.0, out)
        ffprobe = shutil.which("ffprobe")
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", str(out)],
            capture_output=True, text=True,
        )
        data = json.loads(r.stdout)
        audio = next(s for s in data["streams"] if s["codec_type"] == "audio")
        assert int(audio["channels"]) == 2
        assert int(audio["sample_rate"]) == 44100
