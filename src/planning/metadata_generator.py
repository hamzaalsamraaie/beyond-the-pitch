"""
YouTube metadata generator: title, description, tags, and attribution.

Produces VideoMetadata ready for YouTubeUploader.

Inputs:
  - Storyboard (title, scenes, hashtags, proposed_titles)
  - OR a ClipSpec + Transcript (for clip-based Shorts)
  - Attribution list from footage assets

Output complies with:
  - YouTube title: ≤100 chars, no keyword stuffing
  - Description: ≤5000 chars, attribution block, disclosure
  - Tags: ≤500 chars total, relevant keywords
  - Appropriate AI-disclosure flag
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.youtube.uploader import VideoMetadata


@dataclass
class AttributionEntry:
    asset_description: str   # e.g. "Zidane 2006 WC Final"
    creator_name: str
    license_type: str         # e.g. "CC BY 2.0", "Pixabay License"
    source_url: str = ""
    attribution_text: str = ""  # pre-formatted if provided by asset


_CHANNEL_DESCRIPTION_FOOTER = (
    "\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🏟️ Beyond The Pitch — Football stories you've forgotten.\n"
    "Subscribe for more forgotten football stories, every week.\n"
)

_SHORTS_HASHTAGS_ALWAYS = ["#Shorts", "#football", "#soccer", "#footballshorts"]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _build_attribution_block(attributions: list[AttributionEntry]) -> str:
    if not attributions:
        return ""
    lines = ["📸 Credits & Licensing:"]
    for a in attributions:
        if a.attribution_text:
            lines.append(f"  • {a.attribution_text}")
        elif a.creator_name and a.license_type:
            line = f"  • {a.asset_description}: {a.license_type}"
            if a.creator_name:
                line += f" / {a.creator_name}"
            if a.source_url:
                line += f" ({a.source_url})"
            lines.append(line)
    return "\n".join(lines)


def _clean_title(raw: str) -> str:
    """Remove emojis and control chars; trim to 100 chars."""
    cleaned = re.sub(r"[^\x20-\x7E -￿]", "", raw).strip()
    return _truncate(cleaned, 100)


def generate_from_storyboard(
    title_override: str | None = None,
    storyboard_title: str = "",
    proposed_titles: list[str] | None = None,
    hook: str = "",
    hashtags: list[str] | None = None,
    attributions: list[AttributionEntry] | None = None,
    contains_ai: bool = False,
    visibility: str = "private",
) -> VideoMetadata:
    """
    Generate VideoMetadata from storyboard fields.
    Use title_override to force a specific title (e.g. from human review).
    """
    # Title selection
    candidate_titles = [title_override] if title_override else []
    if proposed_titles:
        candidate_titles.extend(proposed_titles)
    if storyboard_title:
        candidate_titles.append(storyboard_title)
    candidate_titles = [t for t in candidate_titles if t]
    title = _clean_title(candidate_titles[0] if candidate_titles else "Football Story")

    # Description
    summary_text = ""
    if hook:
        summary_text = f"{hook}\n\n"

    attribution_block = _build_attribution_block(attributions or [])
    disclosure = ""
    if contains_ai:
        disclosure = "\n⚠️ This video contains AI-generated visuals.\n"

    description_parts = [summary_text, attribution_block, disclosure, _CHANNEL_DESCRIPTION_FOOTER]
    description = "".join(p for p in description_parts if p).strip()
    description = _truncate(description, 5000)

    # Tags
    base_tags = list(hashtags or []) + _SHORTS_HASHTAGS_ALWAYS
    # Deduplicate preserving order
    seen: set[str] = set()
    tags: list[str] = []
    for t in base_tags:
        clean = t.lstrip("#")
        if clean.lower() not in seen:
            seen.add(clean.lower())
            tags.append(clean)

    return VideoMetadata(
        title=title,
        description=description,
        tags=tags[:30],  # YouTube allows up to ~30 tags
        visibility=visibility,
        contains_ai_generated=contains_ai,
    )


def generate_from_clip(
    source_title: str,
    hook_text: str,
    clip_duration_secs: float,
    attributions: list[AttributionEntry] | None = None,
    extra_hashtags: list[str] | None = None,
    visibility: str = "private",
) -> VideoMetadata:
    """
    Generate VideoMetadata for a clip-based Short (no storyboard).
    """
    title = _clean_title(source_title) or "Football Moment"
    if hook_text and len(title) + len(hook_text) + 4 <= 100:
        title = f"{hook_text.capitalize()} | {title}"

    duration_str = f"{int(clip_duration_secs)}s"
    description_lines = [
        f"⚽ {hook_text}" if hook_text else "",
        f"\n📺 Clip duration: {duration_str}",
        "\n" + _build_attribution_block(attributions or []),
        _CHANNEL_DESCRIPTION_FOOTER,
    ]
    description = "\n".join(l for l in description_lines if l).strip()
    description = _truncate(description, 5000)

    base_tags = (extra_hashtags or []) + _SHORTS_HASHTAGS_ALWAYS + [
        "football", "highlights", "footballmoments",
    ]
    seen: set[str] = set()
    tags: list[str] = []
    for t in base_tags:
        clean = t.lstrip("#")
        if clean.lower() not in seen:
            seen.add(clean.lower())
            tags.append(clean)

    return VideoMetadata(
        title=title,
        description=description,
        tags=tags[:30],
        visibility=visibility,
        contains_ai_generated=False,
    )
