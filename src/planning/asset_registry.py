"""
Registry of known commercial-use asset sources.

Each source has:
  - name and URL
  - license type
  - whether attribution is required
  - what asset types it provides
  - commercial use permitted

This registry is used by the shot planner to propose and verify assets.
It does NOT perform live lookups — it describes what sources EXIST and their rules.
Actual asset availability must be verified before production begins.

Sources included:
  Wikimedia Commons — CC-licensed images and some video (player photos, historical events)
  Pixabay           — CC0 images and videos, no attribution required, commercial use OK
  Pexels            — Pexels license: free commercial use, attribution appreciated but not required
  YouTube Audio Library — Free music and SFX, commercial use on YouTube OK
  Freesound (CC0)   — CC0 sound effects only
  OpenGameArt (CC0) — CC0 music and SFX
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssetType = Literal["image", "video_clip", "audio_music", "audio_sfx", "graphic"]


@dataclass(frozen=True)
class AssetSource:
    name: str
    base_url: str
    license_name: str
    license_url: str
    commercial_use_permitted: bool
    attribution_required: bool
    asset_types: tuple[str, ...]
    notes: str = ""


SOURCES: dict[str, AssetSource] = {
    "wikimedia_commons": AssetSource(
        name="Wikimedia Commons",
        base_url="https://commons.wikimedia.org",
        license_name="Various CC (CC BY-SA 4.0, CC BY 4.0, CC0, PD)",
        license_url="https://commons.wikimedia.org/wiki/Commons:Licensing",
        commercial_use_permitted=True,  # for CC-BY and CC0 files only
        attribution_required=True,       # required for CC-BY/CC-BY-SA
        asset_types=("image", "video_clip"),
        notes=(
            "Check each file's individual license. Many player photos are CC-BY-SA. "
            "Pre-1928 photos may be public domain. "
            "NEVER assume a Wikimedia image is CC0 without checking the file page."
        ),
    ),
    "pixabay": AssetSource(
        name="Pixabay",
        base_url="https://pixabay.com",
        license_name="Pixabay License (CC0-equivalent)",
        license_url="https://pixabay.com/service/license-summary/",
        commercial_use_permitted=True,
        attribution_required=False,
        asset_types=("image", "video_clip"),
        notes=(
            "Pixabay License allows commercial use without attribution. "
            "Football-specific stock: pitch aerials, ball, boots, stadium crowds (generic). "
            "No footage of specific players or club kits without model/property release."
        ),
    ),
    "pexels": AssetSource(
        name="Pexels",
        base_url="https://www.pexels.com",
        license_name="Pexels License",
        license_url="https://www.pexels.com/license/",
        commercial_use_permitted=True,
        attribution_required=False,
        asset_types=("image", "video_clip"),
        notes=(
            "Free for commercial use. No attribution required. "
            "Similar to Pixabay: good for generic football visuals. "
            "Avoid any image showing a recognisable player in team kit without rights."
        ),
    ),
    "youtube_audio_library": AssetSource(
        name="YouTube Audio Library",
        base_url="https://studio.youtube.com/channel/music",
        license_name="YouTube Audio Library License",
        license_url="https://support.google.com/youtube/answer/3376882",
        commercial_use_permitted=True,
        attribution_required=False,  # some tracks require attribution; check per track
        asset_types=("audio_music", "audio_sfx"),
        notes=(
            "Free music and sound effects for YouTube use. "
            "Some tracks are 'Attribution required' — check each track. "
            "Only covers YouTube distribution; verify terms for other platforms."
        ),
    ),
    "freesound_cc0": AssetSource(
        name="Freesound (CC0 only)",
        base_url="https://freesound.org",
        license_name="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        commercial_use_permitted=True,
        attribution_required=False,
        asset_types=("audio_sfx",),
        notes=(
            "Filter to CC0 license only. Many sounds on Freesound require attribution "
            "or are non-commercial. Only use files explicitly marked CC0."
        ),
    ),
    "original_graphics": AssetSource(
        name="Original generated graphics",
        base_url="",
        license_name="Original work",
        license_url="",
        commercial_use_permitted=True,
        attribution_required=False,
        asset_types=("image", "graphic"),
        notes=(
            "Motion graphics, text cards, gradients, scoreboards, stat panels "
            "created by this pipeline. No third-party rights involved."
        ),
    ),
    "macos_tts": AssetSource(
        name="macOS TTS (Samantha voice)",
        base_url="https://www.apple.com",
        license_name="Apple Software License",
        license_url="https://www.apple.com/legal/sla/",
        commercial_use_permitted=False,  # personal/educational only per Apple SLA
        attribution_required=False,
        asset_types=("audio_sfx",),
        notes=(
            "BLOCKED for commercial/monetized content. "
            "Apple's TTS is for personal and educational use. "
            "Use a commercially licensed TTS (ElevenLabs, Amazon Polly) for monetized content."
        ),
    ),
    "elevenlabs": AssetSource(
        name="ElevenLabs TTS",
        base_url="https://elevenlabs.io",
        license_name="ElevenLabs Commercial License",
        license_url="https://elevenlabs.io/terms",
        commercial_use_permitted=True,
        attribution_required=False,
        asset_types=("audio_sfx",),
        notes=(
            "Commercial use permitted on paid plans (Starter $5/mo+). "
            "Requires API key. High-quality neural TTS voices. "
            "Set ELEVENLABS_API_KEY in .env to enable."
        ),
    ),
}


def get_source(source_key: str) -> AssetSource | None:
    return SOURCES.get(source_key)


def commercial_sources() -> list[AssetSource]:
    return [s for s in SOURCES.values() if s.commercial_use_permitted]


def sources_for_type(asset_type: str) -> list[AssetSource]:
    return [
        s for s in SOURCES.values()
        if asset_type in s.asset_types and s.commercial_use_permitted
    ]
