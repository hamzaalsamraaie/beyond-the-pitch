"""Tests for the asset manifest."""

import tempfile
from pathlib import Path

import pytest

from src.video.assets import AssetEntry, AssetManifest


def _fresh_manifest() -> AssetManifest:
    tmp = tempfile.mktemp(suffix="_manifest.json")
    return AssetManifest(manifest_path=Path(tmp))


def test_manifest_seeds_builtin_assets():
    m = _fresh_manifest()
    assert m.get("font_impact") is not None
    assert m.get("bg_generated_gradient") is not None
    assert m.get("audio_silence") is not None


def test_manifest_font_path_exists():
    m = _fresh_manifest()
    path = m.get_font_path("font_impact")
    assert path.exists()


def test_manifest_permitted_check():
    m = _fresh_manifest()
    assert m.verify_permitted("font_impact", "commercial") is True
    assert m.verify_permitted("font_impact", "broadcast") is True


def test_manifest_macos_tts_not_commercial():
    m = _fresh_manifest()
    entry = m.get("audio_macos_tts")
    assert entry is not None
    assert "commercial" not in entry.permitted_uses


def test_manifest_register_custom_asset():
    m = _fresh_manifest()
    custom = AssetEntry(
        asset_id="test_asset",
        asset_type="image",
        name="Test Image",
        source_url="https://example.com/image.png",
        license="CC0",
        permitted_uses=["commercial", "educational"],
        attribution_required=False,
        authorization_evidence="CC0 license verified.",
    )
    m.register(custom)
    assert m.get("test_asset") is not None
    assert m.verify_permitted("test_asset", "commercial") is True


def test_manifest_all_entries_have_evidence():
    m = _fresh_manifest()
    for entry in m.all_entries():
        assert entry.authorization_evidence, (
            f"Asset '{entry.asset_id}' has no authorization_evidence"
        )


def test_manifest_get_nonexistent_returns_none():
    m = _fresh_manifest()
    assert m.get("does_not_exist") is None


def test_manifest_get_nonexistent_font_raises():
    m = _fresh_manifest()
    with pytest.raises(KeyError):
        m.get_font_path("does_not_exist")
