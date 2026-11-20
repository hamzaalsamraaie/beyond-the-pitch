"""
Tests for the license checker URL inference.
"""
from src.footage.license_checker import check_url
from src.footage.models import ContentIDRisk, LicenseType


def test_pixabay_video_inferred_commercial():
    r = check_url("https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/")
    assert r.license_type == LicenseType.PIXABAY_CONTENT_LICENSE
    assert r.commercial_use is True
    assert r.monetization_allowed is True
    assert r.attribution_required is False
    assert r.content_id_risk == ContentIDRisk.LOW
    assert r.confidence == "high"


def test_pexels_video_inferred_commercial():
    r = check_url("https://www.pexels.com/video/football-stadium-12345/")
    assert r.license_type == LicenseType.PEXELS_LICENSE
    assert r.commercial_use is True
    assert r.monetization_allowed is True
    assert r.confidence == "high"


def test_coverr_inferred_commercial():
    r = check_url("https://coverr.co/videos/football-stadium")
    assert r.license_type == LicenseType.COVERR_LICENSE
    assert r.commercial_use is True
    assert r.monetization_allowed is True


def test_youtube_always_blocked():
    for url in [
        "https://www.youtube.com/watch?v=abc123",
        "https://youtu.be/abc123",
        "https://youtube.com/shorts/abc123",
    ]:
        r = check_url(url)
        assert r.license_type == LicenseType.YOUTUBE_TOS
        assert r.commercial_use is False
        assert r.monetization_allowed is False
        assert r.content_id_risk == ContentIDRisk.HIGH
        assert r.confidence == "high"


def test_wikimedia_returns_unknown_low_confidence():
    r = check_url("https://commons.wikimedia.org/wiki/File:Marco_Materazzi_flickr.jpg")
    assert r.license_type == LicenseType.UNKNOWN
    assert r.commercial_use is False
    assert r.confidence == "low"
    assert r.content_id_risk == ContentIDRisk.MEDIUM


def test_unknown_domain_returns_unknown():
    r = check_url("https://example.com/some-video.mp4")
    assert r.license_type == LicenseType.UNKNOWN
    assert r.commercial_use is False
    assert r.confidence == "none"


def test_malformed_url_returns_unknown():
    r = check_url("not_a_url_at_all")
    assert r.license_type == LicenseType.UNKNOWN
    assert r.commercial_use is False
