"""
Beat detector: returns beat timestamps from an audio file.

No external dependencies beyond stdlib + numpy (which is already installed
for faster-whisper). Falls back to estimated tempo if audio analysis fails.

Algorithm:
  1. Load mono 22kHz PCM from WAV (extract via ffmpeg if given video)
  2. Compute RMS energy in 50ms windows (hop = 25ms)
  3. Onset detection: find frames where energy exceeds threshold × median
  4. Cluster onsets into beats using minimum inter-beat interval
  5. Return list of beat timestamps in seconds

Accuracy is sufficient for caption timing (±1 frame @ 30fps).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_SAMPLE_RATE   = 22050    # Hz — sufficient for beat detection
_HOP_MS        = 25       # ms between analysis windows
_WINDOW_MS     = 50       # ms RMS window
_ONSET_THRESH  = 1.8      # times median energy to count as onset
_MIN_BEAT_GAP  = 0.25     # seconds — minimum inter-beat interval (~240 BPM cap)
_DEFAULT_BPM   = 120.0    # fallback when audio too quiet or too short


def _extract_mono_wav(source: Path, out_wav: Path) -> None:
    ff = shutil.which("ffmpeg")
    if not ff:
        raise EnvironmentError("ffmpeg not found")
    subprocess.run(
        [ff, "-y", "-i", str(source),
         "-vn", "-ac", "1", "-ar", str(_SAMPLE_RATE), "-c:a", "pcm_s16le", str(out_wav)],
        capture_output=True, check=True,
    )


def _load_pcm(wav_path: Path) -> tuple[list[float], int]:
    """Return (samples_float32, sample_rate)."""
    import numpy as np  # noqa: PLC0415
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def _rms_energy(samples, sr: int) -> list[float]:
    """Return RMS energy for each hop window."""
    import numpy as np  # noqa: PLC0415
    hop    = max(1, int(sr * _HOP_MS  / 1000))
    window = max(1, int(sr * _WINDOW_MS / 1000))
    rms = []
    for i in range(0, len(samples) - window, hop):
        block = samples[i: i + window]
        rms.append(float(np.sqrt(np.mean(block ** 2))))
    return rms


def _pick_onsets(rms: list[float], hop_secs: float) -> list[float]:
    """Return beat timestamps via onset detection on RMS curve."""
    import numpy as np  # noqa: PLC0415
    if not rms:
        return []
    arr = np.array(rms)
    threshold = _ONSET_THRESH * float(np.median(arr[arr > 0])) if arr.any() else 0.0
    if threshold == 0.0:
        return []

    onsets: list[float] = []
    last_beat = -_MIN_BEAT_GAP
    for i, val in enumerate(arr):
        t = i * hop_secs
        if val >= threshold and t - last_beat >= _MIN_BEAT_GAP:
            # Require the value to be a local max over ±5 frames
            lo, hi = max(0, i - 5), min(len(arr), i + 6)
            if val == float(arr[lo:hi].max()):
                onsets.append(round(t, 3))
                last_beat = t
    return onsets


def _estimate_bpm(onsets: list[float]) -> float:
    if len(onsets) < 4:
        return _DEFAULT_BPM
    import numpy as np  # noqa: PLC0415
    gaps = np.diff(onsets)
    median_gap = float(np.median(gaps))
    if median_gap <= 0:
        return _DEFAULT_BPM
    return round(60.0 / median_gap, 1)


def detect_beats(source: Path) -> tuple[list[float], float]:
    """
    Analyse an audio or video file and return (beat_timestamps, estimated_bpm).

    Returns a fallback evenly-spaced grid if analysis fails.
    """
    source = Path(source)
    if not source.exists():
        logger.warning("beat_detect_missing_file", path=str(source))
        return _fallback_beats(60.0, _DEFAULT_BPM), _DEFAULT_BPM

    with tempfile.TemporaryDirectory(prefix="btp_beats_") as tmp:
        wav = Path(tmp) / "mono.wav"
        try:
            _extract_mono_wav(source, wav)
            samples, sr = _load_pcm(wav)
            rms = _rms_energy(samples, sr)
            hop_secs = _HOP_MS / 1000.0
            beats = _pick_onsets(rms, hop_secs)
            bpm = _estimate_bpm(beats)
            if len(beats) < 3:
                # Too quiet (crowd noise only) — fall back to estimated grid
                logger.info("beat_detect_fallback_grid", reason="too_few_onsets", bpm=bpm)
                duration = len(samples) / sr
                return _fallback_beats(duration, bpm), bpm
            logger.info("beat_detect_done", beats=len(beats), bpm=bpm)
            return beats, bpm
        except Exception as exc:
            logger.warning("beat_detect_failed", error=str(exc))
            return _fallback_beats(30.0, _DEFAULT_BPM), _DEFAULT_BPM


def _fallback_beats(duration: float, bpm: float) -> list[float]:
    """Return evenly-spaced beat grid for given duration and BPM."""
    interval = 60.0 / bpm
    beats = []
    t = 0.0
    while t < duration:
        beats.append(round(t, 3))
        t += interval
    return beats


def snap_to_beat(timestamp: float, beats: list[float], window: float = 0.1) -> float:
    """
    Snap a timestamp to the nearest beat within `window` seconds.
    Returns the original timestamp if no beat is within the window.
    """
    if not beats:
        return timestamp
    nearest = min(beats, key=lambda b: abs(b - timestamp))
    if abs(nearest - timestamp) <= window:
        return nearest
    return timestamp
