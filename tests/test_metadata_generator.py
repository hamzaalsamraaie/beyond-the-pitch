"""Tests for the metadata generator."""

import pytest
from src.planning.metadata_generator import (
    generate_from_storyboard,
    generate_from_clip,
    AttributionEntry,
    _truncate,
    _clean_title,
)


def test_truncate_short():
    assert _truncate("hello", 10) == "hello"


def test_truncate_long():
    result = _truncate("a" * 20, 10)
    assert len(result) <= 10
    assert result.endswith("...")


def test_clean_title_strips_control_chars():
    result = _clean_title("Goal\x00s")
    assert "\x00" not in result


def test_clean_title_truncates_to_100():
    long_title = "x" * 200
    result = _clean_title(long_title)
    assert len(result) <= 100


def test_generate_from_storyboard_basic():
    md = generate_from_storyboard(
        storyboard_title="Zidane Headbutt",
        proposed_titles=["The Headbutt That Ended a Legend"],
        hook="2006 World Cup Final. And Zidane completely lost it.",
        hashtags=["#football", "#Shorts"],
    )
    assert md.title
    assert len(md.title) <= 100
    assert len(md.description) <= 5000
    assert "football" in md.tags or "Shorts" in md.tags


def test_generate_from_storyboard_title_override():
    md = generate_from_storyboard(
        title_override="My Custom Title",
        storyboard_title="Something Else",
    )
    assert md.title == "My Custom Title"


def test_generate_from_storyboard_attribution():
    attributions = [
        AttributionEntry(
            asset_description="Zidane photo",
            creator_name="David Ruddell",
            license_type="CC BY 2.0",
        )
    ]
    md = generate_from_storyboard(attributions=attributions)
    assert "David Ruddell" in md.description or "CC BY 2.0" in md.description


def test_generate_from_storyboard_ai_disclosure():
    md = generate_from_storyboard(contains_ai=True)
    assert md.contains_ai_generated is True
    assert "AI" in md.description or "synthetic" in md.description.lower()


def test_generate_from_clip_basic():
    md = generate_from_clip(
        source_title="Football Highlights",
        hook_text="incredible goal",
        clip_duration_secs=42.0,
    )
    assert md.title
    assert len(md.title) <= 100
    assert md.visibility == "private"


def test_generate_from_clip_no_duplicate_tags():
    md = generate_from_clip(
        source_title="Test",
        hook_text="goal",
        clip_duration_secs=30.0,
        extra_hashtags=["#Shorts", "#football"],
    )
    lower_tags = [t.lower() for t in md.tags]
    assert len(lower_tags) == len(set(lower_tags)), "Duplicate tags found"


def test_generate_from_storyboard_no_duplicate_tags():
    md = generate_from_storyboard(
        hashtags=["#Shorts", "#Shorts", "#football", "#football"],
    )
    lower_tags = [t.lower() for t in md.tags]
    assert len(lower_tags) == len(set(lower_tags))
