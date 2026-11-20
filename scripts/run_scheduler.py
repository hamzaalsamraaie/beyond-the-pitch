#!/usr/bin/env python3
"""
Beyond The Pitch — daily video scheduler.

Runs three production slots per day at:
  12:00 PM ET  (slot 1 — America/Toronto)
   5:00 PM ET  (slot 2)
   9:00 PM ET  (slot 3)

Each slot:
  1. Checks the kill switch — halts immediately if armed
  2. Runs StoryboardPipeline to discover and rank stories
  3. Runs AutoProducer to render, QC, and upload each storyboard
  4. Logs the result to logs/scheduler.log

Usage:
  source venv/bin/activate
  python scripts/run_scheduler.py                     # run continuously (foreground)
  python scripts/run_scheduler.py --once              # run one slot immediately and exit
  python scripts/run_scheduler.py --dry-run           # skip render/upload
  python scripts/run_scheduler.py --schedule-next-day # schedule publication for next-day slot

Environment variables read from .env:
  ANTHROPIC_API_KEY   — optional; uses MockScriptWriter if absent
  YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET — optional; skips upload if absent

Kill switch:
  touch config/kill_switch.flag     # halt all jobs
  rm config/kill_switch.flag        # resume
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.database import init_db
from src.core.kill_switch import is_active as kill_switch_active
from src.core.logger import configure_logging, get_logger
from src.production.auto_producer import AutoProducer
from src.research.models import ContentType
from src.research.pipeline import StoryboardPipeline
from src.research.providers import MockResearchProvider, WikipediaResearchProvider
from src.research.rss_provider import RSSResearchProvider
from src.research.script_writer import ClaudeScriptWriter, MockScriptWriter

configure_logging()
logger = get_logger("scheduler")

_TZ = "America/Toronto"
_SLOT_HOURS = [12, 17, 21]  # 12PM, 5PM, 9PM ET


def _next_publish_time(slot_num: int) -> str:
    """
    Return an ISO 8601 UTC timestamp for tomorrow's occurrence of this slot's time.
    Used to schedule YouTube publication one day ahead via the publishAt API field.
    """
    tz = ZoneInfo(_TZ)
    now = datetime.now(tz)
    hour = _SLOT_HOURS[slot_num % 3]
    tomorrow = (now + timedelta(days=1)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    # Convert to UTC, format as RFC 3339
    utc = tomorrow.astimezone(ZoneInfo("UTC"))
    return utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")


_CONTENT_ROTATION: list[ContentType] = [
    ContentType.FOOTBALL_MOMENTS,
    ContentType.PLAYER_STORIES,
    ContentType.FOOTBALL_MOTIVATION,
]


def _build_pipeline() -> StoryboardPipeline:
    """Build the research pipeline with the best available provider and writer."""
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))

    provider: object
    if has_anthropic or True:
        # Try RSS first; fall back to Wikipedia if no network
        try:
            provider = RSSResearchProvider()
            logger.info("scheduler_provider", provider="rss")
        except Exception:
            provider = WikipediaResearchProvider()
            logger.info("scheduler_provider", provider="wikipedia")
    else:
        provider = MockResearchProvider()
        logger.info("scheduler_provider", provider="mock")

    writer = ClaudeScriptWriter() if has_anthropic else MockScriptWriter()
    logger.info("scheduler_writer", writer=type(writer).__name__)

    return StoryboardPipeline(
        provider=provider,
        writer=writer,
        min_score_threshold=0.35,
        topics_per_type=5,
    )


def run_slot(
    slot_num: int,
    dry_run: bool = False,
    auto_publish: bool = False,
    schedule_next_day: bool = False,
) -> None:
    """
    Run one production slot. Produces up to one Short per content type.
    Skips silently if kill switch is armed.

    schedule_next_day: if True, sets publishAt to tomorrow's slot time so YouTube
    automatically publishes at the right time without manual intervention.
    """
    if kill_switch_active():
        logger.warning("scheduler_kill_switch_active", slot=slot_num)
        return

    logger.info("scheduler_slot_start", slot=slot_num)

    publish_at = _next_publish_time(slot_num) if schedule_next_day else ""
    if publish_at:
        logger.info("scheduler_publish_at", publish_at=publish_at, slot=slot_num)

    try:
        pipeline = _build_pipeline()
        storyboards = pipeline.run(content_types=[_CONTENT_ROTATION[slot_num % 3]])
    except Exception as exc:
        logger.error("scheduler_pipeline_failed", slot=slot_num, error=str(exc)[:300])
        return

    if not storyboards:
        logger.warning("scheduler_no_storyboards", slot=slot_num)
        return

    producer = AutoProducer(
        auto_publish=auto_publish,
        dry_run=dry_run,
        publish_at=publish_at,
    )

    for sb in storyboards:
        if kill_switch_active():
            logger.warning("scheduler_kill_switch_mid_slot", slot=slot_num)
            break

        logger.info("scheduler_producing", title=sb.title[:60])
        result = producer.produce_one(sb)

        if result.success:
            logger.info(
                "scheduler_slot_success",
                slot=slot_num,
                title=sb.title[:60],
                youtube_url=result.youtube_url or "(no credentials)",
                stages=result.stages_completed,
            )
        else:
            logger.warning(
                "scheduler_slot_failed",
                slot=slot_num,
                title=sb.title[:60],
                reason=result.failure_reason[:200],
                stages=result.stages_completed,
            )

    logger.info("scheduler_slot_complete", slot=slot_num)


def main() -> int:
    parser = argparse.ArgumentParser(description="Beyond The Pitch scheduler")
    parser.add_argument(
        "--once", action="store_true",
        help="Run one slot immediately and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run pipeline logic but skip render and upload",
    )
    parser.add_argument(
        "--auto-publish", action="store_true",
        help="Automatically publish videos publicly after upload (use with care)",
    )
    parser.add_argument(
        "--slot", type=int, default=0,
        help="Which slot to run (0=12PM, 1=5PM, 2=9PM) — only used with --once",
    )
    parser.add_argument(
        "--schedule-next-day", action="store_true",
        help=(
            "Set publishAt to tomorrow's slot time so YouTube auto-publishes without manual steps. "
            "Requires auto_publish to also be set via --auto-publish."
        ),
    )
    args = parser.parse_args()

    init_db()

    if args.once:
        run_slot(
            args.slot,
            dry_run=args.dry_run,
            auto_publish=args.auto_publish,
            schedule_next_day=args.schedule_next_day,
        )
        return 0

    # Continuous scheduling mode
    sched = BlockingScheduler(timezone=_TZ)

    # Slot 1: 12:00 PM ET
    sched.add_job(
        run_slot,
        CronTrigger(hour=12, minute=0, timezone=_TZ),
        args=[0, args.dry_run, args.auto_publish, args.schedule_next_day],
        id="slot_noon",
        name="Slot 1 — 12:00 PM ET",
        replace_existing=True,
    )

    # Slot 2: 5:00 PM ET
    sched.add_job(
        run_slot,
        CronTrigger(hour=17, minute=0, timezone=_TZ),
        args=[1, args.dry_run, args.auto_publish, args.schedule_next_day],
        id="slot_5pm",
        name="Slot 2 — 5:00 PM ET",
        replace_existing=True,
    )

    # Slot 3: 9:00 PM ET
    sched.add_job(
        run_slot,
        CronTrigger(hour=21, minute=0, timezone=_TZ),
        args=[2, args.dry_run, args.auto_publish, args.schedule_next_day],
        id="slot_9pm",
        name="Slot 3 — 9:00 PM ET",
        replace_existing=True,
    )

    logger.info(
        "scheduler_started",
        slots=["12:00 PM", "5:00 PM", "9:00 PM"],
        timezone=_TZ,
        dry_run=args.dry_run,
        auto_publish=args.auto_publish,
        schedule_next_day=args.schedule_next_day,
    )
    print("Beyond The Pitch scheduler running. Press Ctrl+C to stop.")
    print("Kill switch: touch config/kill_switch.flag to halt jobs without stopping process.")

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler_stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
