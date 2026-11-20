"""
Hard production gate for footage assets.

assert_production_ready() raises FootageGateError if an asset is not fully
cleared. It is called by the production pipeline before any clip is composited
into a video. It cannot be bypassed without raising an exception.

Nothing in this module ever approves an asset — it only checks.
"""
from __future__ import annotations

from src.footage.models import ApprovalStatus, FootageAsset


class FootageGateError(RuntimeError):
    """Raised when an asset fails the production gate check."""


def assert_production_ready(asset: FootageAsset) -> None:
    """
    Raise FootageGateError unless the asset is fully cleared for commercial
    monetized production.

    Three conditions must ALL be true:
      1. approval_status == APPROVED
      2. commercial_use == True
      3. monetization_allowed == True

    Public YouTube availability, watermarks, credit, and editing never satisfy
    any of these conditions.
    """
    if asset.approval_status != ApprovalStatus.APPROVED:
        raise FootageGateError(
            f"Asset '{asset.id}' is {asset.approval_status.value}, not APPROVED. "
            f"Reason: {asset.approval_reason or 'none recorded'}. "
            "Set approval_status to APPROVED only after verifying commercial rights."
        )

    if not asset.commercial_use:
        raise FootageGateError(
            f"Asset '{asset.id}' (license: {asset.license_type.value}) "
            "does not permit commercial use."
        )

    if not asset.monetization_allowed:
        raise FootageGateError(
            f"Asset '{asset.id}' (license: {asset.license_type.value}) "
            "is not cleared for YouTube monetization."
        )

    if asset.expiry_date:
        from datetime import date
        today = date.today().isoformat()
        if today > asset.expiry_date:
            raise FootageGateError(
                f"Asset '{asset.id}' license expired on {asset.expiry_date}. "
                "Renew the license or remove the asset from production."
            )


class FootageGate:
    """
    Gate that checks a list of asset IDs against the catalog before production.
    Raises FootageGateError on the first unapproved asset found.
    """

    def __init__(self, catalog: "FootageCatalog") -> None:  # type: ignore[name-defined]
        self._catalog = catalog

    def check_all(self, asset_ids: list[str]) -> None:
        """
        Verify every asset_id in the list is production-ready.
        Raises FootageGateError for the first failure encountered.
        Raises KeyError if an asset_id is not found in the catalog.
        """
        for asset_id in asset_ids:
            asset = self._catalog.get_asset(asset_id)
            if asset is None:
                raise FootageGateError(
                    f"Asset ID '{asset_id}' not found in footage catalog. "
                    "Register it before including it in a production plan."
                )
            assert_production_ready(asset)
