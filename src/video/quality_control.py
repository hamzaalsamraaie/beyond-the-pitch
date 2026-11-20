"""
Quality control: verify rendered MP4 files using ffprobe.

Returns a QCResult with pass/fail and a human-readable report.
All checks are non-destructive. The file is never modified.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.core.config import get_section
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QCResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    measured_duration_secs: float = 0.0
    measured_width: int = 0
    measured_height: int = 0
    file_size_bytes: int = 0
    has_audio: bool = False
    codec_name: str = ""

    def report(self) -> str:
        lines = [
            f"QC {'PASSED' if self.passed else 'FAILED'}",
            f"  Duration:   {self.measured_duration_secs:.2f}s",
            f"  Resolution: {self.measured_width}x{self.measured_height}",
            f"  Codec:      {self.codec_name}",
            f"  Audio:      {'yes' if self.has_audio else 'NO'}",
            f"  File size:  {self.file_size_bytes:,} bytes",
        ]
        if self.failures:
            lines.append("  FAILURES:")
            for f in self.failures:
                lines.append(f"    ✗ {f}")
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")
        return "\n".join(lines)


def _ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise EnvironmentError("ffprobe not found on PATH")
    return path


def _probe(video_path: Path) -> dict:
    """Run ffprobe and return parsed JSON."""
    result = subprocess.run(
        [
            _ffprobe(), "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:300]}")
    return json.loads(result.stdout)


def run_qc(
    video_path: Path,
    expected_duration_secs: float,
    tts_provider: str = "mock",
) -> QCResult:
    """
    Run all quality checks on video_path.
    expected_duration_secs is the storyboard total_duration.
    """
    cfg = get_section("production")
    max_tol = cfg.get("qc_max_duration_tolerance_secs", 2.0)
    min_size = cfg.get("qc_min_file_size_bytes", 10_000)
    max_size_mb = cfg.get("qc_max_file_size_mb", 500)

    result = QCResult(passed=False)
    failures: list[str] = []
    warnings: list[str] = []

    # ── File exists and is non-empty ──────────────────────────────────────────
    if not video_path.exists():
        result.failures = [f"Output file does not exist: {video_path}"]
        return result

    result.file_size_bytes = video_path.stat().st_size
    if result.file_size_bytes < min_size:
        failures.append(
            f"File too small: {result.file_size_bytes} bytes (min {min_size})"
        )
    if result.file_size_bytes > max_size_mb * 1024 * 1024:
        failures.append(
            f"File too large: {result.file_size_bytes // (1024*1024)} MB (max {max_size_mb} MB)"
        )

    # ── Probe streams ─────────────────────────────────────────────────────────
    try:
        probe = _probe(video_path)
    except RuntimeError as exc:
        result.failures = [str(exc)]
        return result

    streams = probe.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # ── Video stream ──────────────────────────────────────────────────────────
    if not video_stream:
        failures.append("No video stream found")
    else:
        result.measured_width = video_stream.get("width", 0)
        result.measured_height = video_stream.get("height", 0)
        result.codec_name = video_stream.get("codec_name", "unknown")
        result.measured_duration_secs = float(
            video_stream.get("duration") or probe.get("format", {}).get("duration", 0)
        )

        if result.measured_width != 1080:
            failures.append(f"Width is {result.measured_width}, expected 1080")
        if result.measured_height != 1920:
            failures.append(f"Height is {result.measured_height}, expected 1920")
        if result.codec_name not in ("h264", "hevc", "av1"):
            failures.append(f"Unexpected codec: {result.codec_name}")

        duration_diff = abs(result.measured_duration_secs - expected_duration_secs)
        if duration_diff > max_tol:
            failures.append(
                f"Duration mismatch: got {result.measured_duration_secs:.2f}s, "
                f"expected {expected_duration_secs:.2f}s "
                f"(tolerance ±{max_tol}s)"
            )

    # ── Audio stream ──────────────────────────────────────────────────────────
    if not audio_stream:
        if tts_provider == "mock":
            warnings.append(
                "No audio stream. Mock TTS generates silence; "
                "verify FFmpeg included it correctly."
            )
        else:
            failures.append("No audio stream found")
        result.has_audio = False
    else:
        result.has_audio = True
        audio_codec = audio_stream.get("codec_name", "")
        if audio_codec not in ("aac", "mp3", "opus", "pcm_s16le", "pcm_s16be"):
            warnings.append(f"Unusual audio codec: {audio_codec}")

    result.failures = failures
    result.warnings = warnings
    result.passed = len(failures) == 0

    logger.info(
        "qc_complete",
        passed=result.passed,
        failures=len(failures),
        warnings=len(warnings),
        path=video_path.name,
    )
    return result
