"""
trend_report.py — Football Shorts trend discovery and production planning report.

Runs the full pipeline:
  1. Discovers football Shorts via YouTube Data API (or mock fixture data)
  2. Analyses metadata patterns across top Shorts
  3. Ranks 5 original video ideas
  4. Builds a complete production plan for the top-ranked concept
  5. Models hypothetical earnings
  6. Prints a research report and saves it to output/trend_report_YYYY-MM-DD.md

Usage:
    source venv/bin/activate
    export YOUTUBE_API_KEY=your_key_here   # or omit for mock mode
    python scripts/trend_report.py

No video is rendered. No content is uploaded. No competitor revenue is claimed.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")   # load YOUTUBE_API_KEY before any module reads env vars

import src.core.database as db_module
db_module.DB_PATH = ROOT / "data" / "trend_discovery.db"
db_module.init_db()

from src.core.config import get_section
from src.core.kill_switch import disarm
from src.planning.idea_ranker import apply_production_type, rank_ideas
from src.planning.models import VideoIdea
from src.planning.script_generator import (
    check_script_feasibility,
    generate_haaland_origin_script,
    generate_zidane_headbutt_script,
)
from src.planning.shot_planner import build_plan_haaland_origin, build_plan_zidane_headbutt
from src.trends.analyzer import (
    analyse_short,
    build_earnings_scenarios,
    earnings_report,
    summarise_patterns,
    viral_tier,
)
from src.trends.discovery import discover_shorts
from src.trends.models import DiscoveredShort
from src.trends.soccer_filter import RelevanceResult, age_tier, assess_soccer_relevance
from src.trends.youtube_client import YouTubeClient

disarm()


def _header(text: str, level: int = 1) -> str:
    return "\n" + "#" * level + " " + text + "\n"


def _divider() -> str:
    return "\n" + "─" * 72 + "\n"


def build_idea_shortlist(
    discovered: list,
    top_analyses: list,
) -> list[VideoIdea]:
    """Define 5 original concepts, then score and rank them."""
    ideas = [
        VideoIdea(
            title="The Headbutt That Ended a Legend",
            hook="2006 World Cup Final. 10 minutes left. And Zidane completely lost it.",
            concept_summary=(
                "Zidane's red card in his final-ever professional game — the headbutt on "
                "Materazzi and what Materazzi said."
            ),
            content_type="player_story",
            hook_quality=0.92,
            inspired_by=[],
            target_duration_secs=35,
            estimated_views_range="1M–5M",
        ),
        VideoIdea(
            title="Haaland's Father Was in Prison During His First Big Game",
            hook="His father was in prison. That's where the hunger started.",
            concept_summary=(
                "Alfie Haaland's career was ended by Roy Keane's deliberate tackle. "
                "Erling grew up with that story."
            ),
            content_type="player_story",
            hook_quality=0.92,
            inspired_by=[],
            target_duration_secs=30,
            estimated_views_range="2M–8M",
        ),
        VideoIdea(
            title="The Goalkeeper Who Stopped a Civil War",
            hook="One football match stopped a civil war. No, seriously.",
            concept_summary=(
                "Didier Drogba's story: how he pleaded on live TV to stop the "
                "Ivory Coast civil war, and it worked."
            ),
            content_type="player_story",
            hook_quality=0.88,
            inspired_by=[],
            target_duration_secs=35,
            estimated_views_range="500K–3M",
        ),
        VideoIdea(
            title="Messi Was Diagnosed with a Growth Hormone Deficiency at 11",
            hook="At 11, doctors told Messi he might never grow. He grew into the greatest.",
            concept_summary=(
                "Messi's growth hormone deficiency diagnosis, Barcelona paying for his "
                "treatment at 13, and what that decision produced."
            ),
            content_type="player_story",
            hook_quality=0.90,
            inspired_by=[],
            target_duration_secs=30,
            estimated_views_range="2M–10M",
        ),
        VideoIdea(
            title="The Player Who Scored in a World Cup Final and Was Completely Forgotten",
            hook="He scored in a World Cup Final. Nobody remembers his name.",
            concept_summary=(
                "A deep-cut historical fact Short: a player who scored in a famous "
                "World Cup Final but is entirely overshadowed by team legends."
            ),
            content_type="record_fact",
            hook_quality=0.85,
            inspired_by=[],
            target_duration_secs=28,
            estimated_views_range="500K–2M",
        ),
    ]

    # Apply production and licensing types to each idea
    for idea in ideas:
        apply_production_type(
            idea,
            production_type="wikipedia_photos_plus_graphics",
            license_type="cc_by_wikimedia",
        )

    return rank_ideas(ideas, discovered, top_analyses)


def _soccer_tier_label(tier: str) -> str:
    return {"soccer": "soccer", "likely_soccer": "likely soccer",
            "uncertain": "uncertain", "other": "other sport"}.get(tier, tier)


def _short_table_row(rank: int, s: DiscoveredShort, rel: RelevanceResult, atier: str) -> str:
    pub_date = s.published_at[:10] if s.published_at else "?"
    snap = "1st" if s.is_first_snapshot else f"#{s.snapshot_count}"
    vtier = viral_tier(s.view_count)
    return (
        f"| {rank} | {s.title[:48]} | {s.channel_title[:22]} | {pub_date} | "
        f"{s.view_count:,} | {s.duration_secs}s | {snap} | {vtier} | "
        f"[link]({s.url}) |"
    )


def run() -> str:
    cfg = get_section("trends")
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    client = YouTubeClient(api_key=api_key or None,
                           quota_budget=cfg.get("quota_daily_budget", 8000))

    mode_label = ("LIVE (YouTube Data API v3)" if not client.is_mock
                  else "MOCK (fixture data — no API key)")

    print(f"Mode: {mode_label}")
    print("Running discovery (uses cached results if within 24h)…")

    discovered = discover_shorts(
        client=client,
        queries=cfg.get("default_queries"),
        min_views=cfg.get("min_views_threshold", 100_000),
        channel_handles=cfg.get("channel_handles_to_track"),
        cache_ttl_hours=cfg.get("cache_ttl_hours", 24),
    )

    # ── Soccer relevance filter (metadata-only — no video content inspected) ──
    relevance: dict[str, RelevanceResult] = {
        s.video_id: assess_soccer_relevance(s.title, s.channel_title)
        for s in discovered
    }
    soccer_shorts = [s for s in discovered if relevance[s.video_id].is_soccer]
    excluded = [s for s in discovered if not relevance[s.video_id].is_soccer]

    # ── Age tiers ─────────────────────────────────────────────────────────────
    breakout = [s for s in soccer_shorts if age_tier(s.published_at) == "RECENT_BREAKOUT"]
    recent   = [s for s in soccer_shorts if age_tier(s.published_at) == "RECENT_SUCCESS"]
    evergrn  = [s for s in soccer_shorts if age_tier(s.published_at) == "EVERGREEN"]

    # ── Pattern analysis on soccer-only set ──────────────────────────────────
    analyses = [analyse_short(s) for s in soccer_shorts]
    patterns = summarise_patterns(analyses)

    # ── Concepts, production plan, earnings ───────────────────────────────────
    ideas = build_idea_shortlist(soccer_shorts, analyses)
    top_plan = build_plan_zidane_headbutt()
    top_script = generate_zidane_headbutt_script()
    script_check = check_script_feasibility(top_script, top_plan.idea.target_duration_secs)
    haaland_script = generate_haaland_origin_script()
    earnings = build_earnings_scenarios(monthly_videos=30)

    # ── Quota breakdown (read from DB — verifiable) ───────────────────────────
    qbd = client.quota_breakdown_today()

    # ── Report ────────────────────────────────────────────────────────────────
    lines: list[str] = []
    today = date.today().isoformat()
    retrieved_at = discovered[0].collected_at + " UTC" if discovered else today

    lines.append("# Beyond The Pitch — Football Shorts Trend Report")
    lines.append(f"**Generated:** {today}  ")
    lines.append(f"**Data source:** {mode_label}  ")
    if client.is_mock:
        lines.append(
            "> ⚠️ MOCK MODE: All discovery data is fixture data. "
            "Set YOUTUBE_API_KEY to run against the live API."
        )
    lines.append(f"**Metrics retrieved:** {retrieved_at}  ")
    lines.append("")

    # ── Section 1: Discovery summary ──────────────────────────────────────────
    lines.append("## 1. Discovery & Relevance Summary")
    lines.append(f"- Total duration-compatible videos found: **{len(discovered)}**")
    lines.append(f"- Classified soccer (metadata-only): **{sum(1 for r in relevance.values() if r.tier == 'soccer')}**")
    lines.append(f"- Classified likely soccer (metadata-only): **{sum(1 for r in relevance.values() if r.tier == 'likely_soccer')}**")
    lines.append(f"- Uncertain (excluded from report): **{sum(1 for r in relevance.values() if r.tier == 'uncertain')}**")
    lines.append(f"- Other sport / irrelevant (excluded): **{sum(1 for r in relevance.values() if r.tier == 'other')}**")
    lines.append(f"- Soccer set: RECENT BREAKOUT **{len(breakout)}** | RECENT SUCCESS **{len(recent)}** | EVERGREEN **{len(evergrn)}**")
    lines.append("")
    lines.append("> All relevance classification is **metadata-only** (title + channel title).")
    lines.append("> Videos have NOT been watched or inspected beyond title text.")
    lines.append("> Classification is a heuristic estimate — human review is required before production.")
    lines.append("")

    # ── Section 2: Quota breakdown ────────────────────────────────────────────
    lines.append("## 2. API Quota Used Today")
    total_units = qbd["total"]
    lines.append(f"**Total: {total_units} units** (read from api_usage DB — row-level verifiable)")
    if not client.is_mock:
        lines.append("")
        lines.append("| Method | Calls | Units |")
        lines.append("|--------|-------|-------|")
        breakdown_total = 0
        for method, data in qbd["methods"].items():
            if data["calls"] > 0:
                lines.append(f"| {method} | {data['calls']} | {data['units']} |")
                breakdown_total += data["units"]
        lines.append(f"| **Total** | | **{breakdown_total}** |")
        if breakdown_total != total_units:
            lines.append(f"> ⚠️ Breakdown sum ({breakdown_total}) ≠ DB total ({total_units}) — investigate api_usage table.")
        else:
            lines.append(f"> ✓ Breakdown sums to DB total exactly.")
        lines.append(f"  ")
        budget = cfg.get("quota_daily_budget", 8000)
        pct = round(total_units / budget * 100)
        lines.append(f"Budget: {total_units} / {budget} units used ({pct}% of daily soft ceiling).  ")
        lines.append(f"Hard ceiling: 9,000 units/day (enforced in code).  ")
    lines.append("")

    # ── Section 3: Top soccer Shorts ─────────────────────────────────────────
    TABLE_HEADER = (
        "| # | Title | Channel | Published | Views | Duration | Snapshot | Viral | URL |"
    )
    TABLE_SEP = "|---|-------|---------|-----------|-------|----------|----------|-------|-----|"

    lines.append("## 3. Top 20 Soccer Shorts")
    lines.append(
        "_All classification is **metadata-only**. Duration ≤ 180s is a necessary "
        "but not sufficient condition for Short classification. "
        "Single-snapshot records show lifetime views — growth rate is unknown._"
    )
    lines.append("")

    rank = 1
    for tier_label, tier_shorts in [
        ("RECENT BREAKOUT — published within 30 days", breakout),
        ("RECENT SUCCESS — published 31–90 days ago", recent),
        ("EVERGREEN — older than 90 days", evergrn),
    ]:
        shown = [s for s in tier_shorts if rank <= 20][:max(0, 20 - rank + 1)]
        if not shown and not any(len(t) > 0 for t in [breakout, recent, evergrn]):
            continue
        lines.append(f"### {tier_label}")
        if not tier_shorts:
            lines.append("_No videos in this tier._")
            lines.append("")
            continue
        lines.append(TABLE_HEADER)
        lines.append(TABLE_SEP)
        for s in tier_shorts:
            if rank > 20:
                break
            rel = relevance[s.video_id]
            lines.append(_short_table_row(rank, s, rel, age_tier(s.published_at)))
            rank += 1
        lines.append("")

    if rank == 1:
        lines.append("_No soccer-relevant Shorts found in this run._")
        lines.append("")

    # ── Section 4: Excluded videos (sample) ───────────────────────────────────
    if excluded:
        lines.append("## 4. Excluded Videos (sample — first 5)")
        lines.append(
            "_These videos were excluded because metadata signals suggest non-soccer content. "
            "Classification is metadata-only and may be wrong._"
        )
        lines.append("")
        for s in excluded[:5]:
            rel = relevance[s.video_id]
            neg = ", ".join(rel.negative_signals[:2]) or "no soccer signals"
            lines.append(f"- **{s.title[:60]}** ({s.channel_title}) — {rel.tier}: {neg}")
        lines.append("")

    # ── Section 5: Metadata pattern analysis ─────────────────────────────────
    lines.append("## 5. Metadata Pattern Analysis (soccer set only)")
    lines.append(
        "> Derived from **title text only** (metadata_only). "
        "No video content was accessed or viewed."
    )
    lines.append("")
    lines.append("**Hook styles:**")
    for style, count in list(patterns.get("hook_styles", {}).items())[:5]:
        lines.append(f"- {style}: {count}")
    lines.append("")
    lines.append("**Subject categories:**")
    for subj, count in list(patterns.get("subject_categories", {}).items())[:5]:
        lines.append(f"- {subj}: {count}")
    lines.append("")
    lines.append("**Structural signals:**")
    lines.append(f"- Titles containing a player name: {patterns.get('pct_with_player_name', 0)}%")
    lines.append(f"- Titles containing a number: {patterns.get('pct_with_number', 0)}%")
    lines.append(f"- Titles as a question: {patterns.get('pct_with_question', 0)}%")
    lines.append("")

    # ── Section 6: Channel profiles ───────────────────────────────────────────
    lines.append("## 6. Channel Profiles (top soccer channels)")
    lines.append(
        "Subscriber counts are API-reported and may be rounded. "
        "Data retrieved via channels.list (1 unit each).  "
    )
    lines.append("")
    seen_channels: dict[str, tuple[str, int]] = {}
    for s in soccer_shorts:
        if s.channel_id not in seen_channels:
            seen_channels[s.channel_id] = (s.channel_title, s.channel_subscriber_count)
    for cid, (ctitle, subs) in list(seen_channels.items())[:10]:
        subs_label = f"{subs:,}" if subs > 0 else "hidden"
        lines.append(f"- **{ctitle}** — {subs_label} subscribers")
    lines.append("")

    # ── Section 7: Original concept shortlist ────────────────────────────────
    lines.append("## 7. Original Video Concept Shortlist")
    lines.append(
        "_Ranked by: trend_strength 20% + originality 20% + production_feasibility 20% "
        "+ licensing_feasibility 20% + audience_interest 15% + hook_quality 5%_"
    )
    lines.append("")
    lines.append(
        "> Trend strength scores reflect patterns observed from title metadata of discovered videos. "
        "No claim is made about why specific videos went viral — that requires watching the content."
    )
    lines.append("")
    for rank_i, idea in enumerate(ideas[:5], 1):
        status = "BLOCKED" if idea.is_blocked else "FEASIBLE"
        lines.append(f"### {rank_i}. {idea.title}")
        lines.append(f"**Score:** {idea.total_score:.2f} | **Status:** {status}  ")
        lines.append(f"**Hook:** _{idea.hook}_  ")
        lines.append(f"**Type:** {idea.content_type} | **Target:** {idea.target_duration_secs}s  ")
        lines.append(f"**Est. views:** {idea.estimated_views_range}  ")
        lines.append("")
        lines.append("```")
        lines.append(idea.score_breakdown())
        lines.append("```")
        if idea.is_blocked:
            lines.append(f"**Blocking reason:** {idea.blocking_reason}")
        lines.append("")

    # ── Section 8: Production plan — top concept ─────────────────────────────
    lines.append("## 8. Production Plan — Concept #1")
    lines.append(f"### {top_plan.idea.title}")
    lines.append(f"**Status: {top_plan.production_status}**  ")
    lines.append("")
    lines.append("#### Honesty note")
    lines.append(
        "All shot descriptions below are based on RESEARCH (Wikipedia, public records). "
        "No competitor videos were watched to derive these shot ideas. "
        "Asset status is AVAILABLE only where a commercially licensed or original source exists. "
        "Wikimedia URLs require individual verification on the file page before use."
    )
    lines.append("")
    lines.append("#### Shot-by-Shot Plan (20–35s)")
    lines.append(top_plan.status_report())
    lines.append("")
    lines.append("#### Script")
    lines.append("```")
    lines.append(top_script.report())
    lines.append("```")
    lines.append("")
    lines.append("**Script feasibility:**")
    if script_check["ok"]:
        lines.append(
            f"✓ Fits within {script_check['budget_secs']:.0f}s budget "
            f"({script_check['total_words']} words, ~{script_check['estimated_secs']:.1f}s at 2.8 wps)"
        )
    else:
        for issue in script_check["issues"]:
            lines.append(f"⚠ {issue}")
    lines.append("")
    lines.append("#### Concept #2 Script Preview")
    lines.append("```")
    lines.append(haaland_script.report())
    lines.append("```")
    lines.append("")

    # ── Section 9: Production blockers ───────────────────────────────────────
    lines.append("## 9. Production Blockers")
    lines.append(
        "These must be resolved before any concept can be commercially distributed:"
    )
    lines.append("")
    lines.append(
        "1. **Narration TTS** — macOS Samantha voice is NOT licensed for monetised content. "
        "Requires ElevenLabs (commercial plan, $5+/mo) or Amazon Polly."
    )
    lines.append(
        "2. **Wikimedia image verification** — Each image URL must be individually confirmed "
        "on the Wikimedia file page. License type varies per file."
    )
    lines.append(
        "3. **Music selection** — Specific YouTube Audio Library tracks must be selected "
        "and their individual attribution requirements verified."
    )
    lines.append(
        "4. **Match footage** — Any concept requiring broadcast clips is BLOCKED until "
        "commercial licensing is confirmed with the rights holder."
    )
    lines.append("")

    # ── Section 10: Earnings model ────────────────────────────────────────────
    lines.append("## 10. Hypothetical Earnings Model")
    lines.append("```")
    lines.append(earnings_report(earnings))
    lines.append("```")
    lines.append(
        "_Hypothetical only. Actual earnings depend on monetisation eligibility, "
        "RPM fluctuations, and actual views. No competitor revenue figures used._"
    )
    lines.append("")

    # ── Section 11: Next steps ────────────────────────────────────────────────
    lines.append("## 11. Next Steps Before Production")
    lines.append("1. Verify each Wikimedia image URL on the Wikimedia file page — confirm license.")
    lines.append("2. Set up ElevenLabs or Amazon Polly (commercial license) and add key to `.env`.")
    lines.append("3. Select 2–3 YouTube Audio Library tracks; confirm attribution requirements.")
    lines.append("4. Human review of script and shot plan before any render.")
    lines.append(
        "5. Re-run discovery after 24h cache expires to get view velocity data "
        "(2nd snapshot enables growth-rate calculation)."
    )
    lines.append("")

    report_text = "\n".join(lines)
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / f"trend_report_{today}.md"
    report_path.write_text(report_text, encoding="utf-8")
    return str(report_path)


if __name__ == "__main__":
    path = run()
    print(f"\nReport saved: {path}")
