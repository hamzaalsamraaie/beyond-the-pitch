#!/usr/bin/env python3
"""
Footage catalog CLI — manage the Beyond The Pitch footage asset database.

Usage examples:
  # Check what license a URL carries before importing
  python scripts/footage_catalog.py check --url "https://pixabay.com/videos/..."

  # Import a Pixabay stock clip (license auto-inferred, status → PENDING_REVIEW)
  python scripts/footage_catalog.py import stock \
      --url "https://pixabay.com/videos/soccer-sports-event-stadium-arena-8502/" \
      --description "Soccer stadium event aerial" \
      --tags stadium crowd football

  # Import an AI-generated clip after generating it on a paid plan
  python scripts/footage_catalog.py import ai \
      --tool kling --plan-tier standard \
      --prompt "Cinematic penalty spot, wet grass, stadium floodlights, 9:16 vertical" \
      --local-path output/footage/penalty_spot_test.mp4 \
      --duration 5.0

  # Register a creator permission request (you send the email manually)
  python scripts/footage_catalog.py request-permission \
      --creator-name "Football Stories" \
      --creator-url "https://youtube.com/@FootballStories" \
      --source-url "https://youtube.com/watch?v=VIDEOID" \
      --description "Documentary on 2006 World Cup" \
      --method email

  # After receiving written permission, record it and approve the asset
  python scripts/footage_catalog.py confirm-permission \
      --request-id "UUID" \
      --evidence "Creator replied on 2026-11-16: Yes, you have permission to use clips from this video for Beyond The Pitch." \
      --asset-ids "ASSET_UUID_1" "ASSET_UUID_2"

  # Approve a PENDING_REVIEW asset (after visual confirmation)
  python scripts/footage_catalog.py approve --id "ASSET_UUID"

  # Reject an asset
  python scripts/footage_catalog.py reject --id "ASSET_UUID" --reason "Contains identifiable player faces"

  # List all assets
  python scripts/footage_catalog.py list
  python scripts/footage_catalog.py list --tier STOCK_LICENSED --status APPROVED
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.footage.catalog import FootageCatalog
from src.footage.license_checker import check_url
from src.footage.models import ApprovalStatus, AssetTier
from src.footage import sources


def _catalog() -> FootageCatalog:
    return FootageCatalog()


# ── Subcommand handlers ───────────────────────────────────────────────────────

def cmd_check(args: argparse.Namespace) -> None:
    result = check_url(args.url)
    print(f"\nURL: {args.url}")
    print(f"License type    : {result.license_type.value}")
    print(f"Commercial use  : {'YES' if result.commercial_use else 'NO'}")
    print(f"Monetization OK : {'YES' if result.monetization_allowed else 'NO'}")
    print(f"Attribution req : {'YES' if result.attribution_required else 'no'}")
    print(f"Content ID risk : {result.content_id_risk.value}")
    print(f"Confidence      : {result.confidence}")
    print(f"Notes           :\n  {result.notes}")


def cmd_import_stock(args: argparse.Namespace) -> None:
    try:
        asset = sources.stock_clip(
            url=args.url,
            description=args.description,
            tags=args.tags or [],
            creator_name=args.creator_name or "",
            creator_url=args.creator_url or "",
            duration_secs=args.duration,
            resolution=args.resolution or "",
            notes=args.notes or "",
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    catalog = _catalog()
    try:
        asset_id = catalog.add_asset(asset)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAsset registered: {asset_id}")
    print(f"Status  : {asset.approval_status.value}")
    print(f"License : {asset.license_type.value}")
    print(f"\nNext step: visually inspect the clip for identifiable people, logos, or broadcast elements.")
    print(f"If clear, approve with:")
    print(f"  python scripts/footage_catalog.py approve --id {asset_id}")


def cmd_import_ai(args: argparse.Namespace) -> None:
    asset = sources.ai_generated_clip(
        local_path=args.local_path or "",
        tool_name=args.tool,
        plan_tier=args.plan_tier,
        prompt=args.prompt,
        duration_secs=args.duration or 0.0,
        resolution=args.resolution or "1080x1920",
        tags=args.tags or [],
        notes=args.notes or "",
    )
    catalog = _catalog()
    try:
        asset_id = catalog.add_asset(asset)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAI asset registered: {asset_id}")
    print(f"Status : {asset.approval_status.value}")
    print(f"\nReview the generated clip, confirm no real player faces or logos.")
    print(f"If clear, approve with:")
    print(f"  python scripts/footage_catalog.py approve --id {asset_id}")
    print(f"\nRemember: toggle 'Contains AI-generated content' in YouTube Studio when uploading.")


def cmd_request_permission(args: argparse.Namespace) -> None:
    catalog = _catalog()

    asset = sources.creator_authorized(
        source_url=args.source_url,
        creator_name=args.creator_name,
        creator_url=args.creator_url,
        description=args.description or "",
        notes=args.notes or "",
    )
    try:
        asset_id = catalog.add_asset(asset)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    req_id = catalog.create_permission_request(
        creator_name=args.creator_name,
        creator_url=args.creator_url,
        request_method=args.method or "email",
    )

    print(f"\nAsset registered  : {asset_id}  (status: NOT_APPROVED)")
    print(f"Permission request: {req_id}")
    print(f"\nNow send your permission request to {args.creator_name} via {args.method or 'email'}.")
    print(f"Suggested message:")
    print(f"""
  Subject: Permission to use footage from your video for Beyond The Pitch

  Hi {args.creator_name},

  I run Beyond The Pitch, a YouTube channel covering football stories.
  I'd like to use clips from {args.source_url} in an upcoming Short.
  The clip would be credited to your channel in the video description.
  Could you confirm in writing whether this is okay?

  Thank you,
  Beyond The Pitch
""")
    print(f"Once you receive written permission, record it with:")
    print(f"  python scripts/footage_catalog.py confirm-permission \\")
    print(f"      --request-id {req_id} \\")
    print(f'      --evidence "PASTE THEIR REPLY HERE" \\')
    print(f"      --asset-ids {asset_id}")


def cmd_confirm_permission(args: argparse.Namespace) -> None:
    catalog = _catalog()
    asset_ids = args.asset_ids or []
    catalog.confirm_permission(
        request_id=args.request_id,
        evidence_text=args.evidence,
        asset_ids=asset_ids,
    )
    print(f"\nPermission confirmed for request {args.request_id}")
    print(f"Assets approved: {', '.join(asset_ids) if asset_ids else 'none'}")


def cmd_approve(args: argparse.Namespace) -> None:
    catalog = _catalog()
    asset = catalog.get_asset(args.id)
    if asset is None:
        print(f"ERROR: Asset '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    local_path: str = getattr(args, "local_path", None) or ""
    if local_path:
        from pathlib import Path as _Path
        if not _Path(local_path).exists():
            print(f"ERROR: --local-path file not found: {local_path}", file=sys.stderr)
            sys.exit(1)
        catalog.update_local_path(args.id, local_path)
        print(f"Local path set: {local_path}")

    catalog.update_approval(
        args.id,
        ApprovalStatus.APPROVED,
        reason=args.reason or "Manually approved after visual review.",
    )
    print(f"\nAsset '{args.id}' approved for production.")
    if asset.attribution_required:
        print(f"\nAttribution required. Attribution text:")
        print(f"  {asset.attribution_text or '(not set — add with the edit command)'}")


def cmd_reject(args: argparse.Namespace) -> None:
    catalog = _catalog()
    if catalog.get_asset(args.id) is None:
        print(f"ERROR: Asset '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    catalog.update_approval(args.id, ApprovalStatus.REJECTED, reason=args.reason or "")
    print(f"Asset '{args.id}' rejected.")


def cmd_list(args: argparse.Namespace) -> None:
    catalog = _catalog()
    tier = AssetTier(args.tier) if args.tier else None
    status = ApprovalStatus(args.status) if args.status else None
    assets = catalog.list_assets(tier=tier, status=status)

    if not assets:
        print("No assets found.")
        return

    print(f"\n{'ID':<38} {'TIER':<22} {'STATUS':<16} {'LICENSE':<28} {'DESCRIPTION'}")
    print("-" * 130)
    for a in assets:
        desc = a.description[:40] + "…" if len(a.description) > 40 else a.description
        print(
            f"{a.id:<38} {a.asset_tier.value:<22} {a.approval_status.value:<16} "
            f"{a.license_type.value:<28} {desc}"
        )
    print(f"\n{len(assets)} asset(s) total.")


def cmd_list_requests(args: argparse.Namespace) -> None:
    catalog = _catalog()
    rows = catalog.list_permission_requests()
    if not rows:
        print("No permission requests recorded.")
        return
    print(f"\n{'ID':<38} {'CREATOR':<30} {'STATUS':<12} {'METHOD'}")
    print("-" * 100)
    for r in rows:
        print(f"{r['id']:<38} {r['creator_name']:<30} {r['response_status']:<12} {r['request_method']}")
    print(f"\n{len(rows)} request(s) total.")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="footage_catalog.py",
        description="Beyond The Pitch footage catalog management",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # check
    chk = sub.add_parser("check", help="Check license of a URL without importing")
    chk.add_argument("--url", required=True)

    # import stock
    imp = sub.add_parser("import", help="Import a footage asset")
    imp_sub = imp.add_subparsers(dest="import_type", required=True)

    stk = imp_sub.add_parser("stock", help="Import a stock clip (Pixabay, Pexels, Coverr, etc.)")
    stk.add_argument("--url", required=True)
    stk.add_argument("--description", required=True)
    stk.add_argument("--tags", nargs="*")
    stk.add_argument("--creator-name", default="")
    stk.add_argument("--creator-url", default="")
    stk.add_argument("--duration", type=float)
    stk.add_argument("--resolution", default="")
    stk.add_argument("--notes", default="")

    ai = imp_sub.add_parser("ai", help="Register an AI-generated clip")
    ai.add_argument("--tool", required=True, help="kling | runway | pika | ...")
    ai.add_argument("--plan-tier", required=True, help="standard | pro | ...")
    ai.add_argument("--prompt", required=True)
    ai.add_argument("--local-path", default="")
    ai.add_argument("--duration", type=float)
    ai.add_argument("--resolution", default="1080x1920")
    ai.add_argument("--tags", nargs="*")
    ai.add_argument("--notes", default="")

    # request-permission
    rp = sub.add_parser("request-permission", help="Register a Tier 1 creator permission request")
    rp.add_argument("--creator-name", required=True)
    rp.add_argument("--creator-url", required=True)
    rp.add_argument("--source-url", required=True)
    rp.add_argument("--description", default="")
    rp.add_argument("--method", default="email", choices=["email", "dm_youtube", "dm_instagram", "dm_twitter"])
    rp.add_argument("--notes", default="")

    # confirm-permission
    cp = sub.add_parser("confirm-permission", help="Record written permission received from creator")
    cp.add_argument("--request-id", required=True)
    cp.add_argument("--evidence", required=True, help="Quote from creator's reply confirming permission")
    cp.add_argument("--asset-ids", nargs="*", default=[])

    # approve
    apr = sub.add_parser("approve", help="Approve a PENDING_REVIEW asset")
    apr.add_argument("--id", required=True)
    apr.add_argument("--reason", default="")
    apr.add_argument("--local-path", default="", help="Set local file path at approval time")

    # reject
    rej = sub.add_parser("reject", help="Reject an asset")
    rej.add_argument("--id", required=True)
    rej.add_argument("--reason", default="")

    # list
    lst = sub.add_parser("list", help="List footage assets")
    lst.add_argument("--tier", choices=[t.value for t in AssetTier])
    lst.add_argument("--status", choices=[s.value for s in ApprovalStatus])

    # list-requests
    sub.add_parser("list-requests", help="List creator permission requests")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "check": cmd_check,
        "request-permission": cmd_request_permission,
        "confirm-permission": cmd_confirm_permission,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "list": cmd_list,
        "list-requests": cmd_list_requests,
    }

    if args.command == "import":
        if args.import_type == "stock":
            cmd_import_stock(args)
        elif args.import_type == "ai":
            cmd_import_ai(args)
        else:
            parser.error(f"Unknown import type: {args.import_type}")
    elif args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
