"""
Footage catalog: persistent three-tier footage sourcing for Beyond The Pitch.

Tier 1 — CREATOR_AUTHORIZED  : explicit written permission from a YouTube creator
Tier 2 — STOCK_LICENSED      : commercially licensed stock clips (Pixabay, Pexels, Coverr)
Tier 3 — AI_GENERATED        : clips generated on a paid AI plan (Kling, Runway)
Tier 4 — ORIGINAL            : graphics and content produced in-house

Hard rule: an asset's approval_status must be APPROVED, commercial_use must be True,
and monetization_allowed must be True before it can enter video production.
Public YouTube availability, watermarks, credit, or editing do NOT grant any rights.
"""
from src.footage.models import (
    FootageAsset,
    AssetTier,
    LicenseType,
    ApprovalStatus,
    ContentIDRisk,
)
from src.footage.gate import FootageGate, FootageGateError
from src.footage.catalog import FootageCatalog

__all__ = [
    "FootageAsset",
    "AssetTier",
    "LicenseType",
    "ApprovalStatus",
    "ContentIDRisk",
    "FootageGate",
    "FootageGateError",
    "FootageCatalog",
]
