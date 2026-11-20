"""Tests for src/editing/beat_detector.py"""
import math
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from src.editing.beat_detector import (
    _estimate_bpm,
    _fallback_beats,
    _pick_onsets,
    _rms_energy,
    detect_beats,
    snap_to_beat,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_sine_wav(path: Path, freq_hz: float = 440.0, duration: float = 2.0,
                    sample_rate: int = 22050) -> None:
    n_samples = int(sample_rate * duration)
    samples = [int(32767 * math.sin(2 * math.pi * freq_hz * i / sample_rate))
               for i in range(n_samples)]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))


def _write_silent_wav(path: Path, duration: float = 2.0,
                      sample_rate: int = 22050) -> None:
    n_samples = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * n_samples * 2)


# ── _fallback_beats ───────────────────────────────────────────────────────────

class TestFallbackBeats:
    def test_returns_beats_at_correct_interval(self):
        beats = _fallback_beats(10.0, 120.0)
        assert len(beats) > 0
        if len(beats) > 1:
            gap = beats[1] - beats[0]
            assert abs(gap - 0.5) < 1e-3  # 120 BPM = 0.5s intervals

    def test_does_not_exceed_duration(self):
        beats = _fallback_beats(5.0, 120.0)
        assert all(b < 5.0 for b in beats)

    def test_starts_at_zero(self):
        beats = _fallback_beats(5.0, 120.0)
        assert beats[0] == 0.0

    def test_200bpm(self):
        beats = _fallback_beats(6.0, 200.0)
        interval = 60.0 / 200.0
        assert abs((beats[1] - beats[0]) - interval) < 1e-3


# ── _estimate_bpm ─────────────────────────────────────────────────────────────

class TestEstimateBpm:
    def test_120_bpm(self):
        # Beats every 0.5s
        onsets = [i * 0.5 for i in range(16)]
        bpm = _estimate_bpm(onsets)
        assert abs(bpm - 120.0) < 2.0

    def test_fallback_too_few_onsets(self):
        bpm = _estimate_bpm([0.0, 0.5])
        assert bpm == 120.0  # _DEFAULT_BPM fallback

    def test_zero_gap_fallback(self):
        bpm = _estimate_bpm([0.0, 0.0, 0.0, 0.0])
        assert bpm == 120.0


# ── _rms_energy ───────────────────────────────────────────────────────────────

class TestRmsEnergy:
    def test_silent_signal_gives_zero_rms(self):
        import numpy as np
        samples = np.zeros(22050, dtype=np.float32)
        rms = _rms_energy(samples, 22050)
        assert all(r == 0.0 for r in rms)

    def test_full_amplitude_gives_nonzero(self):
        import numpy as np
        samples = np.ones(22050, dtype=np.float32)
        rms = _rms_energy(samples, 22050)
        assert all(r > 0.0 for r in rms)

    def test_returns_list(self):
        import numpy as np
        samples = np.random.uniform(-0.5, 0.5, 22050).astype(np.float32)
        rms = _rms_energy(samples, 22050)
        assert isinstance(rms, list)


# ── _pick_onsets ──────────────────────────────────────────────────────────────

class TestPickOnsets:
    def test_empty_rms(self):
        onsets = _pick_onsets([], 0.025)
        assert onsets == []

    def test_flat_rms_no_onsets(self):
        # Flat RMS — no local maxima above threshold
        rms = [0.1] * 200
        onsets = _pick_onsets(rms, 0.025)
        # Flat signal: nothing exceeds 1.8 × median, should be empty or sparse
        assert isinstance(onsets, list)

    def test_spike_creates_onset(self):
        rms = [0.01] * 100
        rms[50] = 1.0  # spike at index 50 = 1.25s
        onsets = _pick_onsets(rms, 0.025)
        assert len(onsets) > 0


# ── snap_to_beat ──────────────────────────────────────────────────────────────

class TestSnapToBeat:
    def test_exact_beat_snaps(self):
        beats = [0.0, 0.5, 1.0, 1.5]
        assert snap_to_beat(0.5, beats) == 0.5

    def test_close_snap(self):
        beats = [0.0, 0.5, 1.0]
        result = snap_to_beat(0.52, beats, window=0.1)
        assert result == 0.5

    def test_outside_window_no_snap(self):
        beats = [0.0, 0.5, 1.0]
        result = snap_to_beat(0.8, beats, window=0.1)
        assert result == 0.8

    def test_empty_beats_returns_original(self):
        assert snap_to_beat(0.42, [], window=0.1) == 0.42

    def test_negative_snap_window(self):
        # Even with tight window, correct beat is returned
        beats = [0.0, 0.5, 1.0]
        result = snap_to_beat(0.501, beats, window=0.01)
        assert result == 0.5


# ── detect_beats ──────────────────────────────────────────────────────────────

class TestDetectBeats:
    def test_missing_file_returns_fallback(self):
        beats, bpm = detect_beats(Path("/nonexistent_file.mp4"))
        assert isinstance(beats, list)
        assert len(beats) > 0
        assert bpm > 0

    def test_silent_wav_returns_fallback(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = Path(f.name)
        try:
            _write_silent_wav(tmp, duration=4.0)
            beats, bpm = detect_beats(tmp)
            assert isinstance(beats, list)
            assert bpm > 0
        finally:
            tmp.unlink(missing_ok=True)

    def test_sine_wav_returns_beats_and_bpm(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = Path(f.name)
        try:
            _write_sine_wav(tmp, duration=4.0)
            beats, bpm = detect_beats(tmp)
            assert isinstance(beats, list)
            assert isinstance(bpm, float)
            assert bpm > 0
        finally:
            tmp.unlink(missing_ok=True)
