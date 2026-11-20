#!/usr/bin/env python3
"""
Beyond The Pitch — comprehensive weekly growth report.

Queries the local SQLite DB, analytics data, and growth intelligence
to produce a full summary:
  - Videos produced vs target
  - Views and subscriber gains
  - Top 5 performing videos
  - Best-performing players and moment types
  - Retention insights
  - Progress toward YouTube monetization
  - Recommendations for the next 7 days
  - Disk status and blocker checklist

Usage:
  source venv/bin/activate
  python scripts/weekly_report.py              # print to stdout
  python scripts/weekly_report.py --save       # also save to output/reports/
  python scripts/weekly_report.py --days 14    # extend lookback window
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from src.analytics.growth_intelligence import generate_weekly_report
from src.core.database import init_db
from src.core.disk_monitor import disk_status_report, get_free_mb, MINIMUM_FREE_MB
from src.core.logger import configure_logging

configure_logging()
_WEEKLY_TARGET = 21


def _section(title: str, width: int = 60) -> str:
    return f"\n── {title} {'─' * max(0, width - len(title) - 4)}"


def _fmt(label: str, value: object, width: int = 32) -> str:
    return f"  {label:<{width}} {value}"


def _credential_status() -> list[str]:
    lines = []
    creds = {
        "YOUTUBE_CLIENT_ID":     "YouTube upload",
        "YOUTUBE_CLIENT_SECRET": "YouTube upload",
        "ANTHROPIC_API_KEY":     "Claude script writing (MockScriptWriter fallback available)",
        "OPENAI_API_KEY":        "OpenAI TTS (optional)",
        "YOUTUBE_API_KEY":       "YouTube Data API (trending research)",
    }
    for key, purpose in creds.items():
        status = "✓" if os.environ.get(key) else "✗ missing"
        lines.append(f"  {status}  {key} ({purpose})")
    return lines


def build_report(days: int = 7) -> str:
    report = generate_weekly_report(days=days)
    lines: list[str] = [
        "=" * 60,
        "  BEYOND THE PITCH — Weekly Growth Report",
        f"  Period: {report.period_start} → {report.period_end}  ({days} days)",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]

    # ── Production ────────────────────────────────────────────────────────────
    lines.append(_section("PRODUCTION"))
    gap = _WEEKLY_TARGET - report.videos_published
    target_str = f"{report.videos_published} / {_WEEKLY_TARGET} target"
    if gap > 0:
        target_str += f"  (↓{gap} below target)"
    lines.append(_fmt("Videos published:", target_str))
    lines.append(_fmt("Total views:", f"{report.total_views:,}"))
    lines.append(_fmt("Subscribers gained:", report.total_subscribers_gained))
    lines.append("")

    # ── Top videos ────────────────────────────────────────────────────────────
    lines.append(_section("TOP PERFORMING VIDEOS"))
    if report.top_5_videos:
        for i, v in enumerate(report.top_5_videos, 1):
            player = f" [{v['player']}]" if v["player"] else ""
            lines.append(f"  {i}. {v['title'] or v['youtube_id']}{player}")
            lines.append(f"     Views: {v['views']:,}  |  {v['url'] or '(no url)'}")
    else:
        lines.append("  No uploaded videos yet.")
        lines.append("  Next step: python scripts/upload_first_short.py")
    lines.append("")

    # ── Performance patterns ──────────────────────────────────────────────────
    lines.append(_section("PERFORMANCE PATTERNS"))
    lines.append(_fmt("Best player:", report.best_player))
    lines.append(_fmt("Best moment type:", report.best_moment_type))
    lines.append(_fmt("Worst format:", report.worst_format))
    lines.append(_fmt("Retention:", report.retention_insight))
    lines.append(f"  Note: {report.data_note[:100]}")
    lines.append("")

    # ── Monetization ─────────────────────────────────────────────────────────
    lines.append(_section("MONETIZATION PROGRESS"))
    lines.append(f"  {report.monetization_progress}")
    lines.append("")
    lines.append("  YouTube Partner Program thresholds (Canada):")
    lines.append("    Fan-funding (Super Thanks):  500 subs + 3,000 watch hours")
    lines.append("    Advertising revenue:         1,000 subs + 4,000 watch hours")
    lines.append("    Shorts ad revenue:           1,000 subs + 10M Shorts views (90 days)")
    lines.append("")

    # ── Disk and credentials ──────────────────────────────────────────────────
    lines.append(_section("SYSTEM STATUS"))
    free_mb = get_free_mb()
    disk_ok = "OK" if free_mb >= MINIMUM_FREE_MB else "⚠  LOW — may prevent rendering"
    lines.append(_fmt("Disk:", f"{free_mb:.0f} MB free  [{disk_ok}]"))
    lines.append("")
    lines.append("  Credentials:")
    lines.extend(_credential_status())
    lines.append("")

    # ── Recommendations ───────────────────────────────────────────────────────
    lines.append(_section("RECOMMENDATIONS (next 7 days)"))
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"  {i}. {rec}")
    lines.append("")

    # ── 90-day milestone tracker ──────────────────────────────────────────────
    lines.append(_section("90-DAY MILESTONE TRACKER"))
    lines.append("  Days  1–30: Publish 90 Shorts. Experiment with players, moments, music.")
    lines.append("  Days 31–60: Identify top-performing formats. Double down on winners.")
    lines.append("  Days 61–90: Scale best formats. Prepare for monetization application.")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Beyond The Pitch weekly growth report")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days")
    parser.add_argument("--save", action="store_true", help="Save to output/reports/")
    args = parser.parse_args()

    init_db()
    report = build_report(days=args.days)
    print(report)

    if args.save:
        reports_dir = _ROOT / "output" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        fname = f"weekly_report_{date.today().isoformat()}.txt"
        (reports_dir / fname).write_text(report, encoding="utf-8")
        print(f"\nSaved: {reports_dir / fname}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
