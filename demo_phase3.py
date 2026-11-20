"""
demo_phase3.py — Phase 3 demonstration: Storyboard → 1080×1920 MP4

Produces one complete football Short using:
  - MockTTSProvider (silent audio, offline, zero cost)
  - Original generated graphics (no licensed footage)
  - MockScriptWriter storyboard for Ronaldo R9's 1998 World Cup story

Run:
    source venv/bin/activate
    python demo_phase3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import src.core.database as db_module

db_module.DB_PATH = ROOT / "data" / "demo_phase3.db"
db_module.init_db()

from src.core.kill_switch import disarm
from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    Storyboard,
    StoryboardScene,
)
from src.video.assets import AssetManifest
from src.video.producer import VideoProducer
from src.video.tts import MockTTSProvider

disarm()

# ── Demo storyboard: Ronaldo R9 — 1998 World Cup ───────────────────────────────
# All facts sourced from Wikipedia. Clearly labeled as DEMO DATA.

_SOURCES = [
    SourceCitation(
        url="https://en.wikipedia.org/wiki/Ronaldo_(Brazilian_footballer)",
        title="Ronaldo (Brazilian footballer)",
        publisher="Wikipedia",
        date_published="",
    ),
    SourceCitation(
        url="https://en.wikipedia.org/wiki/1998_FIFA_World_Cup_Final",
        title="1998 FIFA World Cup Final",
        publisher="Wikipedia",
        date_published="",
    ),
]

_RESEARCH = [
    ResearchItem(
        fact=(
            "Ronaldo Nazário, nicknamed R9, was widely regarded as the best player "
            "in the world at the 1998 FIFA World Cup in France, having scored 4 goals "
            "in the tournament."
        ),
        source=_SOURCES[0],
        reliability="verified",
    ),
    ResearchItem(
        fact=(
            "Hours before the 1998 World Cup Final against France, Ronaldo suffered "
            "a convulsive fit in his hotel room and was briefly hospitalised, "
            "causing his name to be removed from and then controversially restored "
            "to the Brazilian starting lineup."
        ),
        source=_SOURCES[1],
        reliability="verified",
    ),
    ResearchItem(
        fact=(
            "Despite the pre-match health scare, Ronaldo started the final but Brazil "
            "lost 3-0 to France. Ronaldo said the experience taught him that "
            "football and life must be kept in perspective."
        ),
        source=_SOURCES[1],
        reliability="verified",
    ),
]

_SCENES = [
    StoryboardScene(
        scene_number=1,
        start_time=0.0,
        end_time=7.0,
        narration=(
            "1998. France. The World Cup Final. And the best player on the planet "
            "almost never made it to the pitch."
        ),
        on_screen_text="THE NIGHT THAT SHOOK FOOTBALL",
        visual_requirement="Illustrated graphic of a stadium at night",
        source_indices=[0],
    ),
    StoryboardScene(
        scene_number=2,
        start_time=7.0,
        end_time=20.0,
        narration=(
            "Ronaldo R9 — four goals, unstoppable all tournament. Hours before "
            "kick-off he collapsed in his hotel room with a convulsive fit. "
            "Teammates found him. Doctors rushed in. His name was pulled from "
            "the team sheet — then, mysteriously, put back."
        ),
        on_screen_text="R9: 4 GOALS · 1 NIGHT HE'LL NEVER FORGET",
        visual_requirement="Illustrated graphic of a footballer in action",
        source_indices=[0, 1],
    ),
    StoryboardScene(
        scene_number=3,
        start_time=20.0,
        end_time=30.0,
        narration=(
            "Brazil lost 3-nil. But Ronaldo walked off that pitch, looked at the sky, "
            "and knew something bigger than football had happened. He came back. "
            "Four years later he won the World Cup — and became a legend."
        ),
        on_screen_text="HE CAME BACK. HE WON THE WORLD.",
        visual_requirement="Illustrated graphic of a trophy celebration",
        source_indices=[1, 2],
    ),
]

_STORYBOARD_RAW = Storyboard(
    title="Ronaldo R9: The Night Before the Final",
    content_type=ContentType.PLAYER_STORIES,
    hook="THE NIGHT THAT SHOOK FOOTBALL",
    scenes=_SCENES,
    total_duration=30.0,
    proposed_titles=[
        "The Night Ronaldo Almost Missed the World Cup Final",
        "R9's Secret: What Happened Hours Before the 1998 Final",
        "The Collapse That Almost Ended a Legend",
    ],
    hashtags=[
        "#Shorts", "#football", "#Ronaldo", "#R9", "#WorldCup",
        "#football98", "#Brazil", "#legend", "#playerStory", "#BeyondThePitch",
    ],
    research_items=_RESEARCH,
    generated_by="demo_phase3",
)

# Attach script hash
STORYBOARD = Storyboard.model_validate(
    {**_STORYBOARD_RAW.model_dump(), "script_hash": _STORYBOARD_RAW.compute_hash()}
)

# ── Produce ────────────────────────────────────────────────────────────────────

def main() -> None:
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "demo_phase3_r9.mp4"

    print("=" * 60)
    print("Beyond The Pitch — Phase 3 Demo")
    print("=" * 60)
    print(f"Title   : {STORYBOARD.title}")
    print(f"Type    : {STORYBOARD.content_type.value}")
    print(f"Scenes  : {len(STORYBOARD.scenes)}")
    print(f"Duration: {STORYBOARD.total_duration}s")
    print(f"Output  : {output_path}")
    print(f"TTS     : MockTTSProvider (silent audio — offline demo)")
    print("-" * 60)

    manifest = AssetManifest(manifest_path=ROOT / "data" / "demo_asset_manifest.json")
    producer = VideoProducer(
        tts_provider=MockTTSProvider(),
        manifest=manifest,
        bypass_review=True,
    )

    print("Rendering… (this may take 30–90 seconds)")
    result = producer.produce(STORYBOARD, output_path=output_path)

    print()
    if result.success:
        print("✓ Production succeeded")
        print(f"  File     : {result.output_path}")
        print(f"  Render ID: {result.render_id}")
        print()
        print("QC Report:")
        print(result.qc.report())
    else:
        print("✗ Production FAILED")
        print(f"  Reason: {result.failure_reason}")
        if result.qc:
            print()
            print("QC Report:")
            print(result.qc.report())
        sys.exit(1)


if __name__ == "__main__":
    main()
