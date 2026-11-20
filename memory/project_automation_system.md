---
name: project-automation-system
description: Phase F — fully automated 3-slot/day production system components and their status
metadata:
  type: project
---

Phase F automation system is built and all 504 tests pass (2026-11-20).

**Components:**
- `src/research/rss_provider.py` — RSS provider reading BBC/Sky/ESPN/Google News; dry-run verified live
- `src/editing/cc0_music.py` — CC0 music selection + embedding; needs MP3 files in `assets/music/`
- `src/video/thumbnail.py` — 1280×720 JPEG thumbnail generator; navy fallback when FFmpeg unavailable
- `src/production/auto_producer.py` — full storyboard→render→QC→upload pipeline with kill switch
- `scripts/run_scheduler.py` — APScheduler 3 daily slots at 12PM/5PM/9PM ET (America/New_York)
- `scripts/weekly_report.py` — DB + analytics summary with action items
- `config/com.beyondthepitch.scheduler.plist` — macOS launchd plist for auto-start

**Key dry-run proof:** `python scripts/run_scheduler.py --once --dry-run` successfully:
1. Fetched live BBC Sport RSS (5 topics ranked, top score 0.60)
2. Generated storyboard via MockScriptWriter
3. AutoProducer completed with stages: `['footage_found', 'dry_run']`

**Why:** User authorized 3 videos/day automatic publishing without per-video approval.

**How to apply:** When asked about automation readiness, blockers are: approved footage in catalog + YouTube credentials in .env. ClaudeScriptWriter needs `ANTHROPIC_API_KEY` but MockScriptWriter works as fallback.

[[feedback-watermark]]
[[feedback-disk-space]]
