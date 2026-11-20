"""
Tests for the footage production gate.

The gate must raise FootageGateError for any asset that is:
  - NOT_APPROVED, PENDING_REVIEW, or REJECTED
  - approved but commercial_use = False
  - approved but monetization_allowed = False
  - approved but license is expired

The gate must pass only when all three conditions hold:
  approval_status == APPROVED AND commercial_use AND monetization_allowed
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

import src.core.database as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    orig = db_module.DB_PATH
    db_module.DB_PATH = tmp_path / "test_gate.db"
    db_module.init_db()
    yield
    db_module.DB_PATH = orig


from src.footage.catalog import FootageCatalog
from src.footage.gate import FootageGate, FootageGateError, assert_production_ready
from src.footage.models import ApprovalStatus, AssetTier, FootageAsset, LicenseType
from src.footage import sources


def _approved_asset() -> FootageAsset:
    asset = sources.stock_clip(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium aerial",
    )
    asset.approval_status = ApprovalStatus.APPROVED
    return asset


def _not_approved_asset() -> FootageAsset:
    asset = sources.stock_clip(
        url="https://pixabay.com/videos/football-training-evening-sport-205193/",
        description="Training evening",
    )
    # Leave as PENDING_REVIEW (default for Pixabay)
    return asset


# ── assert_production_ready ───────────────────────────────────────────────────

def test_approved_commercial_monetized_passes():
    asset = _approved_asset()
    assert_production_ready(asset)   # must not raise


def test_not_approved_raises():
    asset = _not_approved_asset()
    with pytest.raises(FootageGateError, match="(NOT_APPROVED|PENDING_REVIEW)"):
        assert_production_ready(asset)


def test_pending_review_raises():
    asset = sources.stock_clip(
        url="https://pixabay.com/videos/goalkeeper-soccer-sports-team-ball-10827/",
        description="Goalkeeper",
    )
    assert asset.approval_status == ApprovalStatus.PENDING_REVIEW
    with pytest.raises(FootageGateError):
        assert_production_ready(asset)


def test_rejected_raises():
    asset = _approved_asset()
    asset.approval_status = ApprovalStatus.REJECTED
    with pytest.raises(FootageGateError):
        assert_production_ready(asset)


def test_approved_but_no_commercial_use_raises():
    asset = _approved_asset()
    asset.commercial_use = False
    with pytest.raises(FootageGateError, match="commercial use"):
        assert_production_ready(asset)


def test_approved_but_no_monetization_raises():
    asset = _approved_asset()
    asset.monetization_allowed = False
    with pytest.raises(FootageGateError, match="monetization"):
        assert_production_ready(asset)


def test_expired_license_raises():
    asset = _approved_asset()
    past = (date.today() - timedelta(days=1)).isoformat()
    asset.expiry_date = past
    with pytest.raises(FootageGateError, match="expired"):
        assert_production_ready(asset)


def test_future_expiry_passes():
    asset = _approved_asset()
    future = (date.today() + timedelta(days=30)).isoformat()
    asset.expiry_date = future
    assert_production_ready(asset)   # must not raise


# ── FootageGate.check_all ─────────────────────────────────────────────────────

def test_gate_check_all_passes_when_all_approved():
    catalog = FootageCatalog()
    a1 = sources.stock_clip(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium",
    )
    a2 = sources.ai_generated_clip(
        local_path="/tmp/ai.mp4",
        tool_name="kling",
        plan_tier="standard",
        prompt="Penalty spot",
        duration_secs=5.0,
    )
    id1 = catalog.add_asset(a1)
    id2 = catalog.add_asset(a2)
    catalog.update_approval(id1, ApprovalStatus.APPROVED)
    catalog.update_approval(id2, ApprovalStatus.APPROVED)

    gate = FootageGate(catalog)
    gate.check_all([id1, id2])   # must not raise


def test_gate_check_all_raises_on_first_failure():
    catalog = FootageCatalog()
    a1 = sources.stock_clip(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium",
    )
    a2 = sources.stock_clip(
        url="https://pixabay.com/videos/football-training-evening-sport-205193/",
        description="Training",
    )
    id1 = catalog.add_asset(a1)
    id2 = catalog.add_asset(a2)
    catalog.update_approval(id1, ApprovalStatus.APPROVED)
    # a2 stays PENDING_REVIEW

    gate = FootageGate(catalog)
    with pytest.raises(FootageGateError):
        gate.check_all([id1, id2])


def test_gate_raises_for_unknown_asset_id():
    catalog = FootageCatalog()
    gate = FootageGate(catalog)
    with pytest.raises(FootageGateError, match="not found in footage catalog"):
        gate.check_all(["completely-nonexistent-id"])


def test_empty_asset_list_passes():
    catalog = FootageCatalog()
    gate = FootageGate(catalog)
    gate.check_all([])   # no assets = no problem


# ── YouTube URLs are always blocked from production ───────────────────────────

def test_youtube_sourced_asset_cannot_reach_approved_via_stock_import():
    """YouTube URLs must raise at import time — they never enter the catalog as stock."""
    with pytest.raises(ValueError):
        sources.stock_clip(
            url="https://www.youtube.com/watch?v=abc123",
            description="Trying to sneak in a YouTube clip",
        )
