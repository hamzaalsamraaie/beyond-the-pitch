"""Tests for trend discovery data models."""

from src.trends.models import (
    DiscoveredShort,
    EarningsScenario,
    MetadataAnalysis,
    TrendSnapshot,
)


def _short(**kwargs) -> DiscoveredShort:
    defaults = dict(
        video_id="abc123",
        title="Messi's greatest goal ever",
        channel_id="UCtest",
        channel_title="Football Moments",
        published_at="2024-11-01T10:00:00Z",
        view_count=5_000_000,
        duration_secs=45,
        channel_subscriber_count=500_000,
        viral_score=250_000.0,
        adjusted_viral_score=354.0,
        age_days=15.0,
    )
    return DiscoveredShort(**{**defaults, **kwargs})


def test_discovered_short_url():
    s = _short(video_id="xYz123")
    assert s.url == "https://www.youtube.com/shorts/xYz123"


def test_discovered_short_age_label_days():
    s = _short(age_days=5.0)
    assert "day" in s.age_label


def test_discovered_short_age_label_weeks():
    s = _short(age_days=14.0)
    assert "week" in s.age_label


def test_discovered_short_age_label_months():
    s = _short(age_days=90.0)
    assert "month" in s.age_label


def test_discovered_short_summary_line_contains_views():
    s = _short(view_count=1_234_567)
    line = s.summary_line()
    assert "1,234,567" in line


def test_discovered_short_summary_line_hides_zero_subs():
    s = _short(channel_subscriber_count=0)
    assert "subs hidden" in s.summary_line()


def test_earnings_scenario_monthly_revenue():
    scenario = EarningsScenario(
        scenario_name="mid",
        rpm_usd=0.07,
        monthly_videos=30,
        avg_views_per_short=200_000,
    )
    # 30 × 200,000 = 6,000,000 views → 6,000 × $0.07 = $420/month
    assert abs(scenario.monthly_revenue_usd - 420.0) < 0.01


def test_earnings_scenario_annual_revenue():
    scenario = EarningsScenario(
        scenario_name="conservative",
        rpm_usd=0.03,
        monthly_videos=30,
        avg_views_per_short=50_000,
        months=12,
    )
    assert abs(scenario.annual_revenue_usd - scenario.monthly_revenue_usd * 12) < 0.01


def test_earnings_report_line_format():
    s = EarningsScenario("mid", 0.07, 30, 200_000)
    line = s.report_line()
    assert "mid" in line.lower()
    assert "$" in line


def test_metadata_analysis_label():
    a = MetadataAnalysis(video_id="abc", analysis_type="metadata_only")
    assert "METADATA_ONLY" in a.label()


def test_trend_snapshot_fields():
    ts = TrendSnapshot(
        video_id="v1",
        title="Test",
        channel_title="Chan",
        view_count=100_000,
        like_count=5_000,
        comment_count=200,
        subscriber_count=50_000,
    )
    assert ts.video_id == "v1"
    assert ts.view_count == 100_000
    assert ts.snapshot_at != ""
