"""Tests for research data models."""

import pytest
from pydantic import ValidationError

from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    Storyboard,
    StoryboardScene,
    TopicCandidate,
    TopicScore,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _citation(**kwargs) -> SourceCitation:
    defaults = dict(
        url="https://en.wikipedia.org/wiki/Test",
        title="Test Article",
        publisher="Wikipedia",
        date_published="",
    )
    return SourceCitation(**{**defaults, **kwargs})


def _item(fact: str = "In 1970 Pelé scored his 500th career goal.", **kwargs) -> ResearchItem:
    return ResearchItem(fact=fact, source=_citation(**kwargs))


def _scene(n: int, start: float, end: float) -> StoryboardScene:
    return StoryboardScene(
        scene_number=n,
        start_time=start,
        end_time=end,
        narration="Pelé was one of the greatest footballers of all time.",
        on_screen_text="THE KING",
        visual_requirement="Illustrated graphic of a footballer",
        source_indices=[0],
    )


def _storyboard(total_duration: float = 30.0) -> Storyboard:
    return Storyboard(
        title="Pelé: The King of Football",
        content_type=ContentType.PLAYER_STORIES,
        hook="THE KING",
        scenes=[
            _scene(1, 0.0, 8.0),
            _scene(2, 8.0, 18.0),
            _scene(3, 18.0, total_duration),
        ],
        total_duration=total_duration,
        proposed_titles=["Title A", "Title B", "Title C"],
        hashtags=["#Shorts", "#football", "#pele", "#legend", "#stories"],
        research_items=[_item()],
        generated_by="mock",
    )


# ── SourceCitation ─────────────────────────────────────────────────────────────

def test_citation_valid():
    c = _citation(date_published="2024-06-01")
    assert c.date_published == "2024-06-01"


def test_citation_rejects_invalid_date_format():
    with pytest.raises(ValidationError):
        _citation(date_published="June 2024")


def test_citation_allows_empty_date():
    c = _citation(date_published="")
    assert c.date_published == ""


# ── ResearchItem ───────────────────────────────────────────────────────────────

def test_item_valid():
    item = _item()
    assert item.reliability == "unverified"


def test_item_rejects_fabrication_markers():
    with pytest.raises(ValidationError, match="allegedly"):
        _item(fact="Allegedly, Messi scored 50 goals in a single season.")

    with pytest.raises(ValidationError, match="sources claim"):
        _item(fact="Sources claim the player is set to retire this year.")


def test_item_rejects_transfer_rumor_language():
    with pytest.raises(ValidationError):
        _item(fact="The player is set to join Manchester City next season.")


def test_item_accepts_verified_reliability():
    item = ResearchItem(
        fact="In 2022, Argentina won the FIFA World Cup.",
        source=_citation(),
        reliability="verified",
    )
    assert item.reliability == "verified"


# ── TopicScore ─────────────────────────────────────────────────────────────────

def test_topic_score_total_with_equal_weights():
    ts = TopicScore(
        freshness=0.8,
        audience_interest=0.6,
        emotional_impact=0.9,
        originality=0.5,
        visual_feasibility=0.7,
    )
    weights = dict(
        freshness=0.20,
        audience_interest=0.25,
        emotional_impact=0.25,
        originality=0.20,
        visual_feasibility=0.10,
    )
    expected = round(0.8 * 0.20 + 0.6 * 0.25 + 0.9 * 0.25 + 0.5 * 0.20 + 0.7 * 0.10, 4)
    assert ts.total(weights) == expected


def test_topic_score_clamped_at_zero_and_one():
    with pytest.raises(ValidationError):
        TopicScore(
            freshness=1.5,  # out of range
            audience_interest=0.5,
            emotional_impact=0.5,
            originality=0.5,
            visual_feasibility=0.5,
        )


# ── StoryboardScene ────────────────────────────────────────────────────────────

def test_scene_end_must_be_after_start():
    with pytest.raises(ValidationError, match="end_time"):
        StoryboardScene(
            scene_number=1,
            start_time=10.0,
            end_time=5.0,  # before start
            narration="Some narration here.",
            on_screen_text="Hook",
            visual_requirement="Illustrated graphic",
            source_indices=[0],
        )


def test_scene_duration_property():
    scene = _scene(1, 0.0, 7.5)
    assert scene.duration == 7.5


# ── Storyboard ─────────────────────────────────────────────────────────────────

def test_storyboard_valid():
    sb = _storyboard()
    assert sb.total_duration == 30.0
    assert len(sb.scenes) == 3


def test_storyboard_duration_too_short():
    with pytest.raises(ValidationError):
        _storyboard(total_duration=15.0)


def test_storyboard_duration_too_long():
    with pytest.raises(ValidationError):
        _storyboard(total_duration=50.0)


def test_storyboard_requires_hashtag_shorts():
    with pytest.raises(ValidationError, match="#shorts"):
        Storyboard(
            title="Test Storyboard",
            content_type=ContentType.PLAYER_STORIES,
            hook="HOOK",
            scenes=[_scene(1, 0.0, 10.0), _scene(2, 10.0, 20.0), _scene(3, 20.0, 30.0)],
            total_duration=30.0,
            proposed_titles=["T1", "T2", "T3"],
            hashtags=["#football", "#stories", "#players", "#goals", "#sports"],  # missing #Shorts
            research_items=[_item()],
        )


def test_storyboard_rejects_bad_source_index():
    with pytest.raises(ValidationError, match="source_index"):
        Storyboard(
            title="Test Storyboard",
            content_type=ContentType.PLAYER_STORIES,
            hook="HOOK",
            scenes=[
                StoryboardScene(
                    scene_number=1,
                    start_time=0.0,
                    end_time=10.0,
                    narration="Some narration.",
                    on_screen_text="Text",
                    visual_requirement="Graphic",
                    source_indices=[5],  # only 1 research item exists (index 0)
                ),
                _scene(2, 10.0, 20.0),
                _scene(3, 20.0, 30.0),
            ],
            total_duration=30.0,
            proposed_titles=["T1", "T2", "T3"],
            hashtags=["#Shorts", "#football", "#stories", "#players", "#sports"],
            research_items=[_item()],
        )


def test_storyboard_hash_is_deterministic():
    sb = _storyboard()
    h1 = sb.compute_hash()
    h2 = sb.compute_hash()
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_storyboard_json_roundtrip():
    sb = _storyboard()
    json_str = sb.to_json()
    restored = Storyboard.from_json(json_str)
    assert restored.title == sb.title
    assert restored.total_duration == sb.total_duration
    assert len(restored.scenes) == len(sb.scenes)
