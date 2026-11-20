"""Tests for the planning pipeline: ranker, shot planner, script generator."""

import tempfile
from pathlib import Path

import pytest

import src.core.database as db_module
from src.planning.asset_registry import SOURCES, commercial_sources, sources_for_type
from src.planning.idea_ranker import _jaccard, apply_production_type, rank_ideas
from src.planning.models import VideoIdea
from src.planning.script_generator import (
    check_script_feasibility,
    generate_haaland_origin_script,
    generate_zidane_headbutt_script,
)
from src.planning.shot_planner import build_plan_haaland_origin, build_plan_zidane_headbutt
from src.trends.models import DiscoveredShort


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_module.DB_PATH = tmp_path / "test_planning.db"
    db_module.init_db()
    yield


def _idea(**kwargs) -> VideoIdea:
    defaults = dict(
        title="Messi's Childhood Story",
        hook="At 11 doctors said he might never grow.",
        concept_summary="Origin story.",
        content_type="player_story",
    )
    return VideoIdea(**{**defaults, **kwargs})


# ── Asset registry ────────────────────────────────────────────────────────────

def test_all_registry_sources_have_license_url():
    for key, source in SOURCES.items():
        assert source.license_url != "" or source.name == "Original generated graphics", (
            f"Source '{key}' has no license_url"
        )


def test_commercial_sources_all_permit_commercial_use():
    for s in commercial_sources():
        assert s.commercial_use_permitted is True


def test_sources_for_image_type_non_empty():
    image_sources = sources_for_type("image")
    assert len(image_sources) > 0


def test_macos_tts_not_commercial():
    macos = SOURCES.get("macos_tts")
    assert macos is not None
    assert macos.commercial_use_permitted is False


def test_original_graphics_commercial():
    og = SOURCES.get("original_graphics")
    assert og is not None
    assert og.commercial_use_permitted is True


# ── Idea ranker ───────────────────────────────────────────────────────────────

def test_jaccard_identical():
    assert _jaccard("messi goal", "messi goal") == 1.0


def test_jaccard_no_overlap():
    assert _jaccard("messi goal", "xyzabc def") == 0.0


def test_jaccard_partial():
    sim = _jaccard("messi goal ever", "messi free kick")
    assert 0 < sim < 1


def test_rank_ideas_sorted_descending():
    ideas = [
        _idea(title="A", trend_strength=0.5, originality=0.5,
              production_feasibility=0.5, licensing_feasibility=0.5,
              audience_interest=0.5, hook_quality=0.5),
        _idea(title="B", trend_strength=0.9, originality=0.9,
              production_feasibility=0.9, licensing_feasibility=0.9,
              audience_interest=0.9, hook_quality=0.9),
    ]
    ranked = rank_ideas(ideas, [], [])
    assert ranked[0].title == "B"


def test_apply_production_type_match_footage_blocks():
    idea = _idea()
    apply_production_type(idea, "match_footage_required", "match_footage")
    assert idea.is_blocked
    assert idea.production_feasibility < 0.20


def test_apply_production_type_graphics_ok():
    idea = _idea()
    apply_production_type(idea, "motion_graphics_only", "fully_cc0")
    assert not idea.is_blocked
    assert idea.production_feasibility > 0.90


# ── Shot planner ──────────────────────────────────────────────────────────────

def test_zidane_plan_has_shots():
    plan = build_plan_zidane_headbutt()
    assert len(plan.shots) >= 5


def test_zidane_plan_has_no_match_footage():
    plan = build_plan_zidane_headbutt()
    for shot in plan.shots:
        assert shot.asset.asset_type != "video_clip" or shot.asset.status == "BLOCKED", (
            f"Shot {shot.shot_number} uses video_clip without being BLOCKED"
        )


def test_zidane_plan_duration_in_range():
    plan = build_plan_zidane_headbutt()
    assert 20 <= plan.total_duration_secs <= 45


def test_zidane_all_captions_short():
    """On-screen captions should be ≤ 8 words for readability."""
    plan = build_plan_zidane_headbutt()
    for shot in plan.shots:
        words = len(shot.on_screen_caption.split())
        assert words <= 8, (
            f"Shot {shot.shot_number} caption too long ({words} words): "
            f"'{shot.on_screen_caption}'"
        )


def test_haaland_plan_has_shots():
    plan = build_plan_haaland_origin()
    assert len(plan.shots) >= 5


def test_plan_status_report_runs_without_error():
    plan = build_plan_zidane_headbutt()
    report = plan.status_report()
    assert "Production plan" in report


# ── Script generator ──────────────────────────────────────────────────────────

def test_zidane_script_has_all_sections():
    script = generate_zidane_headbutt_script()
    section_names = {s.name for s in script.sections}
    assert "hook" in section_names
    assert "payoff" in section_names


def test_zidane_script_hook_is_short():
    script = generate_zidane_headbutt_script()
    hook = next(s for s in script.sections if s.name == "hook")
    assert hook.estimated_duration <= 4.0, (
        f"Hook too long: {hook.estimated_duration:.1f}s"
    )


def test_haaland_script_full_text_non_empty():
    script = generate_haaland_origin_script()
    assert len(script.full_text) > 50


def test_script_feasibility_check_ok():
    script = generate_zidane_headbutt_script()
    result = check_script_feasibility(script, budget_secs=40.0)
    assert result["ok"] is True


def test_script_feasibility_check_fails_tight_budget():
    script = generate_zidane_headbutt_script()
    result = check_script_feasibility(script, budget_secs=5.0)
    assert result["ok"] is False
    assert len(result["issues"]) > 0


def test_script_word_count_positive():
    script = generate_zidane_headbutt_script()
    assert script.total_word_count > 0


def test_script_source_note_non_empty():
    script = generate_zidane_headbutt_script()
    assert "wikipedia" in script.source_note.lower()
