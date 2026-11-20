"""
Data models for YouTube Shorts trend discovery.

All fields that come from the YouTube Data API are marked with their source
(search.list, videos.list, channels.list) so quota cost is transparent.

DiscoveredShort stores one YouTube Short's metadata and computed scores.
TrendSnapshot is a point-in-time metric capture for time-series comparison.
ChannelProfile summarises a creator's channel-level metadata.
EarningsScenario models hypothetical revenue at three RPM levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


# ── YouTube Shorts discovery ───────────────────────────────────────────────────

@dataclass
class DiscoveredShort:
    # From search.list
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: str                       # ISO 8601, e.g. "2024-11-10T12:00:00Z"

    # From videos.list (statistics + contentDetails)
    view_count: int = 0
    like_count: int = 0                    # may be hidden; 0 means unknown
    comment_count: int = 0
    duration_iso: str = ""                  # e.g. "PT45S" — ISO 8601
    duration_secs: int = 0

    # From channels.list
    channel_subscriber_count: int = 0      # 0 if hidden

    # Computed locally — never from API
    viral_score: float = 0.0               # views / age_days^0.7
    adjusted_viral_score: float = 0.0      # viral_score / sqrt(max(subs, 100))
    age_days: float = 0.0

    # Duration classification
    # YouTube Shorts can be up to 3 minutes (extended late 2023).
    # Duration ≤ 180s is COMPATIBLE with being a Short, but not conclusive —
    # a regular upload can also have a short duration.
    is_duration_compatible_short: bool = True

    # Snapshot tracking — populated by _persist_short()
    snapshot_count: int = 1               # how many times we've fetched this video
    view_velocity_per_day: float | None = None  # views/day since last snapshot; None if 1st
    is_first_snapshot: bool = True        # True until a 2nd fetch updates it

    # Metadata
    collected_at: str = ""                  # ISO 8601 of when we fetched this
    data_source: str = "youtube_data_api_v3"

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/shorts/{self.video_id}"

    @property
    def snapshot_label(self) -> str:
        if self.is_first_snapshot or self.snapshot_count <= 1:
            return "1st snapshot — lifetime views, growth rate unavailable"
        if self.view_velocity_per_day is not None:
            return f"snapshot #{self.snapshot_count} — Δ{self.view_velocity_per_day:,.0f} views/day"
        return f"snapshot #{self.snapshot_count}"

    @property
    def age_label(self) -> str:
        if self.age_days < 1:
            return "< 1 day old"
        if self.age_days < 7:
            return f"{self.age_days:.0f} days old"
        if self.age_days < 30:
            return f"{self.age_days / 7:.0f} weeks old"
        return f"{self.age_days / 30:.0f} months old"

    def summary_line(self) -> str:
        subs = (
            f"{self.channel_subscriber_count:,} subs"
            if self.channel_subscriber_count > 0
            else "subs hidden"
        )
        return (
            f"{self.view_count:>10,} views | {self.age_label:<18} | "
            f"{subs:<20} | viral={self.viral_score:,.0f} | {self.title[:55]}"
        )


@dataclass
class TrendSnapshot:
    """Point-in-time metric capture. Stored in DB for time-series comparisons."""
    video_id: str
    title: str
    channel_title: str
    view_count: int
    like_count: int
    comment_count: int
    subscriber_count: int
    snapshot_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""


@dataclass
class ChannelProfile:
    channel_id: str
    handle: str                            # e.g. "@Porsevio"
    title: str
    subscriber_count: int
    video_count: int
    view_count: int                        # total channel views
    country: str = ""
    description_snippet: str = ""
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def summary(self) -> str:
        return (
            f"{self.handle} | {self.subscriber_count:,} subs | "
            f"{self.video_count:,} videos | {self.view_count:,} total views"
        )


# ── Trend analysis ─────────────────────────────────────────────────────────────

AnalysisType = Literal["metadata_only", "direct_inspection"]


@dataclass
class MetadataAnalysis:
    """
    Structural analysis of a Short derived ONLY from API metadata.
    analysis_type is always "metadata_only" — we cannot watch the video via API.
    Title, description and tag patterns are the sole source.
    """
    video_id: str
    analysis_type: AnalysisType = "metadata_only"

    # Derived from title text
    hook_style: str = ""           # e.g. "question", "shocking_claim", "number_list"
    subject_category: str = ""     # e.g. "player_story", "goal_highlight", "motivation"
    emotional_tone: str = ""       # e.g. "awe", "inspiration", "shock"
    title_word_count: int = 0
    title_has_number: bool = False
    title_has_question: bool = False
    title_has_name: bool = False   # player name in title

    # Structural notes (metadata-derived only)
    notes: str = ""

    def label(self) -> str:
        return f"[{self.analysis_type.upper()}]"


# ── Earnings model ─────────────────────────────────────────────────────────────

@dataclass
class EarningsScenario:
    """
    Hypothetical revenue model. All assumptions are explicit.
    No competitor revenue figures are claimed or used.

    YouTube Shorts RPM reference ranges (Sports category, as of late 2024):
      Shorts feed RPM: $0.03–$0.15 / 1,000 views (creator's 45% share after YT cut)
      Regular long-form Sports RPM: $1.50–$4.00 / 1,000 views
    These are industry-reported ranges, not channel-specific figures.
    """
    scenario_name: str             # "conservative" | "mid" | "optimistic"
    rpm_usd: float                 # Revenue Per Mille (per 1,000 views, creator share)
    monthly_videos: int            # shorts published per month
    avg_views_per_short: int       # average views per Short in this scenario
    months: int = 12

    # Computed
    @property
    def monthly_views(self) -> int:
        return self.monthly_videos * self.avg_views_per_short

    @property
    def monthly_revenue_usd(self) -> float:
        return (self.monthly_views / 1_000) * self.rpm_usd

    @property
    def annual_revenue_usd(self) -> float:
        return self.monthly_revenue_usd * self.months

    def report_line(self) -> str:
        return (
            f"  {self.scenario_name.capitalize():<14} "
            f"RPM ${self.rpm_usd:.3f}  "
            f"{self.monthly_videos} vids/mo × {self.avg_views_per_short:,} avg views  "
            f"→ ${self.monthly_revenue_usd:,.0f}/mo  "
            f"(${self.annual_revenue_usd:,.0f}/yr)"
        )
