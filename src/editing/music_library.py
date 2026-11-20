"""
Music library with verified licensing metadata.

Each track record stores:
- The expected SHA-256 hash of the licensed MP3 file
- The license type and URL for the actual license document
- The source URL where the file can be (re-)downloaded
- Which platforms allow embedding for monetized content
- Whether this is a placeholder that must be replaced before launch

Separation of concerns:
  cc0_music.py  — low-level FFmpeg mixing (unchanged, still used by pipeline)
  music_library.py — licensing provenance, verification, platform policies

Embed policies:
  FREE_EMBED      CC0 / public domain — embed freely, monetize on all platforms
  SUBSCRIPTION    Licensed via Artlist/Epidemic Sound — embed allowed while subscription active
  PLATFORM_ONLY   Add via YouTube/TikTok/Snapchat audio picker; must NOT be embedded in file
  PLACEHOLDER     Synthetic beat — must be replaced before public launch
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from src.core.logger import get_logger

logger = get_logger(__name__)

_MUSIC_DIR = Path(__file__).resolve().parents[2] / "assets" / "music"


class LicenseType(str, Enum):
    CC0 = "CC0"                        # Public domain — no restrictions
    CC_BY_4 = "CC_BY_4"               # Attribution required
    ARTLIST = "ARTLIST"               # Artlist.io subscription
    EPIDEMIC_SOUND = "EPIDEMIC_SOUND" # Epidemic Sound subscription
    PLACEHOLDER = "PLACEHOLDER"       # Synthetic placeholder — not for publication


class EmbedPolicy(str, Enum):
    FREE_EMBED = "FREE_EMBED"           # Embed in MP4, monetize freely
    SUBSCRIPTION_EMBED = "SUBSCRIPTION_EMBED"  # Embed while subscription is active
    PLATFORM_ONLY = "PLATFORM_ONLY"    # Must add via audio picker post-upload
    PLACEHOLDER = "PLACEHOLDER"        # Not for public use


@dataclass(frozen=True)
class MusicTrack:
    filename: str                        # relative to assets/music/
    title: str
    artist: str
    bpm: float
    genre: str                           # e.g. "phonk", "brazilian_funk", "cinematic"
    license_type: LicenseType
    license_url: str                     # URL to license document
    source_url: str                      # URL where file was downloaded from
    file_hash_sha256: str                # expected SHA-256 of the licensed file
    embed_policy: EmbedPolicy
    platforms_allowed: list[str]         # ["youtube", "tiktok", "snapchat"] or subset
    story_types: list[str]               # e.g. ["dramatic", "worldcup"]
    notes: str = ""


# ── Track registry ────────────────────────────────────────────────────────────
# IMPORTANT: All 4 current entries are PLACEHOLDER tracks (synthetic beats).
# They MUST be replaced with real licensed tracks before public launch.
# See scripts/setup_music.py for download instructions.

_PLACEHOLDER_HASH = "87daab2d13dfc8cd26f9c98f8ae1d22f9803393479d2aec4cd4048194eef9613"

TRACKS: list[MusicTrack] = [
    MusicTrack(
        filename="epic_cinematic_cc0.mp3",
        title="[PLACEHOLDER] Synthetic Beat 110 BPM",
        artist="Generated",
        bpm=110.0,
        genre="placeholder",
        license_type=LicenseType.PLACEHOLDER,
        license_url="",
        source_url="",
        file_hash_sha256=_PLACEHOLDER_HASH,
        embed_policy=EmbedPolicy.PLACEHOLDER,
        platforms_allowed=[],
        story_types=["dramatic", "worldcup", "moments", "player_stories"],
        notes="Replace with: Pixabay Music search 'epic cinematic sport' — save as epic_cinematic_cc0.mp3",
    ),
    MusicTrack(
        filename="inspiring_sport_cc0.mp3",
        title="[PLACEHOLDER] Synthetic Beat 110 BPM",
        artist="Generated",
        bpm=110.0,
        genre="placeholder",
        license_type=LicenseType.PLACEHOLDER,
        license_url="",
        source_url="",
        file_hash_sha256=_PLACEHOLDER_HASH,
        embed_policy=EmbedPolicy.PLACEHOLDER,
        platforms_allowed=[],
        story_types=["motivation", "comeback", "player_stories"],
        notes="Replace with: Pixabay Music search 'inspiring sport upbeat' — save as inspiring_sport_cc0.mp3",
    ),
    MusicTrack(
        filename="stadium_atmosphere_cc0.mp3",
        title="[PLACEHOLDER] Synthetic Beat 110 BPM",
        artist="Generated",
        bpm=110.0,
        genre="placeholder",
        license_type=LicenseType.PLACEHOLDER,
        license_url="",
        source_url="",
        file_hash_sha256=_PLACEHOLDER_HASH,
        embed_policy=EmbedPolicy.PLACEHOLDER,
        platforms_allowed=[],
        story_types=["moments", "worldcup", "dramatic"],
        notes="Replace with: Pixabay Music search 'stadium crowd sport' — save as stadium_atmosphere_cc0.mp3",
    ),
    MusicTrack(
        filename="tension_buildup_cc0.mp3",
        title="[PLACEHOLDER] Synthetic Beat 110 BPM",
        artist="Generated",
        bpm=110.0,
        genre="placeholder",
        license_type=LicenseType.PLACEHOLDER,
        license_url="",
        source_url="",
        file_hash_sha256=_PLACEHOLDER_HASH,
        embed_policy=EmbedPolicy.PLACEHOLDER,
        platforms_allowed=[],
        story_types=["dramatic", "thriller", "moments"],
        notes="Replace with: Pixabay Music search 'tension buildup cinematic' — save as tension_buildup_cc0.mp3",
    ),
]

# ── Recommended replacements (for reference — user must download and verify) ──
# These are genre descriptions and search terms for Pixabay Music (CC0, free).
# For phonk/Brazilian funk specifically, Artlist ($199/yr) or Epidemic Sound
# ($15/month) have dedicated genre catalogs and clear monetization licenses.
RECOMMENDED_TRACKS = [
    {
        "slot": "epic_cinematic_cc0.mp3",
        "genre": "cinematic/epic sport",
        "search_terms": ["epic sport cinematic", "football intro", "sport energy"],
        "source": "Pixabay Music (pixabay.com/music/) — CC0 license, all platforms, monetization OK",
        "cost": "Free",
        "note": "Best for storytelling shorts (Materazzi, Drogba stories)",
    },
    {
        "slot": "inspiring_sport_cc0.mp3",
        "genre": "inspiring/motivational",
        "search_terms": ["inspiring sport", "motivational upbeat", "energetic sport"],
        "source": "Pixabay Music — CC0 license",
        "cost": "Free",
        "note": "Best for comeback/motivational content",
    },
    {
        "slot": "stadium_atmosphere_cc0.mp3",
        "genre": "phonk/trap sport (Artlist recommended for this genre)",
        "search_terms": ["phonk sport", "trap football", "dark sport energy"],
        "source": (
            "Artlist.io ($199/yr for all platforms) or "
            "Epidemic Sound ($15/month, YouTube + TikTok + Snapchat) — "
            "search 'phonk sport' or 'Brazilian funk football'. "
            "Pixabay Music has limited phonk selection."
        ),
        "cost": "$15–$199/year",
        "note": "Target sound: Phonk/Brazilian funk/montagem. Required for the Neymar/Yamal edit style.",
    },
    {
        "slot": "tension_buildup_cc0.mp3",
        "genre": "tension/thriller",
        "search_terms": ["tension sport", "thriller sport buildup", "dramatic suspense"],
        "source": "Pixabay Music — CC0 license",
        "cost": "Free",
        "note": "Best for reveal moments (Materazzi whisper, penalty shootouts)",
    },
]


# ── Library functions ─────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_track(story_type: str, bpm_hint: float = 100.0) -> Optional[MusicTrack]:
    """
    Return the best available track for story_type.
    Returns None if no suitable track file exists locally.
    Logs a warning if a track is a placeholder.
    """
    story_lower = story_type.lower()
    matches = [t for t in TRACKS if story_lower in t.story_types]
    if not matches:
        matches = list(TRACKS)

    available = [t for t in matches if (_MUSIC_DIR / t.filename).exists()]
    if not available:
        return None

    best = min(available, key=lambda t: abs(t.bpm - bpm_hint))
    if best.license_type == LicenseType.PLACEHOLDER:
        logger.warning(
            "music_track_is_placeholder",
            filename=best.filename,
            note=best.notes,
        )
    return best


def is_placeholder(track: MusicTrack) -> bool:
    return track.license_type == LicenseType.PLACEHOLDER


def all_tracks_are_placeholders() -> bool:
    return all(t.license_type == LicenseType.PLACEHOLDER for t in TRACKS)


def verify_library() -> dict[str, str]:
    """
    Check each track: file exists and hash matches expected.
    Returns dict of filename → "ok" | "missing" | "hash_mismatch" | "placeholder".
    """
    results: dict[str, str] = {}
    for track in TRACKS:
        path = _MUSIC_DIR / track.filename
        if not path.exists():
            results[track.filename] = "missing"
            continue
        if track.license_type == LicenseType.PLACEHOLDER:
            results[track.filename] = "placeholder"
            continue
        actual_hash = _file_hash(path)
        if actual_hash == track.file_hash_sha256:
            results[track.filename] = "ok"
        else:
            results[track.filename] = f"hash_mismatch (expected {track.file_hash_sha256[:16]})"
    return results


def licensing_manifest() -> list[dict]:
    """Return structured licensing metadata for all registered tracks."""
    manifest = []
    for track in TRACKS:
        path = _MUSIC_DIR / track.filename
        actual_hash = _file_hash(path) if path.exists() else ""
        manifest.append({
            "filename": track.filename,
            "title": track.title,
            "artist": track.artist,
            "bpm": track.bpm,
            "genre": track.genre,
            "license_type": track.license_type.value,
            "license_url": track.license_url,
            "source_url": track.source_url,
            "expected_hash": track.file_hash_sha256[:16] + "…",
            "actual_hash": actual_hash[:16] + "…" if actual_hash else "(missing)",
            "hash_verified": actual_hash == track.file_hash_sha256 if actual_hash else False,
            "embed_policy": track.embed_policy.value,
            "platforms_allowed": track.platforms_allowed,
            "notes": track.notes,
        })
    return manifest
