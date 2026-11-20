"""
Production planning data models.

VideoIdea      — a ranked, scored concept before any production begins
Shot           — one discrete visual unit in the editing plan
AssetRequirement — the specific visual/audio asset needed for a Shot
ProductionPlan — the complete shot-by-shot plan for one VideoIdea

Asset status gate:
  AVAILABLE      — asset confirmed accessible with correct license for commercial use
  NEEDS_PURCHASE — asset exists but requires a paid license (stock site, etc.)
  BLOCKED        — no suitable commercial-use asset identified; production halted

A ProductionPlan is BLOCKED if ANY shot has status BLOCKED.
Production must not proceed until BLOCKED shots are resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AssetStatus = Literal["AVAILABLE", "NEEDS_PURCHASE", "BLOCKED"]
AssetType = Literal["image", "video_clip", "audio_music", "audio_sfx", "graphic", "text_only"]


@dataclass
class AssetRequirement:
    description: str           # what visually needs to appear on screen
    asset_type: AssetType
    status: AssetStatus
    source_name: str           # e.g. "Wikimedia Commons", "Pixabay", "YouTube Audio Library"
    source_url: str            # direct URL to the asset or its license page
    license: str               # e.g. "CC BY-SA 4.0", "CC0", "YouTube Audio Library"
    attribution_required: bool
    attribution_text: str = ""
    notes: str = ""            # additional context, reason for BLOCKED status, etc.

    def is_cleared(self) -> bool:
        return self.status == "AVAILABLE"


@dataclass
class Shot:
    shot_number: int
    duration_secs: float       # intended on-screen duration
    description: str           # what happens in this shot (direction note)
    on_screen_caption: str     # short text overlay (≤ 6 words for readability)
    asset: AssetRequirement
    narration_text: str = ""   # spoken words during this shot
    sound_effect: str = ""     # optional SFX label (e.g. "crowd roar", "silence")
    transition_in: str = "cut" # cut | fade | slide

    @property
    def is_clearable(self) -> bool:
        return self.asset.status != "BLOCKED"


@dataclass
class VideoIdea:
    title: str
    hook: str                        # the opening line / first 3 seconds
    concept_summary: str             # 1-2 sentence description
    content_type: str                # player_story | goal_moment | motivation | controversy | record_fact

    # 6-dimension score (0.0–1.0 each)
    trend_strength: float = 0.0
    originality: float = 0.0
    production_feasibility: float = 0.0
    licensing_feasibility: float = 0.0
    audience_interest: float = 0.0
    hook_quality: float = 0.0

    # Metadata
    inspired_by: list[str] = field(default_factory=list)   # video_ids that inspired this
    target_duration_secs: int = 30
    estimated_views_range: str = ""   # e.g. "500K–2M"
    blocking_reason: str = ""         # non-empty if concept is blocked

    @property
    def total_score(self) -> float:
        weights = {
            "trend_strength": 0.20,
            "originality": 0.20,
            "production_feasibility": 0.20,
            "licensing_feasibility": 0.20,
            "audience_interest": 0.15,
            "hook_quality": 0.05,
        }
        return sum(
            getattr(self, k) * w for k, w in weights.items()
        )

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_reason)

    def score_breakdown(self) -> str:
        lines = [f"  Total: {self.total_score:.2f}"]
        for dim in ("trend_strength", "originality", "production_feasibility",
                    "licensing_feasibility", "audience_interest", "hook_quality"):
            lines.append(f"    {dim:<28} {getattr(self, dim):.2f}")
        return "\n".join(lines)


@dataclass
class ProductionPlan:
    idea: VideoIdea
    shots: list[Shot]
    full_script: str             # narration across all shots concatenated
    music_requirement: AssetRequirement | None = None
    total_duration_secs: float = 0.0
    production_status: AssetStatus = "AVAILABLE"
    blocked_shots: list[int] = field(default_factory=list)  # shot numbers that are BLOCKED
    notes: str = ""

    def __post_init__(self) -> None:
        self.total_duration_secs = sum(s.duration_secs for s in self.shots)
        blocked = [s.shot_number for s in self.shots if s.asset.status == "BLOCKED"]
        if self.music_requirement and self.music_requirement.status == "BLOCKED":
            blocked.append(-1)  # -1 = music
        self.blocked_shots = blocked
        self.production_status = "BLOCKED" if blocked else "AVAILABLE"

    def status_report(self) -> str:
        lines = [
            f"Production plan: {self.idea.title}",
            f"Status: {self.production_status}",
            f"Duration: {self.total_duration_secs:.1f}s",
            f"Shots: {len(self.shots)}",
        ]
        if self.blocked_shots:
            labels = [f"shot {n}" if n >= 0 else "music" for n in self.blocked_shots]
            lines.append(f"BLOCKED on: {', '.join(labels)}")
        for shot in self.shots:
            status_char = "✓" if shot.asset.is_cleared() else ("$" if shot.asset.status == "NEEDS_PURCHASE" else "✗")
            lines.append(
                f"  {status_char} Shot {shot.shot_number} ({shot.duration_secs:.0f}s) "
                f"| {shot.asset.asset_type} | {shot.asset.source_name} "
                f"| {shot.asset.license} | {shot.description[:50]}"
            )
        return "\n".join(lines)
