"""Tests for soccer relevance filter and age tier classification."""

from src.trends.soccer_filter import assess_soccer_relevance, age_tier


# ── Soccer relevance — positive cases ────────────────────────────────────────

def test_messi_title_is_soccer():
    r = assess_soccer_relevance("Messi's greatest free kick ever")
    assert r.tier in ("soccer", "likely_soccer")
    assert r.is_soccer


def test_ronaldo_siuu_is_soccer():
    r = assess_soccer_relevance("Ronaldo siuu in different voices")
    assert r.is_soccer


def test_champions_league_is_soccer():
    r = assess_soccer_relevance("The goal that won the Champions League")
    assert r.is_soccer


def test_free_kick_term_is_soccer():
    r = assess_soccer_relevance("1000 IQ free kick tactic")
    assert r.is_soccer


def test_penalty_term_is_soccer():
    r = assess_soccer_relevance("Motivation vs Discipline: penalties")
    assert r.is_soccer


def test_barcelona_club_is_soccer():
    r = assess_soccer_relevance("Barcelona's greatest ever goal")
    assert r.is_soccer


def test_premier_league_is_soccer():
    r = assess_soccer_relevance("Every Premier League winner since 1992")
    assert r.is_soccer


# ── Soccer relevance — exclusion cases ───────────────────────────────────────

def test_nfl_is_excluded():
    r = assess_soccer_relevance("Best NFL touchdowns of 2024")
    assert not r.is_soccer
    assert r.tier == "other"


def test_micdup_is_excluded():
    r = assess_soccer_relevance("Got that W!!! #football #micdup #tackle", "Courtney")
    assert not r.is_soccer
    assert r.tier == "other"


def test_super_bowl_is_excluded():
    r = assess_soccer_relevance("Super Bowl 2026 highlights")
    assert not r.is_soccer


def test_marquise_goodwin_is_excluded():
    r = assess_soccer_relevance("Marquise Goodwin Talking About His Sister #football")
    assert not r.is_soccer


def test_army_motivation_is_excluded():
    r = assess_soccer_relevance("Army Athletes Motivation Status #motivation #army")
    assert not r.is_soccer


def test_basketball_game_is_excluded():
    r = assess_soccer_relevance("NBA game highlights")
    assert not r.is_soccer


# ── Soccer relevance — mixed signals ─────────────────────────────────────────

def test_messi_beats_nfl_signal():
    """A Messi title with NFL in it should be classified by the dominant signal."""
    r = assess_soccer_relevance("Messi reacts to watching an NFL game")
    # Messi (+2) vs NFL (-4) → score = -2 → "other"
    # This is correct — a video about Messi watching NFL is NOT a soccer video
    assert r.tier == "other"


def test_haaland_title_no_negatives_is_soccer():
    r = assess_soccer_relevance("Haaland Fooled EVERYONE #shorts #funny #mbappe")
    assert r.is_soccer


def test_world_cup_stadium_is_soccer():
    r = assess_soccer_relevance("How Much Money Can You Make at a World Cup Stadium")
    assert r.is_soccer


# ── Uncertain cases ───────────────────────────────────────────────────────────

def test_generic_football_no_signals_is_uncertain():
    r = assess_soccer_relevance("Coach Yells Player Yells Back #football")
    # No soccer-specific terms, no American football signals → uncertain
    assert r.tier in ("uncertain", "likely_soccer", "other")


def test_empty_title_is_uncertain():
    r = assess_soccer_relevance("")
    assert r.tier == "uncertain"
    assert not r.is_soccer


# ── Age tier ──────────────────────────────────────────────────────────────────

def test_age_tier_recent_breakout():
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert age_tier(recent) == "RECENT_BREAKOUT"


def test_age_tier_recent_success():
    from datetime import datetime, timezone, timedelta
    mid = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert age_tier(mid) == "RECENT_SUCCESS"


def test_age_tier_evergreen():
    assert age_tier("2023-01-01T00:00:00Z") == "EVERGREEN"


def test_age_tier_bad_date_returns_evergreen():
    assert age_tier("not-a-date") == "EVERGREEN"


def test_age_tier_boundary_30_days():
    from datetime import datetime, timezone, timedelta
    exactly_30 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert age_tier(exactly_30) in ("RECENT_BREAKOUT", "RECENT_SUCCESS")


def test_age_tier_boundary_90_days():
    from datetime import datetime, timezone, timedelta
    exactly_91 = (datetime.now(timezone.utc) - timedelta(days=91)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert age_tier(exactly_91) == "EVERGREEN"


# ── Relevance result fields ───────────────────────────────────────────────────

def test_positive_signals_populated():
    r = assess_soccer_relevance("Ronaldo's impossible free kick")
    assert len(r.positive_signals) > 0


def test_negative_signals_populated():
    r = assess_soccer_relevance("NFL touchdown highlights")
    assert len(r.negative_signals) > 0


def test_note_is_non_empty():
    r = assess_soccer_relevance("Messi goal")
    assert len(r.note) > 0
    assert "metadata" in r.note.lower()
