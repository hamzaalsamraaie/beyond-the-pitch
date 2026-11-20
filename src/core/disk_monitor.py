"""
Disk space monitoring and cleanup.

Before any render starts, call require_space() to prevent half-rendered files
from filling the last bytes of disk.

Recommended minimums:
  - 200 MB to start any render (1 video + temp files)
  - 500 MB comfortable headroom for 3 slots/day
  - 1 GB+ for unattended overnight operation
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SHORTS_DIR = _PROJECT_ROOT / "output" / "shorts"

# Measured average MP4 output size for a 30s Short at CRF 22
_ESTIMATED_OUTPUT_MB = 45
# Temp files during render (work copy + norm copy + thumbnail)
_ESTIMATED_TEMP_MB = 60
# Safety buffer
_SAFETY_BUFFER_MB = 100

MINIMUM_FREE_MB = _ESTIMATED_OUTPUT_MB + _ESTIMATED_TEMP_MB + _SAFETY_BUFFER_MB  # 205 MB


def get_free_mb(path: Path | None = None) -> float:
    """Return free disk space in MB at the given path (default: project root)."""
    target = path or _PROJECT_ROOT
    usage = shutil.disk_usage(str(target))
    return usage.free / (1024 * 1024)


def check_minimum_space(required_mb: float = MINIMUM_FREE_MB, path: Path | None = None) -> None:
    """
    Raise RuntimeError if free disk space is below required_mb.
    Call this before starting any render.
    """
    free = get_free_mb(path)
    if free < required_mb:
        raise RuntimeError(
            f"Insufficient disk space: {free:.0f} MB free, need {required_mb:.0f} MB. "
            "Free up space before rendering: brew cleanup, clear ~/Downloads, "
            "remove old renders with: python scripts/cleanup.py"
        )
    logger.debug("disk_space_ok", free_mb=round(free), required_mb=required_mb)


def estimate_render_mb(duration_secs: float) -> float:
    """Rough estimate of disk space needed for a render of this duration."""
    per_second = _ESTIMATED_OUTPUT_MB / 30.0
    output = per_second * duration_secs
    return output + _ESTIMATED_TEMP_MB + _SAFETY_BUFFER_MB


def prune_old_renders(keep_last: int = 5) -> int:
    """
    Delete the oldest render MP4 files in output/shorts/ beyond keep_last.
    Returns number of files deleted. Never deletes footage assets.
    """
    if not _SHORTS_DIR.exists():
        return 0
    mp4s = sorted(_SHORTS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    to_delete = mp4s[:-keep_last] if len(mp4s) > keep_last else []
    for path in to_delete:
        try:
            path.unlink()
            logger.info("pruned_render", path=path.name)
        except Exception as exc:
            logger.warning("prune_failed", path=path.name, error=str(exc))
    return len(to_delete)


def disk_status_report() -> str:
    """Return a one-line disk status string for logging and reports."""
    free = get_free_mb()
    mp4s = list(_SHORTS_DIR.glob("*.mp4")) if _SHORTS_DIR.exists() else []
    status = "OK" if free >= MINIMUM_FREE_MB else "LOW"
    return (
        f"Disk: {free:.0f} MB free [{status}] | "
        f"Renders kept: {len(mp4s)} | "
        f"Minimum required: {MINIMUM_FREE_MB} MB"
    )
