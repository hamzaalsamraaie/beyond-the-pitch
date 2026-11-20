"""
Sound research library for Beyond The Pitch.

Curated database of 12 tracks suitable for football Shorts, based on
research into trending football-edit audio (November 2026).

Each entry includes:
  - track / artist
  - BPM (measured or estimated)
  - genre / mood
  - licensing status
  - youtube_url — official music video or sound page
  - shorts_picker: True if confirmed available in YouTube Shorts audio picker
  - embed_allowed: True if track can be embedded without Content ID risk
  - notes — usage guidance

IMPORTANT:
  Tracks marked embed_allowed=False must be added via YouTube Shorts audio
  picker at upload time. Never download and re-encode copyrighted tracks.
  Tracks in the YouTube Shorts library are covered by YouTube's licensing
  deal with rights-holders — only valid when used through the Shorts creator
  tools, not externally embedded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EmbedPolicy(str, Enum):
    FREE_EMBED   = "free_embed"       # CC0/CC-BY/royalty-free — embed directly
    SHORTS_ONLY  = "shorts_only"      # YouTube Shorts picker only
    VERIFY_FIRST = "verify_first"     # check license before embedding
    DO_NOT_USE   = "do_not_use"       # fully copyrighted, no licence


@dataclass
class SoundEntry:
    name: str
    artist: str
    bpm: int
    genre: str
    mood: str
    youtube_url: str
    embed_policy: EmbedPolicy
    shorts_picker: bool          # confirmed available in YT Shorts audio picker
    notes: str
    tags: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# CURATED LIBRARY — 12 TRACKS
# ═══════════════════════════════════════════════════════════════════════════════

SOUND_LIBRARY: list[SoundEntry] = [

    # ── TIER 1: Safe to embed directly ──────────────────────────────────────

    SoundEntry(
        name="Dramatic Orchestra Hit (Free)",
        artist="Pixabay Music",
        bpm=0,                 # stinger — not tempo-based
        genre="orchestral",
        mood="dramatic, cinematic",
        youtube_url="https://pixabay.com/music/search/dramatic/",
        embed_policy=EmbedPolicy.FREE_EMBED,
        shorts_picker=False,
        notes="Various CC0 dramatic orchestral stingers on Pixabay Music. "
              "No BPM — use as accent layer, not main track. "
              "Good bed under CINEMATIC_MINIMAL captions.",
        tags=["cinematic", "atmospheric", "storytelling"],
    ),

    SoundEntry(
        name="Phonk Football Edit Beat (CC0)",
        artist="Pixabay Music",
        bpm=135,
        genre="phonk",
        mood="hype, aggressive",
        youtube_url="https://pixabay.com/music/search/phonk%20sport/",
        embed_policy=EmbedPolicy.FREE_EMBED,
        shorts_picker=False,
        notes="Search Pixabay Music for 'phonk sport' or 'dark phonk'. "
              "Several CC0 tracks ~130-140 BPM. Verify individual track license "
              "before embedding. Best for BEAT_SYNC_FLASH and BOLD_IMPACT captions.",
        tags=["phonk", "hype", "fast", "beat_sync"],
    ),

    SoundEntry(
        name="Cinematic Build Riser",
        artist="Pixabay Music",
        bpm=0,
        genre="cinematic",
        mood="tension, build",
        youtube_url="https://pixabay.com/music/search/cinematic%20build/",
        embed_policy=EmbedPolicy.FREE_EMBED,
        shorts_picker=False,
        notes="Tension-building risers/swells on Pixabay. No beat grid — "
              "sync caption reveals to peaks manually. Suits DRAMATIC_REVEAL style.",
        tags=["tension", "reveal", "drama", "cinematic"],
    ),

    # ── TIER 2: YouTube Shorts picker only ──────────────────────────────────

    SoundEntry(
        name="Goals",
        artist="LISA, Anitta & Rema (FIFA Sound)",
        bpm=120,
        genre="K-pop / afrobeats / latin pop fusion",
        mood="celebratory, energetic",
        youtube_url="https://www.youtube.com/watch?v=safzyuZNCGI",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="Official FIFA World Cup 2026 anthem. Highly relevant for any "
              "World Cup 2026 content. Opening beat drops at 0:04. "
              "Add via YouTube Shorts audio picker — do not embed externally. "
              "Best with BOLD_IMPACT or DRAMATIC_REVEAL captions.",
        tags=["worldcup2026", "celebration", "fifa", "trending"],
    ),

    SoundEntry(
        name="Lighter",
        artist="Jelly Roll & Carín León",
        bpm=90,
        genre="country / regional mexican",
        mood="emotional, uplifting",
        youtube_url="https://www.youtube.com/watch?v=YYevs1gXueE",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="Official FIFA World Cup 2026 album. Slower tempo — suits "
              "emotional player tribute or underdog story formats. "
              "KINETIC_SLIDE or CINEMATIC_MINIMAL captions work well.",
        tags=["worldcup2026", "emotional", "tribute"],
    ),

    SoundEntry(
        name="NO BATIDÃO",
        artist="Unknown (Brazilian funk/phonk)",
        bpm=130,
        genre="Brazilian phonk",
        mood="energetic, rhythmic",
        youtube_url="https://www.youtube.com/shorts/VORyALrprik",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="One of the highest-performing sports Shorts sounds (95% popularity "
              "score per Genz.ai Nov 2026). Hard transients work perfectly for "
              "beat-sync caption reveals. BEAT_SYNC_FLASH recommended.",
        tags=["phonk", "sports", "hype", "trending", "beat_sync"],
    ),

    SoundEntry(
        name="Follow The Bass",
        artist="Unknown",
        bpm=128,
        genre="electronic / bass",
        mood="dynamic, high-energy",
        youtube_url="https://www.youtube.com/shorts/",  # search in Shorts picker
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="92% popularity score for sports Shorts (Genz.ai). Short loop ~8-14s, "
              "ideal for 15-30s Shorts. BOLD_IMPACT or BEAT_SYNC_FLASH captions.",
        tags=["electronic", "sports", "hype"],
    ),

    SoundEntry(
        name="Phonk Trap (Football Edit)",
        artist="Various (Shazam chart)",
        bpm=140,
        genre="phonk trap",
        mood="aggressive, menacing",
        youtube_url="https://www.shazam.com/song/1869007823/football-edit-phonk-trap",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="Specifically tagged 'Football Edit' on Shazam. Distorted 808s and "
              "cowbell — the dominant phonk-trap sub-genre for football edits in 2026. "
              "Find in Shorts audio picker by searching 'football edit phonk'.",
        tags=["phonk", "trap", "football_edit", "aggressive"],
    ),

    SoundEntry(
        name="Champions (World Cup 2026)",
        artist="Various FIFA artists",
        bpm=100,
        genre="anthem / pop",
        mood="triumphant, epic",
        youtube_url="https://music.youtube.com/playlist?list=PLIguiRNccbvACis1Hsog4R8N8BiboC3uw",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="Part of Official FIFA WC 2026 album. Suits Spain/Argentina content, "
              "champion tributes. Add via YouTube Shorts picker.",
        tags=["worldcup2026", "champion", "epic"],
    ),

    SoundEntry(
        name="Game Time",
        artist="Various FIFA artists",
        bpm=115,
        genre="hip-hop / trap",
        mood="pre-match hype, intense",
        youtube_url="https://music.youtube.com/playlist?list=PLIguiRNccbvACis1Hsog4R8N8BiboC3uw",
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="FIFA WC 2026 official album. Pre-game hype feel. BOLD_IMPACT or "
              "BEAT_SYNC_FLASH captions at ~115 BPM.",
        tags=["worldcup2026", "hype", "pregame"],
    ),

    SoundEntry(
        name="Laced Max",
        artist="Unknown",
        bpm=145,
        genre="electronic / high-intensity",
        mood="extreme energy, athletic",
        youtube_url="https://www.youtube.com/shorts/",  # search in Shorts picker
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="88% popularity for sports Shorts (Genz.ai). 30-60s runtime suits "
              "full Shorts. Very fast tempo — only use with quick-cut footage.",
        tags=["high_intensity", "fast", "athletic"],
    ),

    SoundEntry(
        name="WE ON GO",
        artist="Unknown",
        bpm=110,
        genre="motivational hip-hop",
        mood="motivating, hype",
        youtube_url="https://www.youtube.com/shorts/",  # search in Shorts picker
        embed_policy=EmbedPolicy.SHORTS_ONLY,
        shorts_picker=True,
        notes="90% popularity for sports Shorts (Genz.ai). 10s loop — good for "
              "quick punchy Shorts. Very usable in Shorts audio picker.",
        tags=["motivational", "hype", "loop"],
    ),
]


# ── Recommendation engine ─────────────────────────────────────────────────────

def recommend_sounds(
    story_type: str = "storytelling",
    bpm_target: int = 0,
    tags: list[str] | None = None,
    embed_only: bool = False,
    top_n: int = 3,
) -> list[SoundEntry]:
    """
    Recommend sounds for a given story type and preferences.

    story_type: "storytelling" | "hype" | "tribute" | "worldcup" | "phonk"
    bpm_target: preferred BPM, 0 = no preference
    embed_only: if True, only return FREE_EMBED tracks
    tags: extra tag filters (OR matching)
    """
    _TAG_MAP = {
        "storytelling": ["cinematic", "atmospheric", "storytelling", "drama", "tension"],
        "hype":         ["hype", "phonk", "beat_sync", "fast", "athletic"],
        "tribute":      ["emotional", "tribute", "cinematic"],
        "worldcup":     ["worldcup2026", "fifa", "champion"],
        "phonk":        ["phonk", "trap", "football_edit", "aggressive"],
    }
    target_tags = set(_TAG_MAP.get(story_type, []))
    if tags:
        target_tags.update(tags)

    pool = [
        s for s in SOUND_LIBRARY
        if (not embed_only or s.embed_policy == EmbedPolicy.FREE_EMBED)
    ]

    def _score(s: SoundEntry) -> float:
        tag_match = len(set(s.tags) & target_tags)
        bpm_penalty = abs(s.bpm - bpm_target) / 200.0 if bpm_target and s.bpm else 0
        return tag_match - bpm_penalty

    pool.sort(key=_score, reverse=True)
    return pool[:top_n]


def format_sound_recommendation(sound: SoundEntry) -> str:
    policy_label = {
        EmbedPolicy.FREE_EMBED:   "✓ Embed directly (royalty-free)",
        EmbedPolicy.SHORTS_ONLY:  "⚠ YouTube Shorts audio picker only",
        EmbedPolicy.VERIFY_FIRST: "? Verify license before embedding",
        EmbedPolicy.DO_NOT_USE:   "✗ Do not use",
    }[sound.embed_policy]

    return (
        f"  🎵 {sound.name} — {sound.artist}\n"
        f"     Genre: {sound.genre} | BPM: {sound.bpm or 'variable'} | Mood: {sound.mood}\n"
        f"     License: {policy_label}\n"
        f"     URL: {sound.youtube_url}\n"
        f"     Notes: {sound.notes[:120]}…"
    )
