"""
Football moment scoring for viral content selection.

Rates football moments on five dimensions aligned with what actually
drives views and replays on YouTube Shorts:

  visual_wow_factor    35% — how visually spectacular is the action?
  rewatch_potential    25% — will viewers replay it?
  player_recognition   15% — how recognizable and popular is the player?
  music_compatibility  15% — how well does it lend itself to edit music?
  current_relevance    10% — is the player or event trending right now?

These weights are starting assumptions. The GrowthIntelligence system will
calibrate them against actual channel performance over time.

IMPORTANT — Footage rights:
  This module scores moments based on description and research.
  It does NOT guarantee that footage is available or licensed.
  All professional match footage (Premier League, La Liga, Champions League,
  international matches) is rights-managed by FIFA, UEFA, and league broadcasters.
  Content ID flags will be issued for any unlicensed broadcast clips.
  See CLAUDE.md Blockers section for the footage rights roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.core.logger import get_logger

logger = get_logger(__name__)


# ── Football moment types ─────────────────────────────────────────────────────

class MomentType(str, Enum):
    SKILL         = "skill"          # dribbles, nutmegs, tricks, flicks
    GOAL          = "goal"           # any type of goal
    SAVE          = "save"           # goalkeeper save / defensive moment
    SEQUENCE      = "sequence"       # team combinations, build-up plays
    NOSTALGIA     = "nostalgia"      # iconic historical moments
    CELEBRATION   = "celebration"    # memorable goal celebrations
    ANALYSIS      = "analysis"       # tactical / technique breakdown


# ── Player recognition tiers (based on global audience size) ─────────────────
# IMPORTANT: Having this data does NOT grant footage rights.
# This only informs creative direction and expected audience interest.

_PLAYER_RECOGNITION: dict[str, float] = {
    # Tier 1 — global icons (0.90–1.00)
    "messi":       1.00,
    "ronaldo":     1.00,
    "ronaldinho":  0.95,
    "neymar":      0.95,
    "mbappé":      0.92,
    "mbappe":      0.92,
    "yamal":       0.88,
    "lamine yamal": 0.88,
    "vinicius":    0.85,
    "vinicius jr": 0.85,
    "bellingham":  0.83,
    "haaland":     0.83,
    # Tier 2 — high recognition (0.65–0.84)
    "salah":       0.80,
    "de bruyne":   0.78,
    "pedri":       0.76,
    "rodri":       0.74,
    "musiala":     0.73,
    "saka":        0.72,
    "pulisic":     0.68,
    "lewandowski": 0.75,
    # Tier 3 — medium recognition (0.40–0.64)
    "martinez":    0.65,
    "oblak":       0.60,
    "alisson":     0.60,
    # Default for unknown players
    "__default__": 0.40,
}

_MOMENT_TYPE_WOW: dict[MomentType, float] = {
    MomentType.SKILL:       0.90,
    MomentType.GOAL:        0.85,
    MomentType.SAVE:        0.75,
    MomentType.SEQUENCE:    0.70,
    MomentType.NOSTALGIA:   0.65,
    MomentType.CELEBRATION: 0.60,
    MomentType.ANALYSIS:    0.40,
}

_MOMENT_TYPE_REWATCH: dict[MomentType, float] = {
    MomentType.SKILL:       0.95,
    MomentType.GOAL:        0.80,
    MomentType.SAVE:        0.75,
    MomentType.SEQUENCE:    0.70,
    MomentType.NOSTALGIA:   0.85,
    MomentType.CELEBRATION: 0.65,
    MomentType.ANALYSIS:    0.50,
}

_MOMENT_TYPE_MUSIC_FIT: dict[MomentType, float] = {
    MomentType.SKILL:       0.95,
    MomentType.GOAL:        0.85,
    MomentType.SAVE:        0.80,
    MomentType.SEQUENCE:    0.75,
    MomentType.NOSTALGIA:   0.70,
    MomentType.CELEBRATION: 0.90,
    MomentType.ANALYSIS:    0.40,
}

# Default scoring weights (calibrated by GrowthIntelligence over time)
DEFAULT_WEIGHTS: dict[str, float] = {
    "visual_wow_factor":   0.35,
    "rewatch_potential":   0.25,
    "player_recognition":  0.15,
    "music_compatibility": 0.15,
    "current_relevance":   0.10,
}


@dataclass
class FootballMomentScore:
    player_name: str
    moment_type: MomentType
    description: str
    visual_wow_factor: float
    rewatch_potential: float
    player_recognition: float
    music_compatibility: float
    current_relevance: float
    total_score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)
    footage_rights_status: str = "UNKNOWN"
    footage_note: str = ""


@dataclass
class MomentCandidate:
    """A football moment to be scored."""
    player_name: str
    moment_type: MomentType
    description: str
    # Optional: provide explicit scores to override auto-scoring
    current_relevance_override: float | None = None
    footage_rights_status: str = "UNKNOWN"
    footage_note: str = ""


class MomentScorer:
    """
    Scores football moment candidates for viral potential.

    Usage:
        scorer = MomentScorer()
        scored = scorer.score(candidates)
        top = scored[0]  # highest score first
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or DEFAULT_WEIGHTS.copy()

    def _player_recognition(self, player_name: str) -> float:
        name_lower = player_name.lower()
        for key, score in _PLAYER_RECOGNITION.items():
            if key in name_lower or name_lower in key:
                return score
        return _PLAYER_RECOGNITION["__default__"]

    def score_one(self, candidate: MomentCandidate) -> FootballMomentScore:
        wow = _MOMENT_TYPE_WOW.get(candidate.moment_type, 0.5)
        rewatch = _MOMENT_TYPE_REWATCH.get(candidate.moment_type, 0.5)
        music = _MOMENT_TYPE_MUSIC_FIT.get(candidate.moment_type, 0.5)
        recognition = self._player_recognition(candidate.player_name)
        relevance = candidate.current_relevance_override if (
            candidate.current_relevance_override is not None
        ) else 0.5  # neutral when unknown

        w = self._weights
        total = round(
            wow         * w.get("visual_wow_factor", 0.35)
            + rewatch   * w.get("rewatch_potential", 0.25)
            + recognition * w.get("player_recognition", 0.15)
            + music     * w.get("music_compatibility", 0.15)
            + relevance * w.get("current_relevance", 0.10),
            4,
        )

        breakdown = {
            "visual_wow":        round(wow         * w["visual_wow_factor"], 4),
            "rewatch":           round(rewatch      * w["rewatch_potential"], 4),
            "player_recognition": round(recognition * w["player_recognition"], 4),
            "music":             round(music        * w["music_compatibility"], 4),
            "relevance":         round(relevance    * w["current_relevance"], 4),
        }

        return FootballMomentScore(
            player_name=candidate.player_name,
            moment_type=candidate.moment_type,
            description=candidate.description,
            visual_wow_factor=wow,
            rewatch_potential=rewatch,
            player_recognition=recognition,
            music_compatibility=music,
            current_relevance=relevance,
            total_score=total,
            score_breakdown=breakdown,
            footage_rights_status=candidate.footage_rights_status,
            footage_note=candidate.footage_note,
        )

    def score(self, candidates: list[MomentCandidate]) -> list[FootballMomentScore]:
        """Score and rank all candidates, highest first."""
        scored = [self.score_one(c) for c in candidates]
        return sorted(scored, key=lambda s: s.total_score, reverse=True)

    def update_weights(self, new_weights: dict[str, float]) -> None:
        """Update scoring weights based on analytics feedback."""
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.05:
            logger.warning(
                "moment_scorer_weights_dont_sum_to_1",
                total=round(total, 4),
            )
        self._weights = new_weights.copy()
        logger.info("moment_scorer_weights_updated", weights=new_weights)


# ── Curated high-potential moment ideas for the first 30 days ────────────────
# These are STORY IDEAS only — footage rights must be verified separately.

LAUNCH_MOMENT_IDEAS: list[MomentCandidate] = [
    # Skills — highest rewatch potential
    MomentCandidate(
        player_name="Neymar Jr",
        moment_type=MomentType.SKILL,
        description="Neymar's most jaw-dropping dribbling sequences — elastico, rainbow, speed feints",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="Match footage owned by FIFA/CBF/club broadcasters. Consider Kling AI recreation or creator permission.",
    ),
    MomentCandidate(
        player_name="Ronaldinho",
        moment_type=MomentType.SKILL,
        description="Ronaldinho's freestyle skills and impossible moments at Barcelona",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="Match footage owned by UEFA/La Liga. Some older clips may qualify for commentary fair use.",
    ),
    MomentCandidate(
        player_name="Lamine Yamal",
        moment_type=MomentType.SKILL,
        description="Yamal's close control and dribbling at 16 — youngest footballer to do X",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="Current La Liga footage — rights-managed. Use text-overlay storytelling approach.",
    ),
    # Goals — high emotional impact
    MomentCandidate(
        player_name="Lionel Messi",
        moment_type=MomentType.GOAL,
        description="Messi's greatest Copa del Rey goal vs Getafe — the Maradona comparison",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="2007 Copa del Rey footage owned by RFEF. Best approach: text-overlay storytelling.",
    ),
    MomentCandidate(
        player_name="Cristiano Ronaldo",
        moment_type=MomentType.GOAL,
        description="Ronaldo's bicycle kick vs Juventus — the moment the opposition applauded",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="2018 UCL footage owned by UEFA. Text-overlay storytelling approach works here.",
    ),
    # Nostalgia — strong engagement
    MomentCandidate(
        player_name="Ronaldinho",
        moment_type=MomentType.NOSTALGIA,
        description="The night Ronaldinho made Bernabeu fans applaud a Barcelona goal",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="2005 UCL footage. Historical significance — good candidate for commentary/educational use.",
    ),
    MomentCandidate(
        player_name="Zinedine Zidane",
        moment_type=MomentType.GOAL,
        description="Zidane's volley in the 2002 UCL Final — voted greatest Champions League goal ever",
        footage_rights_status="REQUIRES_LICENSE",
        footage_note="UEFA-owned footage. Well-documented historical event — text-overlay storytelling approach.",
    ),
    # Saves — underrated virality
    MomentCandidate(
        player_name="Emiliano Martínez",
        moment_type=MomentType.SAVE,
        description="11 saves in the 2026 World Cup Final — a record that wasn't enough",
        footage_rights_status="CC0_TEXT_OVERLAY_READY",
        footage_note="Current approach: CC0 Pexels footage with text-overlay storytelling. Ready to produce.",
        current_relevance_override=0.85,
    ),
]
