"""Tests for production planning models."""

from src.planning.models import AssetRequirement, ProductionPlan, Shot, VideoIdea


def _available_asset(description: str = "Test asset") -> AssetRequirement:
    return AssetRequirement(
        description=description,
        asset_type="graphic",
        status="AVAILABLE",
        source_name="Original graphics",
        source_url="",
        license="Original work",
        attribution_required=False,
    )


def _blocked_asset(description: str = "Blocked asset") -> AssetRequirement:
    return AssetRequirement(
        description=description,
        asset_type="video_clip",
        status="BLOCKED",
        source_name="None",
        source_url="",
        license="None",
        attribution_required=False,
        notes="No commercial license available",
    )


def _shot(n: int, asset: AssetRequirement | None = None) -> Shot:
    return Shot(
        shot_number=n,
        duration_secs=5.0,
        description=f"Shot {n} description",
        on_screen_caption="TEST CAPTION",
        asset=asset or _available_asset(),
        narration_text="Test narration.",
    )


def _idea(**kwargs) -> VideoIdea:
    defaults = dict(
        title="Test Idea",
        hook="Test hook",
        concept_summary="A test concept.",
        content_type="player_story",
        trend_strength=0.8,
        originality=0.9,
        production_feasibility=0.9,
        licensing_feasibility=0.9,
        audience_interest=0.85,
        hook_quality=0.9,
        target_duration_secs=30,
    )
    return VideoIdea(**{**defaults, **kwargs})


# ── AssetRequirement ──────────────────────────────────────────────────────────

def test_available_asset_is_cleared():
    asset = _available_asset()
    assert asset.is_cleared() is True


def test_blocked_asset_not_cleared():
    asset = _blocked_asset()
    assert asset.is_cleared() is False


# ── Shot ──────────────────────────────────────────────────────────────────────

def test_shot_clearable_with_available_asset():
    shot = _shot(1, _available_asset())
    assert shot.is_clearable is True


def test_shot_not_clearable_with_blocked_asset():
    shot = _shot(1, _blocked_asset())
    assert shot.is_clearable is False


# ── VideoIdea ─────────────────────────────────────────────────────────────────

def test_idea_total_score_in_range():
    idea = _idea()
    assert 0.0 <= idea.total_score <= 1.0


def test_idea_total_score_weights_sum():
    """Score with all dimensions at 1.0 should equal 1.0."""
    idea = _idea(
        trend_strength=1.0, originality=1.0, production_feasibility=1.0,
        licensing_feasibility=1.0, audience_interest=1.0, hook_quality=1.0,
    )
    assert abs(idea.total_score - 1.0) < 0.001


def test_idea_total_score_zero():
    idea = _idea(
        trend_strength=0.0, originality=0.0, production_feasibility=0.0,
        licensing_feasibility=0.0, audience_interest=0.0, hook_quality=0.0,
    )
    assert idea.total_score == 0.0


def test_idea_not_blocked_by_default():
    idea = _idea()
    assert not idea.is_blocked


def test_idea_blocked_with_reason():
    idea = _idea(blocking_reason="No match footage available")
    assert idea.is_blocked


def test_idea_score_breakdown_contains_all_dimensions():
    idea = _idea()
    breakdown = idea.score_breakdown()
    for dim in ("trend_strength", "originality", "production_feasibility",
                "licensing_feasibility", "audience_interest", "hook_quality"):
        assert dim in breakdown


# ── ProductionPlan ────────────────────────────────────────────────────────────

def test_plan_available_all_clear():
    idea = _idea()
    shots = [_shot(i) for i in range(1, 4)]
    plan = ProductionPlan(idea=idea, shots=shots, full_script="test script")
    assert plan.production_status == "AVAILABLE"
    assert plan.blocked_shots == []


def test_plan_blocked_when_any_shot_blocked():
    idea = _idea()
    shots = [_shot(1), _shot(2, _blocked_asset()), _shot(3)]
    plan = ProductionPlan(idea=idea, shots=shots, full_script="test script")
    assert plan.production_status == "BLOCKED"
    assert 2 in plan.blocked_shots


def test_plan_total_duration():
    idea = _idea()
    shots = [_shot(i) for i in range(1, 5)]  # 4 shots × 5s = 20s
    plan = ProductionPlan(idea=idea, shots=shots, full_script="test")
    assert plan.total_duration_secs == 20.0


def test_plan_status_report_contains_title():
    idea = _idea(title="My Brilliant Idea")
    shots = [_shot(1)]
    plan = ProductionPlan(idea=idea, shots=shots, full_script="")
    assert "My Brilliant Idea" in plan.status_report()


def test_plan_blocked_music_is_flagged():
    idea = _idea()
    shots = [_shot(1)]
    blocked_music = AssetRequirement(
        description="Background music",
        asset_type="audio_music",
        status="BLOCKED",
        source_name="None",
        source_url="",
        license="None",
        attribution_required=False,
    )
    plan = ProductionPlan(
        idea=idea, shots=shots, full_script="",
        music_requirement=blocked_music,
    )
    assert plan.production_status == "BLOCKED"
    assert -1 in plan.blocked_shots  # -1 flags music
