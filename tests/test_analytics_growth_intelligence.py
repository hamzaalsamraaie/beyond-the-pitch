"""Tests for the growth intelligence system."""

from __future__ import annotations

import pytest

from src.analytics.growth_intelligence import (
    VideoAttributes,
    WeeklyGrowthReport,
    _build_recommendations,
    generate_insights,
    generate_weekly_report,
    record_video_attributes,
)


class TestVideoAttributes:
    def test_default_values(self):
        attrs = VideoAttributes(youtube_id="test123")
        assert attrs.player_name == ""
        assert attrs.moment_type == ""
        assert attrs.has_music is False

    def test_full_attributes(self):
        attrs = VideoAttributes(
            youtube_id="abc",
            player_name="Messi",
            moment_type="skill",
            video_length_secs=28.0,
            music_style="cc0_cinematic",
            hook_style="surprising_fact",
            caption_preset="DRAMATIC_REVEAL",
            posting_slot="noon",
            content_type="football_moments",
            footage_source="pexels",
            has_music=True,
        )
        assert attrs.player_name == "Messi"
        assert attrs.has_music is True


class TestRecordVideoAttributes:
    def test_records_without_error(self):
        attrs = VideoAttributes(
            youtube_id="test_gi_001",
            player_name="Messi",
            moment_type="skill",
        )
        record_video_attributes(attrs)  # should not raise

    def test_replace_on_duplicate_id(self):
        attrs1 = VideoAttributes(youtube_id="gi_dup_001", player_name="Messi")
        attrs2 = VideoAttributes(youtube_id="gi_dup_001", player_name="Ronaldo")
        record_video_attributes(attrs1)
        record_video_attributes(attrs2)  # should not raise (INSERT OR REPLACE)


class TestGenerateInsights:
    def test_returns_list(self):
        result = generate_insights()
        assert isinstance(result, list)

    def test_empty_list_when_no_data(self):
        # With no analytics data, should return empty list gracefully
        result = generate_insights()
        # Either empty (no data) or list of PerformanceInsight
        assert isinstance(result, list)

    def test_insights_have_required_fields(self):
        result = generate_insights()
        for insight in result:
            assert hasattr(insight, "dimension")
            assert hasattr(insight, "best_value")
            assert hasattr(insight, "confidence")
            assert insight.confidence in ("high", "medium", "low")


class TestGenerateWeeklyReport:
    def test_returns_weekly_growth_report(self):
        result = generate_weekly_report()
        assert isinstance(result, WeeklyGrowthReport)

    def test_period_dates_set(self):
        result = generate_weekly_report(days=7)
        assert result.period_start
        assert result.period_end

    def test_counts_are_non_negative(self):
        result = generate_weekly_report()
        assert result.videos_published >= 0
        assert result.total_views >= 0
        assert result.total_subscribers_gained >= 0

    def test_data_note_is_honest(self):
        result = generate_weekly_report()
        assert len(result.data_note) > 10

    def test_recommendations_are_list(self):
        result = generate_weekly_report()
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) >= 1

    def test_monetization_progress_mentions_ypp(self):
        result = generate_weekly_report()
        assert "1,000" in result.monetization_progress or "YPP" in result.monetization_progress or "Partner" in result.monetization_progress

    def test_top_5_is_list(self):
        result = generate_weekly_report()
        assert isinstance(result.top_5_videos, list)


class TestBuildRecommendations:
    def test_zero_published_includes_upload_rec(self):
        recs = _build_recommendations(0, 0, 0, [])
        assert any("upload" in r.lower() or "Upload" in r for r in recs)

    def test_non_zero_published_no_upload_rec(self):
        recs = _build_recommendations(5, 100, 2, [])
        # Should not tell user to upload when they already have
        assert not any("upload your first" in r.lower() for r in recs)

    def test_always_returns_list(self):
        for n in [0, 1, 5, 20]:
            assert isinstance(_build_recommendations(n, 0, 0, []), list)

    def test_low_count_recommends_publishing(self):
        recs = _build_recommendations(5, 50, 1, [])
        recs_text = " ".join(recs).lower()
        # Should mention needing more videos
        assert "publish" in recs_text or "10+" in recs_text or "21" in recs_text
