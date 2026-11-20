#!/usr/bin/env python3
"""
Upload martinez_world_cup_v2.mp4 to YouTube as a PRIVATE draft.

Pre-wired with the correct title, description, credits, and tags.
Requires YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env.

Usage:
  python scripts/upload_first_short.py              # upload as private
  python scripts/upload_first_short.py --publish    # make already-uploaded video public

Add music via YouTube Shorts audio picker AFTER upload — do not embed externally.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from src.core.database import init_db
from src.core.logger import configure_logging, get_logger
from src.planning.metadata_generator import generate_from_storyboard, AttributionEntry
from src.youtube.oauth import credentials_available
from src.youtube.uploader import YouTubeUploader, VideoMetadata

configure_logging()
logger = get_logger("upload_first_short")

VIDEO_PATH  = _ROOT / "output" / "shorts" / "martinez_world_cup_v2.mp4"
RENDER_ID   = 6

# ── Finalised metadata ────────────────────────────────────────────────────────
TITLE = "He made 11 saves. It still wasn't enough. #WorldCup2026 #Martinez"

DESCRIPTION = (
    "Emiliano Martínez set a World Cup final record with 11 saves against Spain. "
    "Argentina did not register a single shot in all of regulation — the first time "
    "that has ever happened in a World Cup final. Then Ferran Torres scored in the "
    "106th minute.\n\n"
    "📸 Credits & Licensing:\n"
    "  • Footage: Pexels Free License — commercial use & monetization permitted, "
    "no attribution required (pexels.com)\n"
    "  • Crowd audio: Pixabay CC0 — commercial use & monetization permitted, "
    "no attribution required (pixabay.com)\n"
    "\n"
    "🎵 Sound: Add 'Goals' (Lisa, Anitta & Rema) or 'NO BATIDÃO' via the "
    "YouTube Shorts audio picker before publishing.\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🏟️ Beyond The Pitch — Football stories you've forgotten.\n"
    "Subscribe for more forgotten football stories, every week."
)

TAGS = [
    "WorldCup2026", "Argentina", "Martinez", "FootballShorts",
    "BeyondThePitch", "Shorts", "football", "soccer",
    "Spain", "FerranTorres", "goalkeeper",
]


def _check_credentials() -> bool:
    if credentials_available():
        return True
    print(
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "BLOCKER: YouTube OAuth credentials are not set.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "1. Open: https://console.cloud.google.com/\n"
        "2. Create a project (e.g. 'BeyondThePitch')\n"
        "3. APIs & Services → Enable APIs → search 'YouTube Data API v3' → Enable\n"
        "4. APIs & Services → Credentials → Create Credentials → OAuth client ID\n"
        "   • Application type: Desktop app\n"
        "   • Name: Beyond The Pitch CLI\n"
        "5. Download JSON — you need 'client_id' and 'client_secret' values\n"
        "6. Open .env and add:\n"
        "     YOUTUBE_CLIENT_ID=your_client_id_here\n"
        "     YOUTUBE_CLIENT_SECRET=your_client_secret_here\n"
        "7. Re-run this script. A browser window will open for consent.\n"
        "\n"
        "⚠️  Also add your channel (@BeyondThePitchMedia1) to the OAuth\n"
        "   'Test users' list while the app is in testing mode.\n"
        "   APIs & Services → OAuth consent screen → Test users → Add user\n"
    )
    return False


def upload_private() -> str | None:
    """Upload the video as private. Returns youtube_id on success."""
    if not VIDEO_PATH.exists():
        print(f"ERROR: Video not found: {VIDEO_PATH}")
        return None

    metadata = VideoMetadata(
        title=TITLE[:100],
        description=DESCRIPTION[:5000],
        tags=TAGS[:30],
        visibility="private",
        contains_ai_generated=False,
        made_for_kids=False,
    )

    init_db()
    uploader = YouTubeUploader()
    print(f"\n⟳  Uploading {VIDEO_PATH.name} as PRIVATE…")
    print("   (A browser window will open for Google sign-in on first run.)\n")

    result = uploader.upload(VIDEO_PATH, metadata, video_db_id=RENDER_ID)

    if result.is_duplicate:
        print(f"⚠  Already uploaded as: https://youtu.be/{result.youtube_id}")
        return result.youtube_id

    if result.success:
        print(f"\n✓  Uploaded (PRIVATE): https://youtu.be/{result.youtube_id}")
        print(f"   YouTube Studio: https://studio.youtube.com/video/{result.youtube_id}/edit")
        print()
        print("── NEXT STEPS ──────────────────────────────────────────────")
        print("1. Open YouTube Studio → verify video processed correctly")
        print("2. Click 'Edit' → 'Audio' → search 'Goals' or 'NO BATIDÃO'")
        print("   Add the sound via Shorts audio picker")
        print("3. Watch the full Short in YouTube Studio preview")
        print("4. When satisfied, run:")
        print(f"   python scripts/upload_first_short.py --publish {result.youtube_id}")
        return result.youtube_id
    else:
        print(f"ERROR: Upload failed — {result.failure_reason}")
        return None


def publish_public(youtube_id: str) -> bool:
    """Change an already-uploaded private video to public."""
    from src.youtube.oauth import build_youtube_client  # noqa: PLC0415
    yt = build_youtube_client()
    yt.videos().update(
        part="status",
        body={
            "id": youtube_id,
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        },
    ).execute()
    print(f"\n✓  Published: https://youtu.be/{youtube_id}")
    print("   Verify at: https://www.youtube.com/shorts/" + youtube_id)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Beyond The Pitch first Short")
    parser.add_argument("--publish", metavar="YOUTUBE_ID",
                        help="Make an already-uploaded private video public")
    args = parser.parse_args()

    if not _check_credentials():
        return 1

    if args.publish:
        print(f"\n⚠  Publishing {args.publish} publicly. This cannot be undone easily.")
        confirm = input("Type YES to confirm: ").strip()
        if confirm != "YES":
            print("Aborted.")
            return 0
        return 0 if publish_public(args.publish) else 1

    youtube_id = upload_private()
    return 0 if youtube_id else 1


if __name__ == "__main__":
    sys.exit(main())
