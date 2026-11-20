"""Tests for the AutoProducer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    Storyboard,
    StoryboardScene,
)


def _make_storyboard(title: str = "Messi's Greatest Goal Ever Scored") -> Storyboard:
    item = ResearchItem(
        fact="Lionel Messi scored a goal in 2007 Copa del Rey semi-final.",
        source=SourceCitation(
            url="https://en.wikipedia.org/wiki/Lionel_Messi",
            title="Lionel Messi",
            publisher="Wikipedia",
        ),
        reliability="verified",
    )
    return Storyboard(
        title=title,
        content_type=ContentType.FOOTBALL_MOMENTS,
        hook="GREATEST GOAL?",
        scenes=[
            StoryboardScene(
                scene_number=1,
                start_time=0.0,
                end_time=8.0,
                narration="In 2007, Messi scored what many call the greatest Copa del Rey goal.",
                on_screen_text="2007 Copa del Rey",
                visual_requirement="Stadium crowd celebration",
                source_indices=[0],
            ),
            StoryboardScene(
                scene_number=2,
                start_time=8.0,
                end_time=16.0,
                narration="He dribbled past five defenders from his own half.",
                on_screen_text="5 defenders beaten",
                visual_requirement="Football dribble sequence",
                source_indices=[0],
            ),
            StoryboardScene(
                scene_number=3,
                start_time=16.0,
                end_time=24.0,
                narration="A moment compared directly to Maradona's hand of God goal.",
                on_screen_text="Like Maradona",
                visual_requirement="Football celebration",
                source_indices=[0],
            ),
        ],
        total_duration=24.0,
        proposed_titles=["Messi Channels Maradona", "Greatest Copa Goal Ever?", "5 Defenders. 1 Messi."],
        hashtags=["#Shorts", "#football", "#Messi", "#Copa", "#football"],
        research_items=[item],
        script_hash="test_hash_abc123",
        generated_by="mock",
    )


class TestAutoProducerKillSwitch:
    def test_kill_switch_stops_produce(self):
        from src.production.auto_producer import AutoProducer
        producer = AutoProducer()
        sb = _make_storyboard()
        with patch("src.production.auto_producer.require_clear", side_effect=RuntimeError("kill")):
            result = producer.produce_one(sb)
        assert not result.success
        assert "kill" in result.failure_reason.lower()


class TestAutoProducerNoFootage:
    def test_no_approved_footage_returns_failure(self):
        from src.production.auto_producer import AutoProducer
        producer = AutoProducer()
        sb = _make_storyboard()
        with patch("src.production.auto_producer.require_clear"):
            with patch.object(producer, "_find_approved_footage", return_value=None):
                result = producer.produce_one(sb)
        assert not result.success
        assert "footage" in result.failure_reason.lower()


class TestAutoProducerDryRun:
    def test_dry_run_succeeds_without_render(self):
        from src.production.auto_producer import AutoProducer
        producer = AutoProducer(dry_run=True)
        sb = _make_storyboard()
        with patch("src.production.auto_producer.require_clear"):
            with patch.object(producer, "_find_approved_footage", return_value="/fake/path.mp4"):
                result = producer.produce_one(sb)
        assert result.success
        assert "dry_run" in result.stages_completed


class TestAutoProducerSlug:
    def test_slug_is_safe(self):
        from src.production.auto_producer import _slug
        assert " " not in _slug("Messi's Greatest Goal! Compilation #1")
        assert "/" not in _slug("path/to/something weird")

    def test_slug_max_length(self):
        from src.production.auto_producer import _slug
        s = _slug("A" * 200)
        assert len(s) <= 40

    def test_slug_lowercased(self):
        from src.production.auto_producer import _slug
        assert _slug("UPPER CASE TITLE") == _slug("upper case title")


class TestStoryboardToStoryBeats:
    def test_produces_correct_tuples(self):
        from src.production.auto_producer import _storyboard_to_story_beats
        sb = _make_storyboard()
        beats = _storyboard_to_story_beats(sb)
        assert len(beats) == len(sb.scenes)
        for start, end, text in beats:
            assert end > start
            assert len(text) > 0

    def test_uses_on_screen_text(self):
        from src.production.auto_producer import _storyboard_to_story_beats
        sb = _make_storyboard()
        beats = _storyboard_to_story_beats(sb)
        # First scene on_screen_text is "2007 Copa del Rey"
        assert beats[0][2] == "2007 Copa del Rey"


class TestBuildMetadata:
    def test_returns_video_metadata(self):
        from src.production.auto_producer import _build_metadata
        from src.youtube.uploader import VideoMetadata
        sb = _make_storyboard()
        meta = _build_metadata(sb)
        assert isinstance(meta, VideoMetadata)
        assert meta.visibility == "private"
        assert meta.made_for_kids is False

    def test_title_within_youtube_limit(self):
        from src.production.auto_producer import _build_metadata
        sb = _make_storyboard()
        meta = _build_metadata(sb)
        assert len(meta.title) <= 100

    def test_description_within_youtube_limit(self):
        from src.production.auto_producer import _build_metadata
        sb = _make_storyboard()
        meta = _build_metadata(sb)
        assert len(meta.description) <= 5000

    def test_publish_at_passed_through(self):
        from src.production.auto_producer import _build_metadata
        sb = _make_storyboard()
        ts = "2026-11-21T17:00:00.000Z"
        meta = _build_metadata(sb, publish_at=ts)
        assert meta.publish_at == ts

    def test_publish_at_empty_by_default(self):
        from src.production.auto_producer import _build_metadata
        sb = _make_storyboard()
        meta = _build_metadata(sb)
        assert meta.publish_at == ""


class TestVerifySceneSources:
    def test_valid_sources_pass(self):
        from src.production.auto_producer import _verify_scene_sources
        sb = _make_storyboard()
        # All scenes have source_indices=[0] and research_items has 1 entry — should pass
        _verify_scene_sources(sb)  # no exception

    def test_scene_without_sources_raises(self):
        from src.production.auto_producer import _verify_scene_sources
        sb = _make_storyboard()
        # Remove source_indices from first scene
        sb.scenes[0].source_indices = []
        with pytest.raises(ValueError, match="source_indices"):
            _verify_scene_sources(sb)

    def test_short_scenes_are_exempt(self):
        from src.production.auto_producer import _verify_scene_sources
        sb = _make_storyboard()
        # Give the first scene a short narration (<=10 words) and an out-of-range
        # source index — _verify_scene_sources should skip it without raising.
        # (Pydantic requires source_indices to have ≥1 item, so use index 99.)
        sb.scenes[0].narration = "Beyond The Pitch"  # 3 words — exempt
        sb.scenes[0].source_indices = [99]  # out of range, but model allows it
        _verify_scene_sources(sb)  # no exception — short narration is exempt

    def test_out_of_range_index_treated_as_missing(self):
        from src.production.auto_producer import _verify_scene_sources
        sb = _make_storyboard()
        # Point to an index that doesn't exist
        sb.scenes[0].source_indices = [99]  # out of range
        with pytest.raises(ValueError):
            _verify_scene_sources(sb)

    def test_empty_storyboard_scenes_pass(self):
        from src.production.auto_producer import _verify_scene_sources
        sb = _make_storyboard()
        sb.scenes = []
        _verify_scene_sources(sb)  # no exception — nothing to verify


class TestAutoProducerPublishAt:
    def test_publish_at_stored_on_producer(self):
        from src.production.auto_producer import AutoProducer
        ts = "2026-11-21T17:00:00.000Z"
        producer = AutoProducer(publish_at=ts)
        assert producer._publish_at == ts

    def test_publish_at_default_empty(self):
        from src.production.auto_producer import AutoProducer
        producer = AutoProducer()
        assert producer._publish_at == ""
