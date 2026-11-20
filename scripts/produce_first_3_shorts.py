#!/usr/bin/env python3
"""
Produce the first 3 Beyond The Pitch Shorts.

Three verified football moments, written directly as storyboards so no API key
is needed. Each video is a storytelling Short using CC0 atmosphere B-roll and
DRAMATIC_REVEAL animated captions.

Stories:
  1. Zidane's headbutt — 2006 World Cup Final, his last professional act
  2. Messi's 91 — breaking a 40-year record in a single calendar year
  3. Ronaldinho at the Bernabéu — the night Madrid fans applauded the opponent

Output: output/YYYY-MM-DD/   — one MP4 + thumbnail + metadata.txt per video

Usage:
  source venv/bin/activate
  python scripts/produce_first_3_shorts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from src.core.database import init_db
from src.core.logger import configure_logging, get_logger
from src.production.auto_producer import AutoProducer
from src.research.models import (
    ContentType,
    ResearchItem,
    SourceCitation,
    Storyboard,
    StoryboardScene,
)

configure_logging()
logger = get_logger("produce_first_3")

# ── Wikipedia sources ─────────────────────────────────────────────────────────

_SRC_ZIDANE = SourceCitation(
    url="https://en.wikipedia.org/wiki/2006_FIFA_World_Cup_Final",
    title="2006 FIFA World Cup Final",
    publisher="Wikipedia",
)
_SRC_MESSI = SourceCitation(
    url="https://en.wikipedia.org/wiki/Lionel_Messi",
    title="Lionel Messi",
    publisher="Wikipedia",
)
_SRC_RONALDINHO = SourceCitation(
    url="https://en.wikipedia.org/wiki/El_Cl%C3%A1sico",
    title="El Clásico",
    publisher="Wikipedia",
)


# ── Storyboard 1 — Zidane's headbutt ─────────────────────────────────────────

def _zidane_storyboard() -> Storyboard:
    items = [
        ResearchItem(
            fact="The 2006 FIFA World Cup Final on July 9, 2006 ended 1-1 after extra time.",
            source=_SRC_ZIDANE, reliability="verified",
        ),
        ResearchItem(
            fact="In the 110th minute Zinedine Zidane headbutted Marco Materazzi and received a red card.",
            source=_SRC_ZIDANE, reliability="verified",
        ),
        ResearchItem(
            fact="Zidane walked off past the World Cup trophy in what was his final professional match.",
            source=_SRC_ZIDANE, reliability="verified",
        ),
        ResearchItem(
            fact="Italy defeated France 5-3 on penalties to win the 2006 World Cup.",
            source=_SRC_ZIDANE, reliability="verified",
        ),
    ]
    scenes = [
        StoryboardScene(
            scene_number=1, start_time=0.0, end_time=4.0,
            narration="2006 World Cup Final.",
            on_screen_text="2006 WORLD CUP FINAL.",
            visual_requirement="Stadium wide shot, crowd atmosphere",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=2, start_time=4.0, end_time=8.0,
            narration="Zidane's last game ever.",
            on_screen_text="ZIDANE'S LAST GAME.",
            visual_requirement="Stadium atmosphere, night shot",
            source_indices=[2],
        ),
        StoryboardScene(
            scene_number=3, start_time=8.0, end_time=12.0,
            narration="108 minutes. France and Italy level.",
            on_screen_text="108 MINUTES. STILL LEVEL.",
            visual_requirement="Crowd tension, stadium lights",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=4, start_time=12.0, end_time=16.0,
            narration="Materazzi said something.",
            on_screen_text="MATERAZZI SAID SOMETHING.",
            visual_requirement="Crowd reaction shot",
            source_indices=[1],
        ),
        StoryboardScene(
            scene_number=5, start_time=16.0, end_time=20.0,
            narration="Zidane turned. Headbutt.",
            on_screen_text="ZIDANE TURNED.",
            visual_requirement="Crowd gasp reaction",
            source_indices=[1],
        ),
        StoryboardScene(
            scene_number=6, start_time=20.0, end_time=24.0,
            narration="Red card. Final act.",
            on_screen_text="RED CARD.",
            visual_requirement="Stadium wide, subdued atmosphere",
            source_indices=[2],
        ),
        StoryboardScene(
            scene_number=7, start_time=24.0, end_time=28.0,
            narration="Italy won. Nobody remembers.",
            on_screen_text="NOBODY REMEMBERS.",
            visual_requirement="Celebration crowd shot",
            source_indices=[3],
        ),
    ]
    sb = Storyboard(
        title="Zidane's Last Act — The Headbutt That Shocked the World",
        content_type=ContentType.PLAYER_STORIES,
        hook="HIS LAST GAME EVER.",
        scenes=scenes,
        total_duration=28.0,
        proposed_titles=[
            "Zidane's Last Professional Act Was a Red Card",
            "The Headbutt That Ended a Legend's Career",
            "2006 World Cup Final: The Moment Everyone Remembers",
        ],
        hashtags=[
            "#Shorts", "#football", "#Zidane", "#WorldCup", "#2006WorldCup",
            "#football shorts", "#BeyondThePitch", "#footballhistory",
        ],
        research_items=items,
        generated_by="claude",
    )
    sb = sb.model_copy(update={"script_hash": sb.compute_hash()})
    return sb


# ── Storyboard 2 — Messi's 91 goals ──────────────────────────────────────────

def _messi_91_storyboard() -> Storyboard:
    items = [
        ResearchItem(
            fact="Gerd Müller scored 85 goals in 1972, a world record that stood for 40 years.",
            source=_SRC_MESSI, reliability="verified",
        ),
        ResearchItem(
            fact="In 2012, Lionel Messi scored 91 goals in a single calendar year, breaking Müller's record.",
            source=_SRC_MESSI, reliability="verified",
        ),
        ResearchItem(
            fact="On December 9, 2012, Messi scored twice against Real Betis to reach 90 and 91 goals.",
            source=_SRC_MESSI, reliability="verified",
        ),
        ResearchItem(
            fact="Messi's 91 goals in 2012 is recognised by Guinness World Records.",
            source=_SRC_MESSI, reliability="verified",
        ),
    ]
    scenes = [
        StoryboardScene(
            scene_number=1, start_time=0.0, end_time=4.5,
            narration="2012. One man. One year.",
            on_screen_text="2012. ONE YEAR.",
            visual_requirement="Stadium atmosphere, wide shot",
            source_indices=[1],
        ),
        StoryboardScene(
            scene_number=2, start_time=4.5, end_time=9.5,
            narration="Gerd Müller: 85 goals in 1972.",
            on_screen_text="MÜLLER: 85 GOALS IN 1972.",
            visual_requirement="Crowd anticipation, stadium lights",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=3, start_time=9.5, end_time=14.5,
            narration="That record stood for 40 years.",
            on_screen_text="40 YEARS UNBROKEN.",
            visual_requirement="Stadium wide, atmospheric",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=4, start_time=14.5, end_time=18.5,
            narration="Until Lionel Messi.",
            on_screen_text="UNTIL MESSI.",
            visual_requirement="Crowd roar, celebration atmosphere",
            source_indices=[1],
        ),
        StoryboardScene(
            scene_number=5, start_time=18.5, end_time=23.0,
            narration="Goal 90. Goal 91.",
            on_screen_text="GOAL 90. GOAL 91.",
            visual_requirement="Crowd celebration, goal reaction",
            source_indices=[2],
        ),
        StoryboardScene(
            scene_number=6, start_time=23.0, end_time=28.0,
            narration="91 goals. Nobody touches this.",
            on_screen_text="91. NOBODY TOUCHES THIS.",
            visual_requirement="Stadium atmosphere, wide dramatic shot",
            source_indices=[3],
        ),
    ]
    sb = Storyboard(
        title="Messi's 91 Goals in 2012 — The Record That Can't Be Broken",
        content_type=ContentType.PLAYER_STORIES,
        hook="91 GOALS. ONE YEAR.",
        scenes=scenes,
        total_duration=28.0,
        proposed_titles=[
            "Messi Scored 91 Goals in a Single Year",
            "The Record Nobody Will Ever Break",
            "91 Goals in 2012: Messi's Impossible Year",
        ],
        hashtags=[
            "#Shorts", "#football", "#Messi", "#LionelMessi", "#footballrecord",
            "#footballhistory", "#BeyondThePitch", "#footballshorts",
        ],
        research_items=items,
        generated_by="claude",
    )
    sb = sb.model_copy(update={"script_hash": sb.compute_hash()})
    return sb


# ── Storyboard 3 — Ronaldinho at the Bernabéu ─────────────────────────────────

def _ronaldinho_bernabeu_storyboard() -> Storyboard:
    items = [
        ResearchItem(
            fact="On November 19, 2005, Barcelona defeated Real Madrid 3-0 at the Santiago Bernabéu.",
            source=_SRC_RONALDINHO, reliability="verified",
        ),
        ResearchItem(
            fact="Ronaldinho scored twice for Barcelona in the 3-0 victory at the Bernabéu.",
            source=_SRC_RONALDINHO, reliability="verified",
        ),
        ResearchItem(
            fact="Real Madrid's own supporters gave Ronaldinho a standing ovation after his second goal.",
            source=_SRC_RONALDINHO, reliability="verified",
        ),
        ResearchItem(
            fact="It is considered one of the most remarkable individual tributes in football history.",
            source=_SRC_RONALDINHO, reliability="verified",
        ),
    ]
    scenes = [
        StoryboardScene(
            scene_number=1, start_time=0.0, end_time=4.0,
            narration="November 19, 2005.",
            on_screen_text="NOVEMBER 19, 2005.",
            visual_requirement="Stadium exterior, night atmosphere",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=2, start_time=4.0, end_time=8.0,
            narration="Real Madrid's home. The Bernabéu.",
            on_screen_text="THE BERNABÉU.",
            visual_requirement="Stadium wide, crowd packed",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=3, start_time=8.0, end_time=12.0,
            narration="Ronaldinho scored. Then scored again.",
            on_screen_text="TWO GOALS.",
            visual_requirement="Crowd roar, celebration atmosphere",
            source_indices=[1],
        ),
        StoryboardScene(
            scene_number=4, start_time=12.0, end_time=16.0,
            narration="Barcelona won 3-0. At the Bernabéu.",
            on_screen_text="3-0. AT THE BERNABÉU.",
            visual_requirement="Stadium atmosphere post-goal",
            source_indices=[0],
        ),
        StoryboardScene(
            scene_number=5, start_time=16.0, end_time=20.0,
            narration="Then something extraordinary happened.",
            on_screen_text="THEN SOMETHING HAPPENED.",
            visual_requirement="Crowd reaction, stadium wide",
            source_indices=[2],
        ),
        StoryboardScene(
            scene_number=6, start_time=20.0, end_time=24.0,
            narration="Madrid fans stood. Applauded him.",
            on_screen_text="MADRID FANS APPLAUDED.",
            visual_requirement="Stadium crowd standing",
            source_indices=[2],
        ),
        StoryboardScene(
            scene_number=7, start_time=24.0, end_time=28.0,
            narration="The opponent. At their own ground.",
            on_screen_text="THE OPPONENT.",
            visual_requirement="Atmospheric stadium wide shot",
            source_indices=[3],
        ),
    ]
    sb = Storyboard(
        title="Ronaldinho Made Real Madrid Fans Applaud the Opponent",
        content_type=ContentType.PLAYER_STORIES,
        hook="MADRID FANS APPLAUDED HIM.",
        scenes=scenes,
        total_duration=28.0,
        proposed_titles=[
            "Real Madrid Fans Applauded Ronaldinho at the Bernabéu",
            "The Night Ronaldinho Made Madrid Fans Stand Up",
            "Ronaldinho at the Bernabéu — The Standing Ovation",
        ],
        hashtags=[
            "#Shorts", "#football", "#Ronaldinho", "#Barcelona", "#RealMadrid",
            "#ElClasico", "#BeyondThePitch", "#footballhistory",
        ],
        research_items=items,
        generated_by="claude",
    )
    sb = sb.model_copy(update={"script_hash": sb.compute_hash()})
    return sb


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_db()

    storyboards = [
        _zidane_storyboard(),
        _messi_91_storyboard(),
        _ronaldinho_bernabeu_storyboard(),
    ]

    producer = AutoProducer(save_only=True, dry_run=False)
    results = []

    for i, sb in enumerate(storyboards, 1):
        print(f"\n{'='*60}")
        print(f"Producing Short {i}/3: {sb.title}")
        print(f"{'='*60}")
        result = producer.produce_one(sb)
        results.append((sb, result))
        if result.success:
            print(f"  ✓  {result.output_path}")
            if result.metadata_path:
                print(f"  ✓  {result.metadata_path}")
            if result.thumbnail_path:
                print(f"  ✓  {result.thumbnail_path}")
        else:
            print(f"  ✗  FAILED: {result.failure_reason}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    succeeded = [r for _, r in results if r.success]
    print(f"{len(succeeded)}/3 videos produced successfully")
    if succeeded:
        folder = succeeded[0].output_path.parent
        print(f"\nAll files saved to:\n  {folder}/\n")
        for sb, r in results:
            status = "✓" if r.success else "✗"
            name = r.output_path.name if r.output_path else "FAILED"
            print(f"  {status}  {name}")
            print(f"       Title: {sb.proposed_titles[0]}")
            print()


if __name__ == "__main__":
    main()
