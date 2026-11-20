"""
Tests for the footage catalog: CRUD, duplicate detection, approval workflow,
and permission request tracking.

All tests use a fresh in-memory / temp SQLite DB — the production DB is never touched.
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

import src.core.database as db_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Redirect the DB to a fresh temp file for every test."""
    db_path = tmp_path / "test_footage.db"
    orig = db_module.DB_PATH
    db_module.DB_PATH = db_path
    db_module.init_db()
    yield db_path
    db_module.DB_PATH = orig


from src.footage.catalog import FootageCatalog
from src.footage.models import (
    ApprovalStatus,
    AssetTier,
    ContentIDRisk,
    FootageAsset,
    LicenseType,
)
from src.footage import sources


def _pixabay_asset(**kwargs) -> FootageAsset:
    defaults = dict(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium aerial",
        tags=["stadium", "football"],
    )
    defaults.update(kwargs)
    return sources.stock_clip(**defaults)


# ── Add and retrieve ──────────────────────────────────────────────────────────

def test_add_and_get_asset():
    catalog = FootageCatalog()
    asset = _pixabay_asset()
    asset_id = catalog.add_asset(asset)
    retrieved = catalog.get_asset(asset_id)

    assert retrieved is not None
    assert retrieved.id == asset_id
    assert retrieved.asset_tier == AssetTier.STOCK_LICENSED
    assert retrieved.license_type == LicenseType.PIXABAY_CONTENT_LICENSE
    assert retrieved.description == "Stadium aerial"
    assert "stadium" in retrieved.tags


def test_get_nonexistent_returns_none():
    catalog = FootageCatalog()
    assert catalog.get_asset("nonexistent-id") is None


# ── Default approval status ───────────────────────────────────────────────────

def test_stock_clip_defaults_to_pending_review_for_known_domains():
    asset = _pixabay_asset()
    assert asset.approval_status == ApprovalStatus.PENDING_REVIEW
    assert asset.commercial_use is True
    assert asset.monetization_allowed is True


def test_creator_authorized_defaults_to_not_approved():
    asset = sources.creator_authorized(
        source_url="https://youtube.com/watch?v=abc",
        creator_name="Football Stories",
        creator_url="https://youtube.com/@FootballStories",
        description="Documentary",
    )
    assert asset.approval_status == ApprovalStatus.NOT_APPROVED
    assert asset.commercial_use is False
    assert asset.monetization_allowed is False


def test_ai_generated_defaults_to_pending_review():
    asset = sources.ai_generated_clip(
        local_path="/tmp/test.mp4",
        tool_name="kling",
        plan_tier="standard",
        prompt="Penalty spot at night",
        duration_secs=5.0,
    )
    assert asset.approval_status == ApprovalStatus.PENDING_REVIEW
    assert asset.commercial_use is True
    assert asset.monetization_allowed is True


def test_original_asset_auto_approved():
    asset = sources.original_asset(
        local_path="/tmp/graphic.png",
        description="Original motion graphic",
    )
    assert asset.approval_status == ApprovalStatus.APPROVED
    assert asset.is_production_ready()


# ── Duplicate detection ───────────────────────────────────────────────────────

def test_duplicate_url_raises():
    catalog = FootageCatalog()
    asset = _pixabay_asset()
    catalog.add_asset(asset)

    with pytest.raises(ValueError, match="Duplicate detected"):
        duplicate = _pixabay_asset()
        catalog.add_asset(duplicate)


def test_duplicate_url_case_insensitive():
    catalog = FootageCatalog()
    asset = _pixabay_asset(url="https://PIXABAY.COM/videos/soccer-sports-event-stadium-arena-8502/")
    catalog.add_asset(asset)

    with pytest.raises(ValueError, match="Duplicate detected"):
        # Same URL, different case
        dup = _pixabay_asset(url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/")
        catalog.add_asset(dup)


def test_different_urls_allowed():
    catalog = FootageCatalog()
    a1 = sources.stock_clip(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium 1",
    )
    a2 = sources.stock_clip(
        url="https://pixabay.com/videos/football-training-evening-sport-205193/",
        description="Training evening",
    )
    id1 = catalog.add_asset(a1)
    id2 = catalog.add_asset(a2)
    assert id1 != id2


def test_find_duplicate_returns_none_when_absent():
    catalog = FootageCatalog()
    result = catalog.find_duplicate("https://pixabay.com/videos/nonexistent-99999/")
    assert result is None


# ── Approval update ───────────────────────────────────────────────────────────

def test_approve_asset():
    catalog = FootageCatalog()
    asset = _pixabay_asset()
    asset_id = catalog.add_asset(asset)

    catalog.update_approval(asset_id, ApprovalStatus.APPROVED, reason="Visual check passed")
    updated = catalog.get_asset(asset_id)

    assert updated.approval_status == ApprovalStatus.APPROVED
    assert updated.approval_reason == "Visual check passed"


def test_reject_asset():
    catalog = FootageCatalog()
    asset = _pixabay_asset()
    asset_id = catalog.add_asset(asset)

    catalog.update_approval(asset_id, ApprovalStatus.REJECTED, reason="Contains club logo")
    updated = catalog.get_asset(asset_id)
    assert updated.approval_status == ApprovalStatus.REJECTED


def test_is_production_ready_only_after_full_approval():
    catalog = FootageCatalog()
    asset = _pixabay_asset()
    asset_id = catalog.add_asset(asset)

    pending = catalog.get_asset(asset_id)
    assert not pending.is_production_ready()

    catalog.update_approval(asset_id, ApprovalStatus.APPROVED)
    approved = catalog.get_asset(asset_id)
    assert approved.is_production_ready()


# ── List and filter ───────────────────────────────────────────────────────────

def test_list_all():
    catalog = FootageCatalog()
    catalog.add_asset(_pixabay_asset(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/"
    ))
    catalog.add_asset(_pixabay_asset(
        url="https://pixabay.com/videos/football-training-evening-sport-205193/"
    ))
    assert len(catalog.list_assets()) == 2


def test_list_filter_by_tier():
    catalog = FootageCatalog()
    catalog.add_asset(_pixabay_asset(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/"
    ))
    ai = sources.ai_generated_clip(
        local_path="/tmp/ai_clip.mp4",
        tool_name="kling",
        plan_tier="standard",
        prompt="Penalty spot test",
        duration_secs=5.0,
    )
    catalog.add_asset(ai)

    stock_only = catalog.list_assets(tier=AssetTier.STOCK_LICENSED)
    ai_only = catalog.list_assets(tier=AssetTier.AI_GENERATED)
    assert len(stock_only) == 1
    assert len(ai_only) == 1


def test_list_filter_by_status():
    catalog = FootageCatalog()
    a1 = _pixabay_asset(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/"
    )
    a2 = _pixabay_asset(
        url="https://pixabay.com/videos/football-training-evening-sport-205193/"
    )
    id1 = catalog.add_asset(a1)
    catalog.add_asset(a2)

    catalog.update_approval(id1, ApprovalStatus.APPROVED)

    approved = catalog.list_assets(status=ApprovalStatus.APPROVED)
    pending = catalog.list_assets(status=ApprovalStatus.PENDING_REVIEW)
    assert len(approved) == 1
    assert len(pending) == 1


# ── Permission requests ───────────────────────────────────────────────────────

def test_permission_request_workflow():
    catalog = FootageCatalog()

    # Register the asset as creator_authorized (NOT_APPROVED by default)
    asset = sources.creator_authorized(
        source_url="https://youtube.com/watch?v=abc123",
        creator_name="Football Stories",
        creator_url="https://youtube.com/@FootballStories",
        description="Documentary",
    )
    asset_id = catalog.add_asset(asset)
    assert catalog.get_asset(asset_id).approval_status == ApprovalStatus.NOT_APPROVED

    # Create permission request
    req_id = catalog.create_permission_request(
        creator_name="Football Stories",
        creator_url="https://youtube.com/@FootballStories",
        request_method="email",
    )
    assert req_id

    # Confirm receipt of written permission
    catalog.confirm_permission(
        request_id=req_id,
        evidence_text="Yes, you have permission to use clips from this video for Beyond The Pitch.",
        asset_ids=[asset_id],
    )

    approved = catalog.get_asset(asset_id)
    assert approved.approval_status == ApprovalStatus.APPROVED
    assert approved.commercial_use is True
    assert approved.monetization_allowed is True
    assert req_id in approved.permission_evidence


def test_list_permission_requests():
    catalog = FootageCatalog()
    catalog.create_permission_request("Creator A", "https://youtube.com/@A", "email")
    catalog.create_permission_request("Creator B", "https://youtube.com/@B", "dm_youtube")
    rows = catalog.list_permission_requests()
    assert len(rows) == 2


# ── YouTube URLs are hard-blocked from stock import ──────────────────────────

def test_youtube_url_raises_on_stock_import():
    with pytest.raises(ValueError, match="Cannot import asset"):
        sources.stock_clip(
            url="https://www.youtube.com/watch?v=SOME_VIDEO",
            description="Attempting to import a YouTube video as stock",
        )


# ── Tags round-trip ───────────────────────────────────────────────────────────

def test_tags_persist_correctly():
    catalog = FootageCatalog()
    asset = sources.stock_clip(
        url="https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/",
        description="Stadium",
        tags=["stadium", "night", "crowd", "football"],
    )
    asset_id = catalog.add_asset(asset)
    retrieved = catalog.get_asset(asset_id)
    assert retrieved.tags == ["stadium", "night", "crowd", "football"]
