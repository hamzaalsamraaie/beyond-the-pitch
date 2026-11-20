"""
Phase 2 — data models for the research and storytelling engine.

All models use Pydantic v2 so that Claude's JSON output is validated
strictly before it enters the pipeline.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class ContentType(str, Enum):
    FOOTBALL_MOMENTS = "football_moments"
    PLAYER_STORIES = "player_stories"
    FOOTBALL_MOTIVATION = "football_motivation"


# ── Source citation ────────────────────────────────────────────────────────────

class SourceCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str = Field(min_length=4, description="Verifiable URL for this fact")
    title: str = Field(min_length=1, description="Title of the source page or article")
    publisher: str = Field(default="", description="Publication or website name")
    # ISO date string (YYYY-MM-DD) or empty string for undated evergreen sources
    date_published: str = Field(
        default="",
        pattern=r"^(\d{4}-\d{2}-\d{2})?$",
        description="ISO 8601 date (YYYY-MM-DD) or empty for undated sources",
    )


# ── Research item ──────────────────────────────────────────────────────────────

class ResearchItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    fact: str = Field(
        min_length=10,
        description="A single verifiable factual statement",
    )
    source: SourceCitation
    # "verified" = human-confirmed; "unverified" = not yet independently confirmed
    reliability: str = Field(
        default="unverified",
        pattern=r"^(verified|unverified)$",
    )

    @model_validator(mode="after")
    def reject_fabrication_markers(self) -> "ResearchItem":
        lower = self.fact.lower()
        banned_phrases = [
            "allegedly", "reportedly", "sources claim", "insider says",
            "rumored to", "set to join", "close to signing",
        ]
        for phrase in banned_phrases:
            if phrase in lower:
                raise ValueError(
                    f"ResearchItem fact contains unverified claim marker '{phrase}'. "
                    "Only use confirmed, citable facts."
                )
        return self


# ── Topic candidate ────────────────────────────────────────────────────────────

class TopicCandidate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    content_type: ContentType
    summary: str = Field(min_length=10, max_length=1000)
    research_items: list[ResearchItem] = Field(min_length=1)
    suggested_hook: str = Field(default="")

    def research_text(self) -> str:
        return " ".join(item.fact for item in self.research_items)


# ── Topic scoring ──────────────────────────────────────────────────────────────

class TopicScore(BaseModel):
    freshness: Annotated[float, Field(ge=0.0, le=1.0)]
    audience_interest: Annotated[float, Field(ge=0.0, le=1.0)]
    emotional_impact: Annotated[float, Field(ge=0.0, le=1.0)]
    originality: Annotated[float, Field(ge=0.0, le=1.0)]
    visual_feasibility: Annotated[float, Field(ge=0.0, le=1.0)]

    def total(self, weights: dict[str, float]) -> float:
        return round(
            self.freshness * weights.get("freshness", 0.20)
            + self.audience_interest * weights.get("audience_interest", 0.25)
            + self.emotional_impact * weights.get("emotional_impact", 0.25)
            + self.originality * weights.get("originality", 0.20)
            + self.visual_feasibility * weights.get("visual_feasibility", 0.10),
            4,
        )

    def breakdown(self, weights: dict[str, float]) -> dict[str, float]:
        return {
            "freshness": round(self.freshness * weights.get("freshness", 0.20), 4),
            "audience_interest": round(self.audience_interest * weights.get("audience_interest", 0.25), 4),
            "emotional_impact": round(self.emotional_impact * weights.get("emotional_impact", 0.25), 4),
            "originality": round(self.originality * weights.get("originality", 0.20), 4),
            "visual_feasibility": round(self.visual_feasibility * weights.get("visual_feasibility", 0.10), 4),
        }


class ScoredTopic(BaseModel):
    candidate: TopicCandidate
    score: TopicScore
    total_score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)


# ── Storyboard ─────────────────────────────────────────────────────────────────

class StoryboardScene(BaseModel):
    scene_number: Annotated[int, Field(ge=1)]
    start_time: Annotated[float, Field(ge=0.0)]
    end_time: Annotated[float, Field(ge=0.1)]
    narration: str = Field(
        min_length=5,
        description="Spoken narration for this scene",
    )
    on_screen_text: str = Field(
        min_length=1,
        description="Short subtitle or headline displayed on screen",
    )
    visual_requirement: str = Field(
        min_length=5,
        description="Description of visual type needed. Must NOT reference specific "
                    "broadcast clips or assume any footage is licensed.",
    )
    source_indices: list[int] = Field(
        min_length=1,
        description="0-based indices into the storyboard's research_items list",
    )

    @model_validator(mode="after")
    def end_after_start(self) -> "StoryboardScene":
        if self.end_time <= self.start_time:
            raise ValueError(
                f"Scene {self.scene_number}: end_time ({self.end_time}) "
                f"must be after start_time ({self.start_time})"
            )
        return self

    @property
    def duration(self) -> float:
        return round(self.end_time - self.start_time, 3)


class Storyboard(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    content_type: ContentType
    hook: str = Field(
        min_length=2, max_length=80,
        description="2-5 word opening hook displayed on screen",
    )
    scenes: list[StoryboardScene] = Field(
        min_length=3, max_length=8,
        description="Between 3 and 8 scenes",
    )
    total_duration: Annotated[float, Field(ge=20.0, le=45.0)]
    proposed_titles: list[str] = Field(
        min_length=3, max_length=3,
        description="Exactly 3 YouTube title options",
    )
    hashtags: list[str] = Field(
        min_length=5, max_length=10,
        description="5–10 hashtags including #Shorts and #football",
    )
    research_items: list[ResearchItem] = Field(min_length=1)
    script_hash: str = Field(default="")
    generated_by: str = Field(
        default="mock",
        description="'mock' or the Claude model ID used",
    )

    @model_validator(mode="after")
    def validate_duration_consistency(self) -> "Storyboard":
        if self.scenes:
            last_end = self.scenes[-1].end_time
            if abs(last_end - self.total_duration) > 0.5:
                raise ValueError(
                    f"total_duration ({self.total_duration}s) doesn't match "
                    f"last scene end_time ({last_end}s)"
                )
        return self

    @model_validator(mode="after")
    def validate_source_indices(self) -> "Storyboard":
        max_idx = len(self.research_items) - 1
        for scene in self.scenes:
            for idx in scene.source_indices:
                if idx < 0 or idx > max_idx:
                    raise ValueError(
                        f"Scene {scene.scene_number} has source_index {idx} "
                        f"but only {len(self.research_items)} research items exist"
                    )
        return self

    @model_validator(mode="after")
    def validate_hashtags_contain_required(self) -> "Storyboard":
        lower_tags = [h.lower() for h in self.hashtags]
        for required in ("#shorts", "#football"):
            if required not in lower_tags:
                raise ValueError(f"hashtags must include '{required}'")
        return self

    def compute_hash(self) -> str:
        """Fingerprint based on narration text — detects duplicate scripts."""
        text = "|".join(s.narration for s in self.scenes)
        return hashlib.sha256(text.encode()).hexdigest()

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> "Storyboard":
        return cls.model_validate_json(raw)
