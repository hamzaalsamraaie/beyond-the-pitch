"""Tests for trend analysis and earnings model."""

from src.trends.analyzer import (
    analyse_short,
    build_earnings_scenarios,
    earnings_report,
    summarise_patterns,
    viral_tier,
)
from src.trends.models import DiscoveredShort


def _short(title: str, views: int = 1_000_000, age_days: float = 30.0) -> DiscoveredShort:
    return DiscoveredShort(
        video_id="test",
        title=title,
        channel_id="UC1",
        channel_title="Test Channel",
        published_at="2024-10-01T00:00:00Z",
        view_count=views,
        duration_secs=45,
        age_days=age_days,
        viral_score=views / max(age_days, 0.5) ** 0.7,
        adjusted_viral_score=100.0,
    )


# ── Viral tier ────────────────────────────────────────────────────────────────

def test_viral_tier_mega():
    assert viral_tier(15_000_000) == "MEGA"


def test_viral_tier_viral():
    assert viral_tier(2_000_000) == "VIRAL"


def test_viral_tier_growing():
    assert viral_tier(500_000) == "GROWING"


def test_viral_tier_modest():
    assert viral_tier(50_000) == "MODEST"


# ── Metadata analysis ─────────────────────────────────────────────────────────

def test_analyse_question_title():
    s = _short("Did Messi really refuse to play?")
    a = analyse_short(s)
    assert a.hook_style == "question"
    assert a.title_has_question is True


def test_analyse_player_name_title():
    s = _short("Ronaldo's impossible free kick shocked everyone")
    a = analyse_short(s)
    assert a.title_has_name is True


def test_analyse_number_title():
    s = _short("The 10 year old who embarrassed Pele")
    a = analyse_short(s)
    assert a.title_has_number is True
    # "embarrassed" triggers shocking_claim; player name triggers player_name_led;
    # number triggers number_or_stat — all are valid depending on priority order
    assert a.hook_style in ("number_or_stat", "player_name_led", "shocking_claim")


def test_analyse_always_metadata_only():
    s = _short("Any title at all")
    a = analyse_short(s)
    assert a.analysis_type == "metadata_only"
    assert "metadata_only" in a.label().lower()


def test_analyse_player_story_subject():
    s = _short("The story of how Zidane's career ended forever")
    a = analyse_short(s)
    assert a.subject_category == "player_story"


def test_analyse_goal_subject():
    s = _short("Messi scores the greatest free kick ever seen")
    a = analyse_short(s)
    assert a.subject_category in ("goal_moment", "player_story", "record_fact")


def test_analyse_motivation_tone():
    s = _short("How Ronaldo became a legend through dedication and hard work")
    a = analyse_short(s)
    assert a.emotional_tone in ("inspiration", "awe", "neutral")


# ── Pattern summarise ─────────────────────────────────────────────────────────

def test_summarise_patterns_empty():
    result = summarise_patterns([])
    assert result == {}


def test_summarise_patterns_has_hook_styles():
    shorts = [
        _short("Messi's greatest goal ever"),
        _short("Did Ronaldo really earn that?"),
        _short("100 goals in one season"),
    ]
    analyses = [analyse_short(s) for s in shorts]
    patterns = summarise_patterns(analyses)
    assert "hook_styles" in patterns
    assert "analysis_note" in patterns


def test_summarise_pct_with_name():
    shorts = [
        _short("Messi story"),
        _short("some other title"),
        _short("Ronaldo comeback"),
    ]
    analyses = [analyse_short(s) for s in shorts]
    patterns = summarise_patterns(analyses)
    # 2 out of 3 have player names
    assert patterns["pct_with_player_name"] > 50


# ── Earnings model ────────────────────────────────────────────────────────────

def test_earnings_scenarios_three_scenarios():
    scenarios = build_earnings_scenarios()
    assert len(scenarios) == 3
    names = [s.scenario_name for s in scenarios]
    assert "conservative" in names
    assert "mid" in names
    assert "optimistic" in names


def test_earnings_optimistic_beats_conservative():
    scenarios = build_earnings_scenarios()
    cons = next(s for s in scenarios if s.scenario_name == "conservative")
    opt = next(s for s in scenarios if s.scenario_name == "optimistic")
    assert opt.annual_revenue_usd > cons.annual_revenue_usd


def test_earnings_report_contains_disclaimer():
    scenarios = build_earnings_scenarios()
    report = earnings_report(scenarios)
    assert "hypothetical" in report.lower() or "range" in report.lower()
    assert "$" in report
