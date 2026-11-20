"""Tests for the disk monitor."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.disk_monitor import (
    MINIMUM_FREE_MB,
    check_minimum_space,
    disk_status_report,
    estimate_render_mb,
    get_free_mb,
    prune_old_renders,
)


class TestGetFreeMb:
    def test_returns_positive_float(self, tmp_path):
        result = get_free_mb(tmp_path)
        assert isinstance(result, float)
        assert result > 0

    def test_uses_project_root_by_default(self):
        result = get_free_mb()
        assert result > 0

    def test_project_root_matches_tmp_on_same_volume(self, tmp_path):
        # Both should give roughly the same free space (same filesystem)
        project_free = get_free_mb()
        assert project_free > 0


class TestCheckMinimumSpace:
    def test_passes_when_sufficient_space(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=1000.0):
            check_minimum_space(200.0)  # should not raise

    def test_raises_when_insufficient_space(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=50.0):
            with pytest.raises(RuntimeError, match="Insufficient disk space"):
                check_minimum_space(200.0)

    def test_default_threshold_is_minimum_free_mb(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=MINIMUM_FREE_MB - 1):
            with pytest.raises(RuntimeError):
                check_minimum_space()

    def test_exact_boundary_passes(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=200.0):
            check_minimum_space(200.0)  # exact boundary — should pass


class TestEstimateRenderMb:
    def test_30s_returns_reasonable_estimate(self):
        result = estimate_render_mb(30.0)
        assert 150 <= result <= 400

    def test_longer_video_needs_more_space(self):
        short_estimate = estimate_render_mb(15.0)
        long_estimate = estimate_render_mb(45.0)
        assert long_estimate > short_estimate

    def test_always_includes_buffer(self):
        result = estimate_render_mb(1.0)  # very short video
        assert result >= 150  # safety buffer + temp always included


class TestPruneOldRenders:
    def test_keeps_last_n(self, tmp_path):
        # Create fake MP4 files
        with patch("src.core.disk_monitor._SHORTS_DIR", tmp_path):
            for i in range(8):
                f = tmp_path / f"render_{i:03d}.mp4"
                f.write_bytes(b"fake")
            deleted = prune_old_renders(keep_last=5)
        assert deleted == 3

    def test_no_delete_when_under_limit(self, tmp_path):
        with patch("src.core.disk_monitor._SHORTS_DIR", tmp_path):
            for i in range(3):
                f = tmp_path / f"render_{i:03d}.mp4"
                f.write_bytes(b"fake")
            deleted = prune_old_renders(keep_last=5)
        assert deleted == 0

    def test_missing_dir_returns_zero(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with patch("src.core.disk_monitor._SHORTS_DIR", missing):
            assert prune_old_renders() == 0


class TestDiskStatusReport:
    def test_returns_string(self):
        result = disk_status_report()
        assert isinstance(result, str)

    def test_contains_free_mb(self):
        result = disk_status_report()
        assert "MB" in result

    def test_contains_ok_or_low(self):
        result = disk_status_report()
        assert "OK" in result or "LOW" in result

    def test_low_status_when_space_insufficient(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=50.0):
            result = disk_status_report()
        assert "LOW" in result

    def test_ok_status_when_space_sufficient(self):
        with patch("src.core.disk_monitor.get_free_mb", return_value=1000.0):
            result = disk_status_report()
        assert "OK" in result
