# Beyond The Pitch — Project State
**Last updated:** 2026-11-20  
**Test suite:** 622 passing, 0 failing  
**Scheduler status:** LIVE — launchd service installed, 3 slots/day at 12PM/5PM/9PM Toronto. PID verified. Starts at login, restarts on crash.
**Demo Short (real footage):** `output/shorts/pixabay_soccer_short.mp4` — 1080×1920, h264, 25.0s, 15 MB, QC passed  
**First Short v2 (animated captions):** `output/shorts/martinez_world_cup_v2.mp4` — 1080×1920, h264, 28.0s, 39 MB, QC passed, render_id=6  
**Upload status:** 1 canonical upload: `uhUTx84DG4w`. Test uploads needing deletion: `aUtO8CYYq1w` (duplicate), `gRP9WqoL3QM`, `yPec0TMpfXQ` (both mock content — DELETE manually in YouTube Studio).
**Automation status:** Scheduler live with `--auto-publish --schedule-next-day`. Each video renders locally, passes QC, then uploads private with `publishAt` for the next day's slot. YouTube auto-publishes at the scheduled time — no manual step needed.
**CRITICAL BLOCKER:** `ANTHROPIC_API_KEY` not set → MockScriptWriter in use → mock-generated videos are BLOCKED from upload by safety gate. Add key to `.env` to enable real production.
**Full pipeline proof (2026-11-20):** `produce_one()` with pixabay footage → render 709 frames (27s) → effects 14s → QC passed → uploaded private → `youtube_id=A19ioZSVXd4`, render_id=8. All 12 stages completed.

---

## Project Goal

Build an automated YouTube Shorts business called **Beyond The Pitch** that publishes original football storytelling videos. The primary product is **automated clipping of rights-cleared, real long-form football videos**: transcribe → detect highlights → select clip → reframe 9:16 → animate captions → mix audio → upload privately for human review.

**Channel identity:** Navy `#0D1B2A` / Gold `#C9A84C`. Tagline: *"Football stories you've forgotten."*

---

## Completed Work

### Infrastructure (Phases 1–4)
- Python 3.13 project, venv at `venv/`, dependencies in `requirements.txt`
- SQLite database at `data/football_shorts.db` with tables for videos, storyboards, renders, ideas, analytics, API usage, topic history, footage assets, and permission requests
- YouTube Data API v3 client with quota tracking (soft 8,000 / hard 9,000 units/day), mock mode for offline testing
- Soccer relevance filter for trend discovery
- Trend report generated: `output/trend_report_2026-11-16.md` (173 soccer videos analysed)
- Concept scoring system in `src/planning/idea_ranker.py`

### Materazzi concept (Phase A — approved)
- Facts verified via Wikipedia: foul on Malouda (7'), header equaliser from Pirlo corner (19'), Zidane headbutt (108'), Italy won 5–3 on penalties, Materazzi scored Italy's second penalty
- Script written (73 words, ~26s): `output/phase_a_materazzi_script.md`
- Storyboard (9 shots): `output/phase_a_materazzi_storyboard.md`
- Assets manifest: `output/phase_a_materazzi_assets.md`
- Production requirements: `output/phase_a_materazzi_production_requirements.md`

### Photos downloaded and verified (Phase B)
All three in `output/phase_b_materazzi/assets/photos/`:
- `materazzi_cc_by_2.0.jpg` — 353×503px (small — will be soft at 1080p; acceptable for treatment shots)
- `zidane_wcf2006_cc_by_2.0.jpg` — 3456×2304px (high quality)
- `zidane_thuram_final_cc_by_2.0.jpg` — 1273×1184px (adequate quality)
- All licensed CC BY 2.0. Attribution required in video description. Photographers: David Ruddell (Zidane shots), Oscar Federico Bodini (Materazzi).

### Static storyboard frames (Phase B — REJECTED, kept for reference)
Nine PNG frames at 1080×1920 in `output/phase_b_materazzi/assets/graphics/`  
Contact sheet: `output/phase_b_materazzi/storyboard_contact_sheet.png`  
**These were rejected** — they look like a slideshow. Files are kept as reference only.

### Footage catalog system (Phase C — complete)
New module `src/footage/` with 40 tests. Persistent SQLite-backed three-tier catalog:
- **Tier 1 CREATOR_AUTHORIZED**: explicit written permission from YouTube creators. Never auto-approved.
- **Tier 2 STOCK_LICENSED**: Pixabay, Pexels, Coverr. License auto-inferred from domain; status set to PENDING_REVIEW until visual inspection confirms no logos/identifiable faces.
- **Tier 3 AI_GENERATED**: Kling, Runway on paid commercial plans. PENDING_REVIEW until visually confirmed.
- **Hard gate**: `FootageGate.check_all()` raises `FootageGateError` unless `approval_status == APPROVED AND commercial_use AND monetization_allowed`. YouTube public availability, watermarks, and credit **never** satisfy this gate.
- CLI: `python scripts/footage_catalog.py [check|import stock|import ai|request-permission|confirm-permission|approve|reject|list]`

### Clipping pipeline (Phase D — complete)
New module `src/clipping/` — the primary production system:
- **Transcriber** (`transcriber.py`): faster-whisper with word-level timestamps. Falls back to `MockTranscriber` with BLOCKER warning if faster-whisper not installed.
- **Highlight detector** (`highlight_detector.py`): keyword scoring across 50s sliding windows; density bonuses; hook-quality bonus for excited language in first 5s.
- **Clip selector** (`clip_selector.py`): wraps detector + motion-guided crop analysis (column-wise brightness variance across sampled frames).
- **Reframer** (`reframer.py`): `scale=-2:1920,crop=1080:1920:CROP_X:0` via FFmpeg — always outputs 1080×1920.
- **Caption renderer** (`caption_renderer.py`): ASS subtitle format, 3 styles (BTP_Caption 86px white, BTP_Hook 110px gold, BTP_Brand 38px gold), burned via FFmpeg `ass=` filter.
- **Audio mixer** (`audio_mixer.py`): loudnorm `-16 LUFS, -1.5 TP, 11 LRA`; optional music bed at −20 dB.
- **Editor** (`editor.py`): full pipeline — gate check → reframe → captions → normalise → optional music → DB record.

### Publishing pipeline (Phase D — complete)
- **OAuth** (`src/youtube/oauth.py`): token cached at `data/youtube_token.json` (chmod 600), auto-refreshes.
- **Uploader** (`src/youtube/uploader.py`): resumable upload, 3 retries with backoff, daily cap (default 3), duplicate detection, records `youtube_id` in DB.
- **Analytics** (`src/analytics/collector.py`): YouTube Data API + Analytics API v2, `get_top_performing_topics()` for feedback loop.
- **Metadata generator** (`src/planning/metadata_generator.py`): title/description/tags from storyboard or clip; attribution block; AI disclosure flag; truncation to YouTube limits.

### Photo compositor (Phase D — fallback only)
`src/video/photo_compositor.py` — Ken Burns-style compositor for CC-BY photos when no real footage is available. Output is intentionally secondary; real video clipping takes priority.

### Demo Short — photo fallback (2026-11-19 — deleted)
Built via: `python scripts/pipeline.py produce materazzi --tts macos`  
**Deleted** to free disk space — macOS TTS (Samantha) not licensed for monetized upload. Static frames in `output/phase_b_materazzi/` preserved as reference only.

### Editing style library (Phase E — complete)
New module `src/editing/` with 108 tests. Five professional caption presets + auto-selector + beat detector + sound library:

**Caption presets** (`src/editing/caption_presets.py`):
| Preset | Font | Size | Animation | Use case |
|--------|------|------|-----------|----------|
| `CINEMATIC_MINIMAL` | Montserrat ExtraBold | 52px | Slow fade (12 frames in) | Atmospheric B-roll, slow moments |
| `BOLD_IMPACT` | Bebas Neue | 116px | Pop scale 1.25→1.0 (5 frames) | Stats, goals, shock facts, hooks |
| `BEAT_SYNC_FLASH` | Bebas Neue | 96px | Instant on/off | Phonk/drill soundtracks |
| `KINETIC_SLIDE` | Montserrat ExtraBold | 80px | Slide up 50px (8 frames) | Factual storytelling, default |
| `DRAMATIC_REVEAL` | Montserrat ExtraBold | 90px | Word-by-word fade, final word gold | Climax moments, World Cup hooks |

**Auto-selector** (`src/editing/style_selector.py`): `select_caption_preset(story_type, bpm, beats, has_speech, mood, override)` — 7 decision rules, all overridable.

**Beat detector** (`src/editing/beat_detector.py`): RMS energy in 50ms windows, onset detection, BPM estimation. `snap_to_beat()` aligns caption start times to music.

**Sound library** (`src/editing/sound_library.py`): 12 curated tracks (3 FREE_EMBED CC0, 9 SHORTS_ONLY). Recommendation engine by story type, BPM, embed policy.

**Animated renderer** (`src/editing/renderer.py`): PIL frame-pipe (FFmpeg extract → Python animate → FFmpeg encode). Watermark "BEYOND THE PITCH" in gold at y=60px, constant. All 5 animation types implemented. Safe-zone enforced: top 190px, bottom 380px, sides 54px.

**Production scripts:**
- `scripts/produce_first_short.py` — v1 (ASS burn, Pexels footage)
- `scripts/produce_first_short_v2.py` — v2 (animated PIL, DRAMATIC_REVEAL, beat-snapped)

### Demo Short — real footage clipping (2026-11-20 — QC passed)
`output/shorts/pixabay_soccer_short.mp4` — 1080×1920, h264, 25.0s, 15 MB.  
Source: Pixabay CC0 stadium crowd atmosphere (caace90c). No speech detected → no-speech fallback used.  
Pipeline: faster-whisper → no-speech fallback window → motion crop anchor (0.509) → reframe → PIL captions → LUFS normalise.  
**Caption note:** FFmpeg 9.0.2 Homebrew bottle excludes libass; captions burn via PIL frame-pipe fallback instead.

### Viral Moment Scoring (Phase 2 — complete)
New module `src/content/moment_scorer.py` with 21 tests. Scores football moment candidates on 5 dimensions:

| Dimension | Weight | Notes |
|-----------|--------|-------|
| `visual_wow_factor` | 35% | Skill > goal > save > nostalgia |
| `rewatch_potential` | 25% | Skill, nostalgia rank highest |
| `player_recognition` | 15% | Messi/Ronaldo = 1.0; Yamal = 0.88; unknown = 0.40 |
| `music_compatibility` | 15% | Skill, goal, celebration rank highest |
| `current_relevance` | 10% | Overridable per topic |

`LAUNCH_MOMENT_IDEAS` — 8 scored candidate moments. All professional match footage marked `REQUIRES_LICENSE` (Content ID registered by FIFA/UEFA/leagues). `CC0_TEXT_OVERLAY_READY` used for text-overlay storytelling videos.

**Footage rights reality:** No clip of Messi, Neymar, Yamal, or Ronaldo in a real match can be licensed by an individual creator. Options: Kling/Runway AI recreation, creator permission requests, or text-overlay over atmosphere B-roll (current approach).

### Video Effects Engine (Phase 3 — complete)
New module `src/editing/effects.py` with 22 tests. Single FFmpeg pass for professional grading:

| Preset | Zoom | Grade | Vignette | Use case |
|--------|------|-------|----------|----------|
| `FOOTBALL_EDIT_CINEMATIC` | 1.04× | cinematic curves | 0.4 | Atmospheric storytelling |
| `FOOTBALL_EDIT_DRAMATIC` | 1.06× | dramatic S-curve | 0.6 | World Cup, finals, goals |
| `FOOTBALL_EDIT_VIBRANT` | 1.05× | vibrant warm | 0.3 | Skill compilations |
| `FOOTBALL_EDIT_NONE` | — | — | — | Copy pass only |

`select_effects_config(story_type, mood)` auto-selects preset. Zoom uses `scale+crop` (fast, seconds per clip). Color grades use FFmpeg `curves` with S-curve + warm shadow boost.

**Effects fix (2026-11-20):** Replaced `zoompan` filter with `scale=W*factor:H*factor,crop=W:H`. Zoompan took 27+ minutes per clip; scale+crop takes ~14 seconds. Output identical visually for the subtle 1.04–1.06× zoom used here. CRF raised to 28 for effects intermediates to reduce file size (~80 MB vs ~700 MB).

### Disk Monitor (Phase 7 — complete)
New module `src/core/disk_monitor.py` with 22 tests. `MINIMUM_FREE_MB = 205`. AutoProducer checks before every render. `prune_old_renders(keep_last=5)` cleans output dir automatically. `disk_status_report()` shows one-line status in weekly report.

### Growth Intelligence (Phase 8 — complete)
New module `src/analytics/growth_intelligence.py` with 17 tests. Per-video attribute tracking (player, moment type, music style, caption preset, posting slot) in SQLite `video_attributes` table. `generate_insights(days=30)` returns performance patterns when ≥ 3 analytics rows exist. `generate_weekly_report()` powers `scripts/weekly_report.py`.

### Full Automation System (Phase F — complete)

**RSS Research Provider** (`src/research/rss_provider.py`):
- Reads BBC Sport, Sky Sports, ESPN FC, Google News RSS (no API keys)
- Filters out transfer rumours, betting content, unverified claims
- Relevance scoring by content type keywords
- Falls back gracefully if any feed is unavailable

**CC0 Music Embedder** (`src/editing/cc0_music.py`):
- 4 curated CC0 track slots (epic cinematic, inspiring sport, stadium, tension)
- Selects by story_type + BPM proximity
- Embeds at −20 dBFS under existing audio
- MP3 files must be placed in `assets/music/` (Pixabay Music, CC0)

**Thumbnail Generator** (`src/video/thumbnail.py`):
- Samples 8 frames (10%–95% of duration), picks highest visual energy (pixel std-dev)
- Falls back to navy gradient if FFmpeg fails or video is missing
- 1280×720 JPEG with navy gradient bar + white title + gold channel name
- **Limitation:** YouTube Shorts custom thumbnails don't reliably show in the Shorts feed. Thumbnail is generated for search/browse outside the Shorts shelf.

**Renderer fix (`src/editing/renderer.py`) — 2026-11-20:**
- Always outputs 1080×1920 regardless of source resolution by scaling in the FFmpeg extract command (`scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920`)
- Probes audio stream; only maps `-map 1:a` when source has audio (video-only footage no longer crashes)
- Checks encoder return code after `writer.wait()` and raises if non-zero
- Both fixes verified with pixabay footage (1080×1920 → 20MB output) and confirmed through tests

**AutoProducer** (`src/production/auto_producer.py`):
- Connects: storyboard → footage → beat detection → preset selection → PIL render → LUFS normalise → effects → CC0 music → thumbnail → factual source verification → QC → DB record → YouTube upload
- Kill switch checked at start of every job
- Automatic disk management: `_work/` cleaned up after each render; oldest renders pruned to keep last 10
- `dry_run=True` mode for testing without render/upload
- `publish_at="2026-11-21T17:00:00.000Z"` wires YouTube `publishAt` for auto-publication at a future time
- `_find_approved_footage()` now returns absolute paths (relative paths from DB are resolved against project root)
- `_verify_scene_sources()` gate: raises `ValueError` if any scene with >10-word narration lacks valid `source_indices` — prevents fabricated facts

**Scheduler** (`scripts/run_scheduler.py`):
- APScheduler 3.11.3, timezone-aware (`America/Toronto`)
- Three daily slots: 12:00 PM, 5:00 PM, 9:00 PM ET
- `--once --slot N` for single immediate run
- `--dry-run` for pipeline testing without rendering
- `--auto-publish` to publish publicly after upload (requires explicit opt-in)
- `--schedule-next-day` sets `publishAt` to tomorrow's slot time (uses `_next_publish_time(slot_num)`)

**launchd plist** (`config/com.beyondthepitch.scheduler.plist`):
- Starts at login, keeps alive on crash, throttles restarts (60s)
- Logs to `logs/scheduler_stdout.log` / `logs/scheduler_stderr.log`
- Install: `cp config/com.beyondthepitch.scheduler.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist`

**Weekly Reporter** (`scripts/weekly_report.py`):
- Queries DB for: videos produced/uploaded, QC pass rate, top videos by views, API usage
- Prints action items (gap to target, missing credentials, kill switch)
- `--save` writes to `output/reports/weekly_report_YYYY-MM-DD.txt`

---

## Pipeline Commands

```bash
source venv/bin/activate

# ── Automation (Phase F) ──────────────────────────────────────────────────────

# Run one production slot immediately (dry-run = no render/upload)
python scripts/run_scheduler.py --once --dry-run

# Run one real slot (needs approved footage + YouTube credentials)
python scripts/run_scheduler.py --once --slot 0

# Start the continuous 3-slot/day scheduler (12PM / 5PM / 9PM ET — America/Toronto)
python scripts/run_scheduler.py

# Start scheduler with auto-publish (all safety gates must pass)
python scripts/run_scheduler.py --auto-publish

# Schedule each video to auto-publish at tomorrow's slot time (no manual Studio step)
python scripts/run_scheduler.py --auto-publish --schedule-next-day

# Kill switch (halts all jobs without stopping process)
touch config/kill_switch.flag     # arm
rm config/kill_switch.flag        # disarm

# Weekly performance report
python scripts/weekly_report.py
python scripts/weekly_report.py --save   # also save to output/reports/

# Install as a background service (auto-starts at login, stays alive)
cp config/com.beyondthepitch.scheduler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist

# ── Per-video pipeline ────────────────────────────────────────────────────────

# Clip a specific footage asset (must be APPROVED in catalog)
python scripts/pipeline.py clip --source-id UUID

# Full automated pipeline: discover → catalog scan → transcribe → clip → edit
python scripts/pipeline.py auto [--limit 5] [--dry-run]

# Photo fallback demo (Materazzi CC-BY photos)
python scripts/pipeline.py produce materazzi [--tts macos|openai|mock]

# Upload a completed render (needs YouTube credentials)
python scripts/pipeline.py upload --render-id ID

# Collect analytics for all uploaded videos
python scripts/pipeline.py analytics

# DB counts + credential status
python scripts/pipeline.py status
```

---

## Current Decisions (confirmed, do not revisit without reason)

| Decision | Detail |
|----------|--------|
| **Primary product** | Automated clipping of rights-cleared real footage, NOT photo slideshows |
| **Photo compositor** | Kept as optional fallback only; not the main output path |
| **First Short** | Martínez 2026 WC Final — 10 beats, 28s, DRAMATIC_REVEAL preset, Pexels footage, Pixabay CC0 audio |
| **No match footage** | FIFA/UEFA/league footage is rights-managed and Content ID registered. Story told through narration, graphics, and atmosphere B-roll. |
| **Caption system** | PIL frame-pipe (renderer.py) with 5 presets. DRAMATIC_REVEAL is the default for storytelling/climax content. |
| **Beat sync** | Crowd-noise audio → 120 BPM fallback grid. True beat sync requires adding real music before the render, which requires embedding copyrighted audio — not permitted. Add music via Shorts picker at upload time. |
| **Music policy** | CC0 tracks embedded at −20 dBFS via `cc0_music.py` for licensed background audio. Add trending music via YouTube Shorts audio picker post-upload. Never embed copyrighted tracks. |
| **AI disclosure** | Not required for text-overlay storytelling videos. Required if Kling/Runway AI footage is used — set `contains_ai_generated=True` in `VideoMetadata`. |
| **Auto-publish gate** | Scheduler uploads privately by default. Pass `--auto-publish` to publish publicly; all QC + safety gates must pass. No per-video approval needed when this flag is set. |
| **3 videos/day realism** | Realistic only with sufficient approved footage in catalog. Scheduler skips slots when no footage is available rather than producing low-quality content. |
| **Mac sleep limitation** | Scheduler requires Mac to stay awake. launchd restarts the process on crash but cannot wake from sleep. Alternative: migrate to Hetzner CX11 VPS (€3.80/month) running Ubuntu + same Python stack for 24/7 operation. |
| **Viral moment scoring** | Use `MomentScorer` to rank `LAUNCH_MOMENT_IDEAS` before each production slot. Score ≥ 0.70 to proceed; < 0.50 — skip that idea. |
| **Effects per content type** | `select_effects_config(story_type, mood)` wires automatically: skill/goal → VIBRANT, storytelling/WC → DRAMATIC, motivation → CINEMATIC. |

---

## 90-Day Growth Plan

| Phase | Days | Goal | Key action |
|-------|------|------|-----------|
| Experiment | 1–30 | 90 Shorts published | Test all moment types: skill, goal, nostalgia, celebration. Try different players, hooks, music. |
| Identify winners | 31–60 | 180 Shorts published | Double down on top-3 formats by retention + views. Cut formats with < 20% retention. |
| Scale | 61–90 | 270 Shorts published | Publish only proven formats. Apply for YPP when eligible. |

**YPP thresholds (Canada):**
- Fan-funding: 500 subs + 3,000 watch hours
- Advertising: 1,000 subs + 4,000 watch hours  
- Shorts ad revenue: 1,000 subs + 10M Shorts views (90 days)

Growth intelligence tracking per-video: player, moment type, music style, caption preset, posting slot → `src/analytics/growth_intelligence.py`. Weekly report shows patterns after ≥ 3 analytics rows.

---

## Blockers

| # | Blocker | Affects | Resolution |
|---|---------|---------|-----------|
| 1 | ~~`faster-whisper` not installed~~ | ~~Real transcription~~ | **RESOLVED 2026-11-20** — installed 1.2.1 |
| 2 | ~~OAuth `_load_token()` bug~~ | ~~Upload~~ | **RESOLVED 2026-11-20** — fixed to use `Credentials.from_authorized_user_info(json.loads(text))`. Channel "Beyond Pitch" verified accessible. |
| 9 | ~~Uploader FK bug caused duplicate uploads~~ | ~~Duplicate prevention~~ | **RESOLVED 2026-11-20** — DB write in separate try/except; `log_production` passes `None`; path normalization added; file hash dedup added. |
| 10 | ~~Renderer failed on video-only footage (no audio stream)~~ | ~~Production pipeline~~ | **RESOLVED 2026-11-20** — `render_video_with_captions()` now probes audio streams and only maps `-map 1:a` when audio exists. Encoder return code checked. |
| 11 | ~~Effects `zoompan` took 27+ minutes per clip~~ | ~~Production speed~~ | **RESOLVED 2026-11-20** — Replaced `zoompan` with `scale+crop`. Effects now take ~14 seconds. CRF=28 for intermediates (down from CRF=23 → ~80 MB vs ~700 MB). |
| 12 | ~~OAuth `get_credentials()` hung on token refresh failure~~ | ~~Automated pipeline~~ | **RESOLVED 2026-11-20** — Raises `EnvironmentError` immediately on refresh failure (network unavailable / revoked). AutoProducer catches it as `upload_skipped_no_credentials`. |
| 3 | No approved footage with audio | **Quality** | Current footage (pexels_match_31511131.mp4) has no audio. Beat detection falls back to 100 BPM. LUFS normalise produces silent video. Import footage with audio for a richer result. Existing pipeline still produces valid video. |
| 4 | Real licensed music (phonk/Brazilian funk) | **Sound design** | All 4 music slots are synthetic placeholder beats. Pipeline works. Replace with CC0 tracks from Pixabay Music (cinematic/sport free) or Artlist ($199/yr) / Epidemic Sound ($15/month) for phonk/montagem. |
| 5 | `ANTHROPIC_API_KEY` not set | **Real uploads blocked** | Mock-generated videos are now HARD BLOCKED from upload by safety gate. Add key to `.env`. After adding, reset `DAILY_UPLOAD_CAP=3` in `.env` (currently 6 to allow today's remaining slots after testing). |
| 6 | `OPENAI_API_KEY` not set | OpenAI TTS fallback | Add to `.env` if TTS narration is needed |
| 7 | No Kling account | AI-generated cinematic clips | Create free account at klingai.com; test with daily Basic credits |
| 8 | FFmpeg 9.0.2 Homebrew bottle excludes libass | ASS caption burn | Moot — PIL frame-pipe renderer is now primary caption system |

---

## Outstanding Issues

| # | Issue | Blocker? | Resolution path |
|---|-------|----------|----------------|
| 1 | Reference Short analysis limited | No | YouTube loads content dynamically; only titles visible. G__XkDjNpHM = Pedri skill clip. VwvZOcOel3E = "TOP 5 Shots" compilation. Both use emoji hooks and hashtag-heavy titles — standard Shorts format. |
| 2 | Placeholder music only | No | 4 synthetic beats in `assets/music/`. Pipeline works; replace with real CC0 tracks from Pixabay Music. See `RECOMMENDED_TRACKS` in `src/editing/music_library.py`. |
| 3 | Storyboard concepts hardcoded in `trend_report.py` | No | Low priority |
| 4 | Pexels footage (pexels_match_31511131.mp4) has no audio | No | Beat detection falls back to 100 BPM; LUFS produces silent video. Use pixabay_soccer_8502.mp4 for all tests (has audio). |

---

## Exact Next Steps

### Step 1 — Delete test uploads from YouTube Studio

Go to YouTube Studio → Content → delete these 3 videos:
- `aUtO8CYYq1w` — duplicate of the canonical upload
- `gRP9WqoL3QM` — mock content from testing
- `yPec0TMpfXQ` — mock content from testing

Keep `uhUTx84DG4w` ("He made 11 saves…").

### Step 2 — Add ANTHROPIC_API_KEY (REQUIRED for real uploads)

The scheduler is running but the mock-content gate blocks all uploads until a real script writer is active. Add to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

After adding, also reset the daily cap (was raised to 6 for testing):
```
DAILY_UPLOAD_CAP=3
```

Restart the scheduler to pick up the new env:
```bash
launchctl unload ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
```

### Step 3 — Replace placeholder music (quality improvement)

Download 1-4 MP3 tracks from Pixabay Music (free, CC0) and place them in `assets/music/` matching the filenames in `src/editing/music_library.py`:

- `epic_cinematic_cc0.mp3` — search "epic sport cinematic"
- `inspiring_sport_cc0.mp3` — search "inspiring sport upbeat"
- `stadium_atmosphere_cc0.mp3` — search "stadium crowd sport" (or Artlist for phonk)
- `tension_buildup_cc0.mp3` — search "tension buildup cinematic"

After downloading, verify: `python -c "from src.editing.music_library import verify_library; print(verify_library())"` — look for `"ok"` entries, not `"placeholder"`.

### Step 4 — Import more approved footage with audio

The pipeline is fully verified. The bottleneck is approved footage. Import more Pixabay/Pexels clips:

```bash
python scripts/footage_catalog.py import stock \
  --url "https://pixabay.com/videos/CLIP_URL" \
  --local-path output/footage/my_clip.mp4
python scripts/footage_catalog.py approve --id UUID
```

Use clips with crowd audio for better beat detection and richer LUFS normalisation.

### Step 5 — The scheduler is already live

The launchd service is installed and running. To verify: `launchctl list | grep beyondthepitch`

To restart after changing `.env`:
```bash
launchctl unload ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
```

To stop entirely:
```bash
launchctl unload ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
```

Logs: `tail -f logs/scheduler_stdout.log`

---

## Automated 3-Slots/Day Workflow

**To activate the fully automated system:**

```bash
# 1. Add YouTube credentials to .env (one-time setup)
#    YOUTUBE_CLIENT_ID=...        ✓ already set
#    YOUTUBE_CLIENT_SECRET=...    ✓ already set
#    ANTHROPIC_API_KEY=...        ← REQUIRED — without this, uploads are blocked

# 2. Import and approve stock footage
python scripts/footage_catalog.py import stock \
  --url "https://pixabay.com/videos/CLIP_URL" \
  --local-path output/footage/my_clip.mp4
python scripts/footage_catalog.py approve --id UUID

# 3. Download CC0 music tracks into assets/music/
#    See filenames in src/editing/cc0_music.py _CC0_TRACKS
#    Source: Pixabay Music (CC0 license, free to download)

# 4. Test one slot dry-run
python scripts/run_scheduler.py --once --dry-run

# 5. Test one real slot (private upload)
python scripts/run_scheduler.py --once --slot 0

# 6. Launch continuous scheduler
python scripts/run_scheduler.py --auto-publish

# 7. Install as a background service
cp config/com.beyondthepitch.scheduler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.beyondthepitch.scheduler.plist
```

**Weekly review:**
```bash
python scripts/weekly_report.py --save
```

**Safety controls always active:**
- Kill switch: `touch config/kill_switch.flag` halts all jobs immediately
- QC must pass before upload
- `--auto-publish` must be explicitly passed to publish publicly
- No broadcast/licensed footage ever enters the pipeline

---

## How to Resume

```bash
cd ~/football-shorts
source venv/bin/activate

# Confirm tests still pass
python -m pytest -q --tb=short
# Expected: 622 passed

# See footage catalog contents
python scripts/footage_catalog.py list

# Check pipeline status (DB counts + credentials)
python scripts/pipeline.py status

# Check any URL's license before importing
python scripts/footage_catalog.py check --url "URL_HERE"

# Run the scheduler dry-run smoke test
python scripts/run_scheduler.py --once --dry-run
```

---

## Security Constraints (permanent)

- API keys live in `.env` only (chmod 600). Never hardcoded, never logged, never committed.
- Never download or reupload competitors' videos, broadcast match clips, or copyrighted audio.
- Only original, authorized, or commercially licensed assets enter the production pipeline.
- Do not publish or upload anything without explicit instruction.
- Do not purchase services without explicit instruction.
- Do not use macOS Samantha or any unlicensed AI voice for monetized content.

---

## File Map (key files only)

```
football-shorts/
├── CLAUDE.md                              ← this file
├── config/settings.yaml                   ← all runtime settings
├── data/football_shorts.db                ← SQLite (videos, storyboards, footage_assets, etc.)
├── output/
│   ├── materazzi_youtube_short.mp4        ← demo Short (QC passed, macOS TTS — not for upload)
│   ├── phase_a_materazzi_script.md        ← verified 73-word script
│   ├── phase_a_materazzi_storyboard.md    ← 9-shot plan
│   ├── phase_a_materazzi_assets.md        ← asset manifest with license details
│   ├── phase_b_materazzi/
│   │   ├── assets/photos/                 ← 3 CC BY 2.0 photos (keep)
│   │   ├── assets/graphics/               ← 9 static PNG frames (rejected, kept for ref)
│   │   └── storyboard_contact_sheet.png
│   ├── phase_c_test_plan.md               ← Kling/Runway comparison + test prompt
│   ├── phase_c_footage_catalog_setup.md   ← catalog CLI usage guide
│   └── shorts/                            ← pipeline output dir (created on first run)
├── config/
│   ├── settings.yaml                      ← all runtime settings
│   └── com.beyondthepitch.scheduler.plist ← macOS launchd service (auto-start at login)
├── logs/                                  ← scheduler stdout/stderr logs
├── assets/
│   ├── fonts/                             ← Montserrat-ExtraBold.ttf, BebasNeue-Regular.ttf
│   └── music/                             ← CC0 MP3 tracks (download from Pixabay Music)
├── scripts/
│   ├── pipeline.py                        ← main orchestrator (clip/auto/produce/upload/analytics/status)
│   ├── run_scheduler.py                   ← 3-slot daily scheduler (Phase F)
│   ├── weekly_report.py                   ← weekly performance report (Phase F)
│   ├── footage_catalog.py                 ← CLI for the footage catalog
│   ├── upload_first_short.py              ← one-off upload for martinez_world_cup_v2.mp4
│   ├── produce_first_short.py             ← v1 Short (ASS burn, Pexels footage, 28s)
│   ├── produce_first_short_v2.py          ← v2 Short (animated PIL, DRAMATIC_REVEAL)
│   ├── generate_materazzi_frames.py       ← generated the Phase B static PNGs
│   └── trend_report.py                    ← trend discovery and concept scoring
└── src/
    ├── production/                        ← Phase F: auto-producer
    │   └── auto_producer.py               ← storyboard → render → QC → upload pipeline
    ├── clipping/                          ← PRIMARY: video clipping pipeline
    │   ├── models.py                      ← WordTimestamp, Transcript, ClipSpec, ScoredWindow
    │   ├── transcriber.py                 ← FasterWhisperTranscriber + MockTranscriber
    │   ├── highlight_detector.py          ← keyword scoring, sliding windows
    │   ├── clip_selector.py               ← wraps detector + motion crop analysis
    │   ├── reframer.py                    ← FFmpeg 9:16 reframe
    │   ├── caption_renderer.py            ← ASS captions + burn-in
    │   ├── audio_mixer.py                 ← LUFS normalisation + music bed
    │   └── editor.py                      ← full pipeline + gate check + DB record
    ├── research/                          ← Phase 2 + F: story research
    │   ├── models.py                      ← Pydantic v2 models: Storyboard, StoryboardScene, etc.
    │   ├── providers.py                   ← ResearchProvider ABC + Mock + Wikipedia
    │   ├── rss_provider.py                ← RSS provider: BBC/Sky/ESPN/Google News (Phase F)
    │   ├── scorer.py                      ← TopicScorer (5 dimensions)
    │   ├── safety.py                      ← content safety filter
    │   ├── script_writer.py               ← MockScriptWriter + ClaudeScriptWriter
    │   └── pipeline.py                    ← StoryboardPipeline orchestrator
    ├── youtube/
    │   ├── oauth.py                       ← Google OAuth 2.0, token at data/youtube_token.json
    │   └── uploader.py                    ← resumable upload, duplicate detection (hash+path), publishAt scheduling, quota
    ├── content/                           ← viral moment scoring (Phase 2)
    │   └── moment_scorer.py               ← MomentScorer, 5-dimension weights, LAUNCH_MOMENT_IDEAS
    ├── analytics/
    │   ├── collector.py                   ← YouTube Data + Analytics API, top topics query
    │   └── growth_intelligence.py         ← per-video attribute tracking, weekly report (Phase 8)
    ├── planning/
    │   ├── idea_ranker.py                 ← concept scoring
    │   └── metadata_generator.py          ← title/description/tags + attribution block
    ├── editing/                           ← caption presets, beat detector, sound library, renderer
    │   ├── caption_presets.py             ← 5 presets + AnimationType + Color
    │   ├── beat_detector.py               ← RMS onset detection, BPM estimate, snap_to_beat
    │   ├── sound_library.py               ← 12 curated tracks + recommend_sounds()
    │   ├── style_selector.py              ← auto-select preset + snap beats to music
    │   ├── renderer.py                    ← animated PIL frame-pipe + watermark; audio-stream probe fix
    │   ├── effects.py                     ← FFmpeg zoom/color-grade/vignette presets (Phase 3)
    │   ├── cc0_music.py                   ← CC0 music selection + embedding (Phase F)
    │   └── music_library.py               ← licensing provenance store: LicenseType, EmbedPolicy, MusicTrack, verify_library()
    ├── video/
    │   ├── photo_compositor.py            ← Ken Burns fallback (CC-BY photos)
    │   ├── thumbnail.py                   ← 1280×720 thumbnail generator (Phase F)
    │   └── tts.py                         ← OpenAI TTS + macOS TTS + mock fallback chain
    ├── footage/                           ← 3-tier catalog + hard gate
    │   ├── models.py
    │   ├── catalog.py
    │   ├── sources.py
    │   ├── license_checker.py
    │   └── gate.py
    ├── core/
    │   ├── database.py                    ← schema (all tables)
    │   └── disk_monitor.py                ← free-space check, render estimates, prune (Phase 7)
    └── trends/youtube_client.py           ← YouTube Data API v3 with quota tracking
```

## Optional Dependencies

Install these before running the real pipeline (not needed for tests):

```bash
pip install faster-whisper          # real transcription (CPU Whisper)
pip install yt-dlp                  # download stock footage with metadata
pip install openai                  # OpenAI TTS (needs OPENAI_API_KEY in .env)
```
