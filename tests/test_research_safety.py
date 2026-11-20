"""Tests for the content safety checker."""

import pytest

from src.research.models import ContentType, ResearchItem, SourceCitation
from src.research.safety import (
    check_research_items,
    check_storyboard,
    check_text,
    check_topic_title,
    is_safe_research,
    is_safe_storyboard,
)
from tests.test_research_models import _item, _scene, _storyboard


# ── check_text ─────────────────────────────────────────────────────────────────

def test_clean_text_has_no_violations():
    assert check_text("Messi scored a hat-trick in the Copa del Rey final.") == []


def test_gambling_reference_flagged():
    v = check_text("The odds for Barcelona winning are 2/1 at the bookmaker.")
    assert any("gambling" in msg for msg in v)


def test_betting_flagged():
    v = check_text("Place your bet before kick-off.")
    assert any("gambling" in msg for msg in v)


def test_explicit_content_flagged():
    v = check_text("This contains pornographic material.")
    assert any("explicit" in msg for msg in v)


def test_transfer_rumor_language_flagged():
    v = check_text("He is set to sign for Real Madrid next week.")
    assert any("transfer_rumor" in msg for msg in v)


def test_unnamed_sources_flagged():
    v = check_text("Sources claim the manager will resign tomorrow.")
    assert any("unverified_sourcing" in msg for msg in v)


# ── check_topic_title ──────────────────────────────────────────────────────────

def test_clean_title_passes():
    assert check_topic_title("Zinedine Zidane's Greatest Moments") == []


def test_banned_topic_keyword_flagged():
    v = check_topic_title("Premier League Gambling Scandal 2024")
    assert any("banned_topic" in msg for msg in v)


# ── check_research_items ───────────────────────────────────────────────────────

def test_clean_research_items_pass():
    items = [
        _item("In 1958, Pelé won the FIFA World Cup with Brazil at age 17."),
        _item("Pelé scored over 1000 career goals in professional football."),
    ]
    assert check_research_items(items) == []


def test_gambling_in_research_item_flagged():
    items = [
        _item("The odds for Pelé's team to win were 5/1 at betting shops."),
    ]
    v = check_research_items(items)
    assert len(v) > 0
    assert "research_item[0]" in v[0]


# ── check_storyboard ───────────────────────────────────────────────────────────

def test_clean_storyboard_passes():
    sb = _storyboard()
    assert check_storyboard(sb) == []


def test_gambling_in_narration_flagged():
    from src.research.models import Storyboard, StoryboardScene
    sb = Storyboard(
        title="Football Test",
        content_type=ContentType.PLAYER_STORIES,
        hook="HOOK",
        scenes=[
            StoryboardScene(
                scene_number=1,
                start_time=0.0,
                end_time=10.0,
                narration="You can bet on this player reaching the top.",  # 'bet' triggers
                on_screen_text="Text",
                visual_requirement="Illustrated graphic",
                source_indices=[0],
            ),
            _scene(2, 10.0, 20.0),
            _scene(3, 20.0, 30.0),
        ],
        total_duration=30.0,
        proposed_titles=["T1", "T2", "T3"],
        hashtags=["#Shorts", "#football", "#stories", "#players", "#sports"],
        research_items=[_item()],
    )
    v = check_storyboard(sb)
    assert any("gambling" in msg for msg in v)


def test_licensed_footage_claim_in_visual_requirement_flagged():
    from src.research.models import Storyboard, StoryboardScene
    sb = Storyboard(
        title="Football Test",
        content_type=ContentType.FOOTBALL_MOMENTS,
        hook="HOOK",
        scenes=[
            StoryboardScene(
                scene_number=1,
                start_time=0.0,
                end_time=10.0,
                narration="A wonderful moment in football history.",
                on_screen_text="Text",
                visual_requirement="Use the official footage from the TV broadcast clip.",
                source_indices=[0],
            ),
            _scene(2, 10.0, 20.0),
            _scene(3, 20.0, 30.0),
        ],
        total_duration=30.0,
        proposed_titles=["T1", "T2", "T3"],
        hashtags=["#Shorts", "#football", "#stories", "#players", "#sports"],
        research_items=[_item()],
    )
    v = check_storyboard(sb)
    assert any("licensed" in msg.lower() or "footage" in msg.lower() for msg in v)


# ── is_safe_ convenience wrappers ──────────────────────────────────────────────

def test_is_safe_research_returns_tuple():
    items = [_item()]
    safe, violations = is_safe_research(items)
    assert safe is True
    assert violations == []


def test_is_safe_storyboard_returns_tuple():
    sb = _storyboard()
    safe, violations = is_safe_storyboard(sb)
    assert safe is True
    assert violations == []
