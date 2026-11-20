"""
FootageCatalog: SQLite-backed CRUD for footage assets and permission requests.

Duplicate detection:
  - By source_url (exact match, case-insensitive)
  - By file_hash (SHA256) if the file has been downloaded locally

The catalog never approves anything automatically. Approval is a human action
performed via the CLI (footage_catalog.py approve) or the confirm_permission()
method for creator-authorised content.
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import src.core.database as db_module
from src.core.logger import get_logger
from src.footage.models import (
    ApprovalStatus,
    AssetTier,
    ContentIDRisk,
    FootageAsset,
    LicenseType,
)

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_asset(row: sqlite3.Row) -> FootageAsset:
    return FootageAsset(
        id=row["id"],
        asset_tier=AssetTier(row["asset_tier"]),
        source_url=row["source_url"],
        license_type=LicenseType(row["license_type"]),
        license_url=row["license_url"] or "",
        permission_evidence=row["permission_evidence"] or "",
        commercial_use=bool(row["commercial_use"]),
        monetization_allowed=bool(row["monetization_allowed"]),
        attribution_required=bool(row["attribution_required"]),
        attribution_text=row["attribution_text"] or "",
        modifications_allowed=bool(row["modifications_allowed"]),
        expiry_date=row["expiry_date"],
        approval_status=ApprovalStatus(row["approval_status"]),
        approval_reason=row["approval_reason"] or "",
        content_id_risk=ContentIDRisk(row["content_id_risk"]),
        creator_name=row["creator_name"] or "",
        creator_url=row["creator_url"] or "",
        local_path=row["local_path"] or "",
        file_hash=row["file_hash"] or "",
        duration_secs=row["duration_secs"],
        resolution=row["resolution"] or "",
        description=row["description"] or "",
        tags=FootageAsset.tags_from_json(row["tags"] or "[]"),
        notes=row["notes"] or "",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


class FootageCatalog:
    """
    Thread-safe (WAL mode) footage asset catalog backed by the project SQLite DB.
    Pass db_path to override the default for testing.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is not None:
            self._orig_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
        self._db_path = db_module.DB_PATH
        db_module.init_db()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_asset(self, asset: FootageAsset) -> str:
        """
        Insert a new footage asset.  Returns its ID.
        Raises ValueError if a duplicate URL or file_hash already exists.
        """
        existing_id = self.find_duplicate(asset.source_url, asset.file_hash)
        if existing_id:
            raise ValueError(
                f"Duplicate detected: asset already registered as '{existing_id}'. "
                "Use get_asset() to retrieve it."
            )

        now = _now()
        asset_id = asset.id or str(uuid.uuid4())
        with db_module._connect() as conn:
            conn.execute(
                """INSERT INTO footage_assets
                   (id, asset_tier, source_url, license_type, license_url,
                    permission_evidence, commercial_use, monetization_allowed,
                    attribution_required, attribution_text, modifications_allowed,
                    expiry_date, approval_status, approval_reason, content_id_risk,
                    creator_name, creator_url, local_path, file_hash,
                    duration_secs, resolution, description, tags, notes,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    asset_id,
                    asset.asset_tier.value,
                    asset.source_url.strip().lower(),
                    asset.license_type.value,
                    asset.license_url,
                    asset.permission_evidence,
                    int(asset.commercial_use),
                    int(asset.monetization_allowed),
                    int(asset.attribution_required),
                    asset.attribution_text,
                    int(asset.modifications_allowed),
                    asset.expiry_date,
                    asset.approval_status.value,
                    asset.approval_reason,
                    asset.content_id_risk.value,
                    asset.creator_name,
                    asset.creator_url,
                    asset.local_path,
                    asset.file_hash,
                    asset.duration_secs,
                    asset.resolution,
                    asset.description,
                    asset.tags_as_json(),
                    asset.notes,
                    now,
                    now,
                ),
            )
        logger.info("footage_asset_added", id=asset_id,
                    tier=asset.asset_tier.value, license=asset.license_type.value,
                    approval=asset.approval_status.value)
        return asset_id

    def get_asset(self, asset_id: str) -> Optional[FootageAsset]:
        with db_module._connect() as conn:
            row = conn.execute(
                "SELECT * FROM footage_assets WHERE id = ?", (asset_id,)
            ).fetchone()
        return _row_to_asset(row) if row else None

    def list_assets(
        self,
        tier: Optional[AssetTier] = None,
        status: Optional[ApprovalStatus] = None,
    ) -> list[FootageAsset]:
        query = "SELECT * FROM footage_assets WHERE 1=1"
        params: list = []
        if tier:
            query += " AND asset_tier = ?"
            params.append(tier.value)
        if status:
            query += " AND approval_status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC"
        with db_module._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_asset(r) for r in rows]

    def update_approval(
        self,
        asset_id: str,
        status: ApprovalStatus,
        reason: str = "",
    ) -> None:
        """Set the approval status of an asset. Logs the change."""
        with db_module._connect() as conn:
            conn.execute(
                """UPDATE footage_assets
                   SET approval_status = ?, approval_reason = ?, updated_at = ?
                   WHERE id = ?""",
                (status.value, reason, _now(), asset_id),
            )
        logger.info("footage_asset_approval_updated",
                    id=asset_id, status=status.value, reason=reason)

    def update_local_path(self, asset_id: str, local_path: str) -> None:
        """Record the local file path after a clip has been downloaded."""
        file_hash = ""
        p = Path(local_path)
        if p.exists():
            file_hash = _sha256(p)
        with db_module._connect() as conn:
            conn.execute(
                """UPDATE footage_assets
                   SET local_path = ?, file_hash = ?, updated_at = ?
                   WHERE id = ?""",
                (local_path, file_hash, _now(), asset_id),
            )

    # ── Duplicate detection ───────────────────────────────────────────────────

    def find_duplicate(self, url: str, file_hash: str = "") -> Optional[str]:
        """
        Return the existing asset ID if a duplicate is found by URL or file hash.
        Returns None if no duplicate exists.
        """
        norm_url = url.strip().lower()
        with db_module._connect() as conn:
            row = conn.execute(
                "SELECT id FROM footage_assets WHERE source_url = ?", (norm_url,)
            ).fetchone()
            if row:
                return row["id"]
            if file_hash:
                row = conn.execute(
                    "SELECT id FROM footage_assets WHERE file_hash = ? AND file_hash != ''",
                    (file_hash,),
                ).fetchone()
                if row:
                    return row["id"]
        return None

    # ── Permission requests (Tier 1) ──────────────────────────────────────────

    def create_permission_request(
        self,
        creator_name: str,
        creator_url: str,
        channel_id: str = "",
        request_method: str = "email",
    ) -> str:
        """
        Record that a permission request will be sent to a creator.
        Does NOT send anything — the user sends the request manually.
        Returns the request ID.
        """
        req_id = str(uuid.uuid4())
        with db_module._connect() as conn:
            conn.execute(
                """INSERT INTO permission_requests
                   (id, creator_name, creator_url, channel_id, request_method, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (req_id, creator_name, creator_url, channel_id, request_method, _now()),
            )
        logger.info("permission_request_created",
                    id=req_id, creator=creator_name, method=request_method)
        return req_id

    def confirm_permission(
        self,
        request_id: str,
        evidence_text: str,
        asset_ids: Optional[list[str]] = None,
    ) -> None:
        """
        Record that written permission was received from a creator.
        evidence_text must be a quote or reference from the creator's reply.
        Updates related footage_assets to APPROVED.
        """
        import json as _json
        asset_ids = asset_ids or []
        with db_module._connect() as conn:
            conn.execute(
                """UPDATE permission_requests
                   SET response_status = 'approved',
                       response_received_at = ?,
                       evidence_text = ?,
                       footage_asset_ids = ?
                   WHERE id = ?""",
                (
                    _now(),
                    evidence_text,
                    _json.dumps(asset_ids),
                    request_id,
                ),
            )
            for aid in asset_ids:
                conn.execute(
                    """UPDATE footage_assets
                       SET approval_status = ?, permission_evidence = ?,
                           commercial_use = 1, monetization_allowed = 1,
                           updated_at = ?
                       WHERE id = ?""",
                    (
                        ApprovalStatus.APPROVED.value,
                        f"Creator written permission — request {request_id}: {evidence_text[:200]}",
                        _now(),
                        aid,
                    ),
                )
        logger.info("permission_confirmed",
                    request_id=request_id, assets_approved=len(asset_ids))

    def get_permission_request(self, request_id: str) -> Optional[sqlite3.Row]:
        with db_module._connect() as conn:
            return conn.execute(
                "SELECT * FROM permission_requests WHERE id = ?", (request_id,)
            ).fetchone()

    def list_permission_requests(self) -> list[sqlite3.Row]:
        with db_module._connect() as conn:
            return conn.execute(
                "SELECT * FROM permission_requests ORDER BY created_at DESC"
            ).fetchall()


# ── Utility ───────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
