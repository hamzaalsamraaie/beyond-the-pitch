"""
Data models for the footage catalog.

ApprovalStatus defaults to NOT_APPROVED for every new asset.
An asset must be explicitly set to APPROVED — it can never self-approve.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AssetTier(str, Enum):
    CREATOR_AUTHORIZED = "CREATOR_AUTHORIZED"
    STOCK_LICENSED     = "STOCK_LICENSED"
    AI_GENERATED       = "AI_GENERATED"
    ORIGINAL           = "ORIGINAL"


class LicenseType(str, Enum):
    # Stock platforms with uniform commercial licenses
    PIXABAY_CONTENT_LICENSE = "PIXABAY_CONTENT_LICENSE"
    PEXELS_LICENSE          = "PEXELS_LICENSE"
    COVERR_LICENSE          = "COVERR_LICENSE"
    STORYBLOCKS             = "STORYBLOCKS"

    # Creative Commons
    CC_BY_2_0  = "CC_BY_2_0"
    CC_BY_3_0  = "CC_BY_3_0"
    CC_BY_4_0  = "CC_BY_4_0"
    CC_BY_SA_2_0 = "CC_BY_SA_2_0"   # ShareAlike — caution for commercial video
    CC_BY_SA_4_0 = "CC_BY_SA_4_0"
    CC0        = "CC0"

    # Other
    AI_COMMERCIAL              = "AI_COMMERCIAL"           # paid AI tool plan
    CREATOR_WRITTEN_PERMISSION = "CREATOR_WRITTEN_PERMISSION"
    ORIGINAL_WORK              = "ORIGINAL_WORK"

    # Hard block
    YOUTUBE_TOS = "YOUTUBE_TOS"   # never valid for commercial reuse
    UNKNOWN     = "UNKNOWN"


class ApprovalStatus(str, Enum):
    NOT_APPROVED   = "NOT_APPROVED"    # default — rights unverified
    PENDING_REVIEW = "PENDING_REVIEW"  # verification submitted but not confirmed
    APPROVED       = "APPROVED"        # explicitly verified, may enter production
    REJECTED       = "REJECTED"        # rights unavailable or refused


class ContentIDRisk(str, Enum):
    LOW     = "LOW"      # original / AI-generated / public domain
    MEDIUM  = "MEDIUM"   # CC-licensed, possible third-party elements
    HIGH    = "HIGH"     # broadcast footage, match clips, any real match content
    UNKNOWN = "UNKNOWN"


# Licenses that may never be auto-approved for commercial monetized use
_ALWAYS_BLOCKED_LICENSES: frozenset[LicenseType] = frozenset({
    LicenseType.YOUTUBE_TOS,
    LicenseType.UNKNOWN,
})

# Licenses where ShareAlike complicates commercial video distribution
_SHARE_ALIKE_LICENSES: frozenset[LicenseType] = frozenset({
    LicenseType.CC_BY_SA_2_0,
    LicenseType.CC_BY_SA_4_0,
})


@dataclass
class FootageAsset:
    id: str
    asset_tier: AssetTier
    source_url: str

    # License
    license_type: LicenseType   = LicenseType.UNKNOWN
    license_url: str            = ""
    permission_evidence: str    = ""  # quote or reference proving rights

    # Permitted uses — must be True to pass the production gate
    commercial_use: bool        = False
    monetization_allowed: bool  = False  # specifically: YouTube Partner Program
    attribution_required: bool  = False
    attribution_text: str       = ""
    modifications_allowed: bool = True
    expiry_date: Optional[str]  = None   # ISO date string; None = no expiry

    # Approval
    approval_status: ApprovalStatus = ApprovalStatus.NOT_APPROVED
    approval_reason: str            = ""

    # Risk
    content_id_risk: ContentIDRisk = ContentIDRisk.UNKNOWN

    # Creator / source
    creator_name: str = ""
    creator_url: str  = ""

    # File
    local_path: str           = ""
    file_hash: str            = ""    # SHA256 of downloaded file
    duration_secs: Optional[float] = None
    resolution: str           = ""

    # Metadata
    description: str       = ""
    tags: list[str]        = field(default_factory=list)
    notes: str             = ""
    created_at: str        = ""
    updated_at: str        = ""

    def is_production_ready(self) -> bool:
        """True only when all three conditions for the hard gate are met."""
        return (
            self.approval_status == ApprovalStatus.APPROVED
            and self.commercial_use
            and self.monetization_allowed
        )

    def has_share_alike(self) -> bool:
        return self.license_type in _SHARE_ALIKE_LICENSES

    def tags_as_json(self) -> str:
        return json.dumps(self.tags)

    @staticmethod
    def tags_from_json(raw: str) -> list[str]:
        try:
            return json.loads(raw) if raw else []
        except Exception:
            return []
