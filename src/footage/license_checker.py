"""
Automated license inference from asset URLs.

Only two platforms get auto-inferred commercial approval because their license
is uniform across all content: Pixabay and Pexels.

Coverr is auto-inferred as commercial (proprietary free license).

Wikimedia Commons URLs return UNKNOWN — license varies per file and must be
verified individually (many photos are CC BY 2.0, but ShareAlike variants exist).

YouTube URLs always return HIGH-risk / NOT_APPROVED. Public availability,
watermarks, credit, and editing do NOT constitute permission.

All other URLs return UNKNOWN and must be verified manually.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.footage.models import LicenseType, ContentIDRisk


@dataclass
class LicenseCheckResult:
    license_type: LicenseType
    commercial_use: bool
    monetization_allowed: bool
    attribution_required: bool
    content_id_risk: ContentIDRisk
    confidence: str   # "high" | "medium" | "low" | "none"
    notes: str


_PIXABAY_NOTES = (
    "Pixabay Content License: uniform across all Pixabay videos. "
    "Commercial use, YouTube monetization, and modification all permitted. "
    "No attribution required. "
    "VERIFY on download: check for identifiable people, recognisable team kits, or logos — "
    "these require extra care under the license."
)

_PEXELS_NOTES = (
    "Pexels License: free for all commercial use including monetized YouTube. "
    "No attribution required. "
    "VERIFY on download: identifiable people must not appear in a bad light; "
    "content must not falsely imply endorsement."
)

_COVERR_NOTES = (
    "Coverr proprietary free license: commercial use and monetized YouTube permitted. "
    "No attribution required. No watermark."
)

_WIKIMEDIA_NOTES = (
    "Wikimedia Commons: license varies per file — must verify individually. "
    "Photos are often CC BY 2.0 (commercial ✓, attribution required). "
    "ShareAlike variants (CC BY-SA) complicate commercial video distribution. "
    "Never assume: read the license box on each file's Commons page."
)

_YOUTUBE_NOTES = (
    "YouTube Terms of Service govern this URL. "
    "Public availability, credit, watermarks, and editing do NOT grant reuse rights. "
    "Broadcasting rights for match footage are owned by FIFA, UEFA, leagues, and their "
    "licensees — not by the uploader. This asset cannot be used in production."
)


def check_url(url: str) -> LicenseCheckResult:
    """
    Infer license from URL structure alone — no network calls.
    Returns a LicenseCheckResult; confidence reflects how certain the inference is.
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path   = parsed.path.lower()
    except Exception:
        return _unknown("Could not parse URL.")

    # ── Pixabay ───────────────────────────────────────────────────────────────
    if "pixabay.com" in netloc:
        if "/videos/" in path:
            return LicenseCheckResult(
                license_type=LicenseType.PIXABAY_CONTENT_LICENSE,
                commercial_use=True,
                monetization_allowed=True,
                attribution_required=False,
                content_id_risk=ContentIDRisk.LOW,
                confidence="high",
                notes=_PIXABAY_NOTES,
            )
        # Images on Pixabay also carry the Content License
        return LicenseCheckResult(
            license_type=LicenseType.PIXABAY_CONTENT_LICENSE,
            commercial_use=True,
            monetization_allowed=True,
            attribution_required=False,
            content_id_risk=ContentIDRisk.LOW,
            confidence="high",
            notes=_PIXABAY_NOTES,
        )

    # ── Pexels ────────────────────────────────────────────────────────────────
    if "pexels.com" in netloc:
        return LicenseCheckResult(
            license_type=LicenseType.PEXELS_LICENSE,
            commercial_use=True,
            monetization_allowed=True,
            attribution_required=False,
            content_id_risk=ContentIDRisk.LOW,
            confidence="high",
            notes=_PEXELS_NOTES,
        )

    # ── Coverr ────────────────────────────────────────────────────────────────
    if "coverr.co" in netloc:
        return LicenseCheckResult(
            license_type=LicenseType.COVERR_LICENSE,
            commercial_use=True,
            monetization_allowed=True,
            attribution_required=False,
            content_id_risk=ContentIDRisk.LOW,
            confidence="high",
            notes=_COVERR_NOTES,
        )

    # ── Wikimedia Commons ─────────────────────────────────────────────────────
    if "commons.wikimedia.org" in netloc:
        return LicenseCheckResult(
            license_type=LicenseType.UNKNOWN,
            commercial_use=False,
            monetization_allowed=False,
            attribution_required=True,
            content_id_risk=ContentIDRisk.MEDIUM,
            confidence="low",
            notes=_WIKIMEDIA_NOTES,
        )

    # ── YouTube (hard block) ──────────────────────────────────────────────────
    if "youtube.com" in netloc or "youtu.be" in netloc:
        return LicenseCheckResult(
            license_type=LicenseType.YOUTUBE_TOS,
            commercial_use=False,
            monetization_allowed=False,
            attribution_required=False,
            content_id_risk=ContentIDRisk.HIGH,
            confidence="high",
            notes=_YOUTUBE_NOTES,
        )

    # ── Default ───────────────────────────────────────────────────────────────
    return _unknown(
        f"Source domain '{netloc}' has no automatic license rule. "
        "Verify the license manually and use the catalog CLI to register."
    )


def _unknown(notes: str) -> LicenseCheckResult:
    return LicenseCheckResult(
        license_type=LicenseType.UNKNOWN,
        commercial_use=False,
        monetization_allowed=False,
        attribution_required=False,
        content_id_risk=ContentIDRisk.UNKNOWN,
        confidence="none",
        notes=notes,
    )
