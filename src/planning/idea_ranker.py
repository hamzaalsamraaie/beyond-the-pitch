"""
Rank original video ideas using 6 dimensions derived from trend data.

Dimensions and weights:
  trend_strength       0.20  — how well the concept aligns with currently trending patterns
  originality          0.20  — how different it is from existing top Shorts (title similarity)
  production_feasibility 0.20 — can we build it without match footage?
  licensing_feasibility  0.20 — are all required assets commercially available?
  audience_interest    0.15  — emotional pull and subject matter appeal
  hook_quality         0.05  — strength of the opening 3 seconds

Each dimension is scored 0.0–1.0. Total score uses the weights above.
"""

from __future__ import annotations

import re

from src.core.logger import get_logger
from src.planning.models import VideoIdea
from src.trends.models import DiscoveredShort, MetadataAnalysis

logger = get_logger(__name__)

# High-interest subject keywords (drive audience_interest score)
_HIGH_INTEREST_SUBJECTS = {
    "player_story": 0.85,
    "goal_moment": 0.80,
    "skill_moment": 0.75,
    "record_fact": 0.75,
    "motivation": 0.70,
    "controversy": 0.65,
    "general_football": 0.50,
}

# Production feasibility by concept type
# "motion_graphics" ideas need only original graphics + text — HIGH feasibility
# "match_footage" ideas require specific licensed clips — LOW feasibility
_PRODUCTION_TYPES = {
    "motion_graphics_only": 0.95,  # stat cards, text reveals, illustrated timelines
    "stock_plus_graphics": 0.80,   # generic stock football + graphics
    "wikipedia_photos_plus_graphics": 0.85,  # CC-BY photos + graphics
    "match_footage_required": 0.10,  # BLOCKED unless licensed
    "broadcast_clip_required": 0.05,  # BLOCKED unless licensed
}

# Licensing feasibility — does the asset type have clear commercial-use sources?
_LICENSE_FEASIBILITY = {
    "fully_cc0": 1.0,
    "cc_by_wikimedia": 0.90,
    "stock_free_commercial": 0.90,
    "stock_paid": 0.60,
    "match_footage": 0.05,
    "broadcast_clip": 0.02,
}


def _jaccard(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _originality_score(idea: VideoIdea, existing_titles: list[str]) -> float:
    """Return 1.0 if fully original, 0.0 if near-duplicate of an existing top Short."""
    if not existing_titles:
        return 1.0
    max_sim = max(_jaccard(idea.title, t) for t in existing_titles)
    if max_sim > 0.60:
        return 0.0   # too similar
    if max_sim > 0.40:
        return 0.4
    if max_sim > 0.25:
        return 0.7
    return 1.0


def _trend_strength_score(
    idea: VideoIdea,
    top_analyses: list[MetadataAnalysis],
) -> float:
    """
    Score how well this idea's content_type and hook style align with
    the most successful patterns in the discovered Shorts.
    """
    if not top_analyses:
        return 0.5  # no data, neutral

    subject_match = sum(
        1 for a in top_analyses
        if a.subject_category == idea.content_type
    ) / len(top_analyses)

    return min(0.3 + subject_match * 1.4, 1.0)


def rank_ideas(
    ideas: list[VideoIdea],
    discovered_shorts: list[DiscoveredShort],
    top_analyses: list[MetadataAnalysis],
) -> list[VideoIdea]:
    """
    Score all ideas and return them sorted by total_score descending.
    Modifies each idea's score fields in place.
    """
    existing_titles = [s.title for s in discovered_shorts]

    for idea in ideas:
        idea.trend_strength = _trend_strength_score(idea, top_analyses)
        idea.originality = _originality_score(idea, existing_titles)
        idea.audience_interest = _HIGH_INTEREST_SUBJECTS.get(idea.content_type, 0.5)
        # production_feasibility and licensing_feasibility must be set by caller
        # based on the actual shot plan; here we default to what's declared
        if idea.production_feasibility == 0.0:
            idea.production_feasibility = 0.5
        if idea.licensing_feasibility == 0.0:
            idea.licensing_feasibility = 0.5

    ideas.sort(key=lambda i: i.total_score, reverse=True)
    logger.info("ideas_ranked", count=len(ideas),
                top=ideas[0].title if ideas else "")
    return ideas


def apply_production_type(idea: VideoIdea, production_type: str, license_type: str) -> None:
    """Update an idea's feasibility scores based on its production approach."""
    idea.production_feasibility = _PRODUCTION_TYPES.get(production_type, 0.5)
    idea.licensing_feasibility = _LICENSE_FEASIBILITY.get(license_type, 0.5)
    if idea.production_feasibility < 0.20 or idea.licensing_feasibility < 0.20:
        idea.blocking_reason = (
            f"Production type '{production_type}' or license type '{license_type}' "
            "requires assets that are not available for commercial use. "
            "Replace BLOCKED shots before production can proceed."
        )
