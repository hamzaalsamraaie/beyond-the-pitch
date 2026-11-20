# Beyond The Pitch — Football Shorts Automation

Automated pipeline to produce original 1080×1920 football YouTube Shorts.
Content is research-backed, source-cited, and safety-screened before it reaches a human reviewer.

**Upload is always private by default. No automatic publishing.**

---

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.12+ (tested on 3.13)
- FFmpeg (`brew install ffmpeg`)
- Homebrew

---

## Setup

```bash
# Clone or unzip the project
cd ~/football-shorts

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the environment template
cp .env.example .env
# Then edit .env and fill in your API keys
```

---

## Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Phase 2+ | Claude API for script generation |
| `YOUTUBE_CLIENT_ID` | Phase 3 | YouTube Data API OAuth |
| `YOUTUBE_CLIENT_SECRET` | Phase 3 | YouTube Data API OAuth |
| `DAILY_UPLOAD_CAP` | Optional | Max uploads per day (default: 3) |
| `MONTHLY_CLAUDE_SPEND_LIMIT_USD` | Optional | Spend guard (default: $20) |

Credentials are read from `.env` by `python-dotenv`. Never commit `.env` to git.

---

## Project structure

```
football-shorts/
├── config/
│   ├── settings.yaml          — scoring weights, limits, Claude model, logging
│   └── kill_switch.flag       — CREATE this file to halt all automation instantly
├── src/
│   ├── core/
│   │   ├── config.py          — read settings.yaml
│   │   ├── database.py        — SQLite schema + helpers
│   │   ├── kill_switch.py     — arm/disarm automation halt
│   │   └── logger.py          — structured logging → file + stdout
│   ├── research/
│   │   ├── models.py          — Pydantic models: ResearchItem, Storyboard, etc.
│   │   ├── safety.py          — content safety checker (runs before + after generation)
│   │   ├── scorer.py          — transparent 5-dimension topic scorer
│   │   ├── providers.py       — MockProvider + WikipediaProvider
│   │   ├── script_writer.py   — MockScriptWriter + ClaudeScriptWriter
│   │   └── pipeline.py        — StoryboardPipeline orchestrator
│   └── video/
│       └── test_generator.py  — Phase 1 test video generator (Pillow + FFmpeg)
├── tests/                     — 73 tests, all passing
├── data/football_shorts.db    — SQLite (gitignored)
├── output/                    — rendered MP4s (gitignored)
└── logs/                      — daily log files (gitignored)
```

---

## Running the tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

All 73 tests run without any API keys or network access.

---

## Phase 1 — Test video generator

Generates a self-contained 1080×1920 Short using only Pillow and FFmpeg.

```bash
source venv/bin/activate
python -m src.video.test_generator
# Output: output/football_stories_test_short.mp4
```

---

## Phase 2 — Research and storytelling engine (mock demo)

```bash
source venv/bin/activate
python demo_phase2.py
```

Runs the full pipeline with mock data. No API calls. Prints a JSON storyboard to stdout.

To use the real Claude API, set `ANTHROPIC_API_KEY` in `.env` and run:

```bash
python demo_phase2.py --use-claude
```

The pipeline uses `claude-haiku-4-5-20251001` (configurable in `config/settings.yaml`) with a
default cap of 10 requests per day. The cap is tracked in the SQLite `api_usage` table.

---

## Kill switch

To stop all automation immediately:

```bash
touch config/kill_switch.flag
```

To re-enable:

```bash
rm config/kill_switch.flag
```

Every pipeline action checks this flag before running.

---

## Content safety

The safety checker rejects content that contains:

- Gambling, betting, or wagering references
- Explicit material
- Transfer rumour language ("set to sign", "close to signing")
- Claims from unnamed sources ("sources claim", "insider says")
- Visual requirements that assert specific footage is licensed

It runs **twice**: once on research items (before generation) and once on the generated storyboard.

---

## Source citation requirements

Every research item must include a verifiable `url` and `title`.
`ResearchItem` model validation rejects facts that contain:

- "allegedly", "reportedly", "sources claim"
- "set to join", "close to signing", "transfer fee of"

No footage is assumed to be licensed because it is publicly accessible.
`visual_requirement` fields must describe the type of visual needed, not name specific clips.

---

## Scoring dimensions

Topics are ranked using five transparent, configurable dimensions (weights in `config/settings.yaml`):

| Dimension | Default weight | What it measures |
|---|---|---|
| `freshness` | 0.20 | How recent the source material is |
| `audience_interest` | 0.25 | Viewer interest (keyword signals) |
| `emotional_impact` | 0.25 | Emotional resonance of the story |
| `originality` | 0.20 | How novel vs topics already covered |
| `visual_feasibility` | 0.10 | Can we illustrate without specific licensed footage |

Topics scoring below `research.min_score_threshold` (default 0.40) are skipped.

---

## Phase roadmap

| Phase | Status | Description |
|---|---|---|
| 1 | Complete | Environment, project structure, test video generator |
| 2 | Complete | Research provider, topic scorer, safety checker, Claude script writer |
| 3 | Planned | Licensed asset integration (Pexels, Google Fonts, royalty-free music) |
| 4 | Planned | YouTube Data API: private upload, metadata generation |
| 5 | Planned | YouTube Analytics: performance tracking, format comparison |
| 6 | Planned | macOS launchd scheduler, daily 3-Short pipeline |
