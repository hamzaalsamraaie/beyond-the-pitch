"""
demo_phase3_macos.py — Phase 3 improved demo: MacOS TTS with spoken narration

Improvements over demo_phase3.py:
  1. MacOSTTSProvider: Samantha voice, real speech synthesis
  2. Narrations verified to fit within scene budgets (no word cutoff)
  3. Pre-flight check: measures natural TTS duration before rendering
  4. Full narration subtitle display (no 90-char truncation)
  5. Contact sheet: 6 representative frames extracted for visual review
  6. FFprobe audio level analysis confirms audio contains speech

Run:
    source venv/bin/activate
    python demo_phase3_macos.py

Outputs:
    output/demo_phase3_macos_r9.mp4
    output/demo_phase3_macos_contact.jpg
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import src.core.database as db_module

db_module.DB_PATH = ROOT / "data" / "demo_phase3_macos.db"
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
from src.video.contact_sheet import make_contact_sheet
from src.video.producer import VideoProducer
from src.video.tts import MacOSTTSProvider, measure_natural_tts_duration

disarm()

# ── Narration design notes ─────────────────────────────────────────────────────
#
# macOS Samantha voice: ~3.5 words/second (measured, not assumed).
# Each narration was pre-synthesised and timed before use.
# Scene budgets and measured natural durations:
#
#   Scene 1 (7.0s):  5.6s natural  → 1.4s trailing silence  ✓
#   Scene 2 (13.0s): 11.6s natural → 1.4s trailing silence  ✓
#   Scene 3 (10.0s): 8.5s natural  → 1.5s trailing silence  ✓
#
# Trailing silence is intentional: it lets the viewer absorb the frame
# before the next scene begins.

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
            "Ronaldo Nazário, nicknamed R9, scored four goals at the 1998 FIFA "
            "World Cup in France and was regarded as the best player in the world."
        ),
        source=_SOURCES[0],
        reliability="verified",
    ),
    ResearchItem(
        fact=(
            "Hours before the 1998 World Cup Final against France, Ronaldo "
            "suffered a convulsive fit and was hospitalised, causing his name to "
            "be removed from and then controversially restored to the starting lineup."
        ),
        source=_SOURCES[1],
        reliability="verified",
    ),
    ResearchItem(
        fact=(
            "Ronaldo returned to win the 2002 FIFA World Cup with Brazil, scoring "
            "two goals in the final against Germany and finishing as the tournament's "
            "top scorer with eight goals."
        ),
        source=_SOURCES[0],
        reliability="verified",
    ),
]

_SCENES = [
    StoryboardScene(
        scene_number=1,
        start_time=0.0,
        end_time=7.0,
        # 15 words — measured 5.6s natural on Samantha (1.4s padding)
        narration="1998. The World Cup Final. And Ronaldo R9 almost never made it to the pitch.",
        on_screen_text="THE NIGHT THAT SHOOK FOOTBALL",
        visual_requirement="Illustrated graphic of a stadium at night",
        source_indices=[0],
    ),
    StoryboardScene(
        scene_number=2,
        start_time=7.0,
        end_time=20.0,
        # 33 words — measured 11.6s natural on Samantha (1.4s padding)
        narration=(
            "R9 had scored four goals all tournament. Hours before kick-off he collapsed "
            "in his hotel room. Teammates found him, doctors rushed in. His name vanished "
            "from the starting lineup, then came back."
        ),
        on_screen_text="R9 COLLAPSED HOURS BEFORE KICK-OFF",
        visual_requirement="Illustrated graphic of a footballer in action",
        source_indices=[0, 1],
    ),
    StoryboardScene(
        scene_number=3,
        start_time=20.0,
        end_time=30.0,
        # 28 words — measured 8.5s natural on Samantha (1.5s padding)
        narration=(
            "Brazil lost three nil. But four years later Ronaldo came back better than ever. "
            "He won the 2002 World Cup and became the greatest of his generation."
        ),
        on_screen_text="HE CAME BACK AND WON THE WORLD",
        visual_requirement="Illustrated graphic of a trophy celebration",
        source_indices=[1, 2],
    ),
]

_SB_RAW = Storyboard(
    title="Ronaldo R9: The Night Before the Final",
    content_type=ContentType.PLAYER_STORIES,
    hook="THE NIGHT THAT SHOOK FOOTBALL",
    scenes=_SCENES,
    total_duration=30.0,
    proposed_titles=[
        "The Night Ronaldo Almost Missed the World Cup Final",
        "R9: What Happened Hours Before the 1998 Final",
        "The Collapse That Almost Ended a Legend",
    ],
    hashtags=[
        "#Shorts", "#football", "#Ronaldo", "#R9", "#WorldCup",
        "#Brazil", "#legend", "#playerStory", "#BeyondThePitch", "#1998",
    ],
    research_items=_RESEARCH,
    generated_by="demo_phase3_macos",
)
STORYBOARD = Storyboard.model_validate(
    {**_SB_RAW.model_dump(), "script_hash": _SB_RAW.compute_hash()}
)


# ── Pre-flight TTS duration check ─────────────────────────────────────────────

def preflight_check(voice: str = "Samantha") -> bool:
    """
    Measure natural TTS duration for each scene and report fit quality.
    Returns True if all scenes fit within budget (no trimming required).
    """
    print("\nPre-flight TTS duration check (Samantha voice):")
    print(f"  {'Scene':<8} {'Budget':>8} {'Natural':>9} {'Padding':>9}  Status")
    print("  " + "-" * 55)

    all_ok = True
    for i, scene in enumerate(STORYBOARD.scenes, 1):
        natural = measure_natural_tts_duration(scene.narration, voice=voice)
        budget = scene.duration
        padding = budget - natural
        ratio = natural / budget if budget > 0 else 1.0

        if ratio > 1.05:
            status = "OVER BUDGET — will trim (words may be cut off)"
            all_ok = False
        elif ratio > 0.95:
            status = "tight fit"
        elif padding < 2.0:
            status = "good fit"
        else:
            status = f"fits ({padding:.1f}s silence)"

        marker = "✗" if ratio > 1.05 else "✓"
        print(
            f"  {marker} Sc {i:<5} {budget:>7.1f}s  {natural:>7.2f}s  {padding:>+7.2f}s  {status}"
        )

    return all_ok


# ── FFprobe deep inspection ────────────────────────────────────────────────────

def ffprobe_inspect(video_path: Path) -> None:
    """Print detailed FFprobe output including audio level analysis."""
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")

    # Stream info
    r = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(video_path)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    print(f"\nFFprobe inspection: {video_path.name}")
    print(f"  Container  : {fmt.get('format_name', '?')}")
    print(f"  Duration   : {float(fmt.get('duration', 0)):.3f}s")
    print(f"  Bit rate   : {int(fmt.get('bit_rate', 0)) // 1000} kbps")
    print(f"  File size  : {int(fmt.get('size', 0)):,} bytes")
    print(f"  Video      : {video.get('codec_name','?')} "
          f"{video.get('width','?')}×{video.get('height','?')} "
          f"{video.get('r_frame_rate','?')} fps")
    print(f"  Audio      : {audio.get('codec_name','?')} "
          f"{audio.get('sample_rate','?')} Hz "
          f"{audio.get('channels','?')}ch "
          f"{audio.get('bit_rate','?')} bps")

    # Audio level analysis
    r2 = subprocess.run(
        [ffmpeg, "-i", str(video_path),
         "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    stderr = r2.stderr
    mean_vol = "?"
    max_vol = "?"
    for line in stderr.splitlines():
        if "mean_volume" in line:
            mean_vol = line.split("mean_volume:")[-1].strip()
        if "max_volume" in line:
            max_vol = line.split("max_volume:")[-1].strip()
    print(f"  Audio mean : {mean_vol} (silent audio = -91 dB; speech = -20 to -6 dB)")
    print(f"  Audio peak : {max_vol}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "demo_phase3_macos_r9.mp4"
    contact_path = output_dir / "demo_phase3_macos_contact.jpg"

    print("=" * 65)
    print("Beyond The Pitch — Phase 3 MacOSTTS Demo")
    print("=" * 65)
    print(f"Title   : {STORYBOARD.title}")
    print(f"Type    : {STORYBOARD.content_type.value}")
    print(f"Scenes  : {len(STORYBOARD.scenes)}")
    print(f"Duration: {STORYBOARD.total_duration}s")
    print(f"Output  : {output_path}")
    print(f"TTS     : MacOSTTSProvider (Samantha voice — real speech)")
    print("-" * 65)

    # Pre-flight
    ok = preflight_check(voice="Samantha")
    if not ok:
        print("\n[WARNING] One or more scenes over budget — proceeding with trim.")
    else:
        print("\n  All narrations fit within scene budgets. No word cutoff expected.")

    # Render
    manifest = AssetManifest(manifest_path=ROOT / "data" / "demo_macos_manifest.json")
    producer = VideoProducer(
        tts_provider=MacOSTTSProvider(),
        manifest=manifest,
        bypass_review=True,
    )

    print("\nRendering… (30-60 seconds)")
    result = producer.produce(STORYBOARD, output_path=output_path)

    print()
    if not result.success:
        print("✗ Production FAILED")
        print(f"  Reason: {result.failure_reason}")
        if result.qc:
            print(result.qc.report())
        sys.exit(1)

    print("✓ Production succeeded")
    print(f"  File     : {result.output_path}")
    print(f"  Render ID: {result.render_id}")
    print()
    print(result.qc.report())

    # FFprobe deep inspection
    ffprobe_inspect(output_path)

    # Contact sheet
    print("\nGenerating contact sheet…")
    # Timestamps: start + midpoint of each scene
    scene_timestamps = []
    for scene in STORYBOARD.scenes:
        scene_timestamps.append(scene.start_time + 0.5)
        scene_timestamps.append((scene.start_time + scene.end_time) / 2)
    make_contact_sheet(
        video_path=output_path,
        timestamps=scene_timestamps,
        output_path=contact_path,
        thumb_w=360,
        thumb_h=640,
        cols=3,
    )
    print(f"✓ Contact sheet: {contact_path}")

    print("\n" + "=" * 65)
    print("Output files:")
    print(f"  MP4           : {output_path}")
    print(f"  Contact sheet : {contact_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
