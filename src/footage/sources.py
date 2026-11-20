"""
Structured importers for each footage tier.

Each function validates that only the right defaults are set for that source
and returns a FootageAsset ready to pass to FootageCatalog.add_asset().

Nothing here downloads files or makes network calls.
Approval status is always NOT_APPROVED on creation; for Pixabay/Pexels/Coverr
the license is auto-inferred and the status is set to PENDING_REVIEW (license
is known, but the user must visually confirm no logos/identifiable people before
approving via the CLI).

Tier 1 — creator_authorized(): returns NOT_APPROVED; requires confirm_permission()
Tier 2 — stock_clip():         returns PENDING_REVIEW for known platforms, NOT_APPROVED otherwise
Tier 3 — ai_generated_clip():  returns PENDING_REVIEW; user must approve after reviewing output
"""
from __future__ import annotations

import uuid
from typing import Optional

from src.footage.license_checker import check_url
from src.footage.models import (
    ApprovalStatus,
    AssetTier,
    ContentIDRisk,
    FootageAsset,
    LicenseType,
    _ALWAYS_BLOCKED_LICENSES,
)

# Platforms whose licenses are uniform — auto-infer to PENDING_REVIEW
_AUTO_LICENSE_DOMAINS = {"pixabay.com", "pexels.com", "coverr.co"}

# AI tools that offer commercial rights on paid plans
_KNOWN_AI_TOOLS = {
    "kling":   "Kling AI — commercial use on Standard plan and above",
    "runway":  "Runway — commercial use on Standard plan and above",
    "pika":    "Pika Labs — commercial use on paid plan",
    "sora":    "OpenAI Sora — commercial use on paid plan",
    "hailuo":  "Hailuo AI — commercial use on paid plan",
}


def stock_clip(
    url: str,
    description: str,
    tags: Optional[list[str]] = None,
    creator_name: str = "",
    creator_url: str = "",
    duration_secs: Optional[float] = None,
    resolution: str = "",
    notes: str = "",
) -> FootageAsset:
    """
    Create a FootageAsset for a stock clip.
    License is auto-inferred from the URL for known platforms.
    Status is PENDING_REVIEW if the license was inferred, NOT_APPROVED otherwise.
    """
    result = check_url(url)

    if result.license_type in _ALWAYS_BLOCKED_LICENSES:
        raise ValueError(
            f"Cannot import asset from {url!r}: {result.notes}"
        )

    from urllib.parse import urlparse
    netloc = urlparse(url.lower()).netloc
    is_known = any(d in netloc for d in _AUTO_LICENSE_DOMAINS)
    status = ApprovalStatus.PENDING_REVIEW if is_known else ApprovalStatus.NOT_APPROVED

    return FootageAsset(
        id=str(uuid.uuid4()),
        asset_tier=AssetTier.STOCK_LICENSED,
        source_url=url,
        license_type=result.license_type,
        license_url="",
        permission_evidence=result.notes,
        commercial_use=result.commercial_use,
        monetization_allowed=result.monetization_allowed,
        attribution_required=result.attribution_required,
        modifications_allowed=True,
        approval_status=status,
        approval_reason=(
            "License auto-inferred from domain. "
            "Visually confirm: no identifiable people in a bad light, no club logos, no broadcast elements."
            if is_known else
            "Manual license verification required before approval."
        ),
        content_id_risk=result.content_id_risk,
        creator_name=creator_name,
        creator_url=creator_url,
        duration_secs=duration_secs,
        resolution=resolution,
        description=description,
        tags=tags or [],
        notes=notes,
    )


def creator_authorized(
    source_url: str,
    creator_name: str,
    creator_url: str,
    description: str,
    tags: Optional[list[str]] = None,
    notes: str = "",
) -> FootageAsset:
    """
    Register a footage asset that requires explicit creator permission.
    Always returns NOT_APPROVED until confirm_permission() is called.
    YouTube URLs are accepted here because we are recording the INTENT to request
    permission — the asset is blocked from production until actually approved.
    """
    return FootageAsset(
        id=str(uuid.uuid4()),
        asset_tier=AssetTier.CREATOR_AUTHORIZED,
        source_url=source_url,
        license_type=LicenseType.CREATOR_WRITTEN_PERMISSION,
        permission_evidence="",
        commercial_use=False,
        monetization_allowed=False,
        attribution_required=True,
        approval_status=ApprovalStatus.NOT_APPROVED,
        approval_reason="Written permission from creator not yet received.",
        content_id_risk=ContentIDRisk.HIGH,
        creator_name=creator_name,
        creator_url=creator_url,
        description=description,
        tags=tags or [],
        notes=notes,
    )


def ai_generated_clip(
    local_path: str,
    tool_name: str,
    plan_tier: str,
    prompt: str,
    duration_secs: float,
    resolution: str = "1080x1920",
    tags: Optional[list[str]] = None,
    notes: str = "",
) -> FootageAsset:
    """
    Register an AI-generated clip produced on a paid commercial plan.
    Returns PENDING_REVIEW — user must visually confirm quality and that no real
    player likenesses were generated before approving.

    tool_name: 'kling' | 'runway' | 'pika' | etc.
    plan_tier: the subscription tier used (e.g. 'standard', 'pro')
    prompt: the exact text prompt used to generate the clip
    """
    tool_lower = tool_name.lower()
    tool_evidence = _KNOWN_AI_TOOLS.get(tool_lower, f"{tool_name} — commercial rights on paid plan")

    evidence = (
        f"Generated by {tool_name} ({plan_tier} plan). "
        f"{tool_evidence}. "
        "Prompt: " + prompt[:500]
    )

    return FootageAsset(
        id=str(uuid.uuid4()),
        asset_tier=AssetTier.AI_GENERATED,
        source_url=f"ai://{tool_lower}/{str(uuid.uuid4())}",
        license_type=LicenseType.AI_COMMERCIAL,
        permission_evidence=evidence,
        commercial_use=True,
        monetization_allowed=True,
        attribution_required=False,
        modifications_allowed=True,
        approval_status=ApprovalStatus.PENDING_REVIEW,
        approval_reason=(
            "AI commercial plan recorded. "
            "Visually confirm: no identifiable real player faces, no brand logos, "
            "no broadcast elements. Toggle AI disclosure in YouTube Studio at upload."
        ),
        content_id_risk=ContentIDRisk.LOW,
        local_path=local_path,
        duration_secs=duration_secs,
        resolution=resolution,
        description=f"AI-generated clip. Prompt: {prompt[:200]}",
        tags=tags or [],
        notes=notes,
    )


def original_asset(
    local_path: str,
    description: str,
    tags: Optional[list[str]] = None,
    notes: str = "",
) -> FootageAsset:
    """
    Register a graphic or video produced entirely in-house (original work).
    Auto-approved — no third-party rights involved.
    """
    return FootageAsset(
        id=str(uuid.uuid4()),
        asset_tier=AssetTier.ORIGINAL,
        source_url=f"original://{local_path}",
        license_type=LicenseType.ORIGINAL_WORK,
        permission_evidence="Produced in-house by Beyond The Pitch. No third-party assets.",
        commercial_use=True,
        monetization_allowed=True,
        attribution_required=False,
        modifications_allowed=True,
        approval_status=ApprovalStatus.APPROVED,
        approval_reason="Original work — auto-approved.",
        content_id_risk=ContentIDRisk.LOW,
        local_path=local_path,
        description=description,
        tags=tags or [],
        notes=notes,
    )
