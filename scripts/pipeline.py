#!/usr/bin/env python3
"""
Beyond The Pitch — end-to-end production pipeline.

COMMANDS
────────
  clip    --source-id UUID [options]
            Process an approved footage asset into a finished Short.

  auto    [--limit N] [--dry-run]
            Discover trends, find approved footage, produce up to N Shorts.

  produce materazzi [--tts macos|openai|mock] [--output PATH]
            Produce the Materazzi demo Short using CC-BY photos (photo fallback).

  upload  --render-id ID [--visibility private|public]
            Upload a completed render to YouTube (needs OAuth credentials).

  analytics
            Fetch YouTube Analytics for all uploaded videos.

  status
            Print DB summary: footage assets, renders, uploads, analytics.

REQUIRED CREDENTIALS (add to .env)
────────────────────────────────────
  YOUTUBE_API_KEY       — trend discovery (read-only, already set)
  ANTHROPIC_API_KEY     — Claude script generation (optional, falls back to static)
  OPENAI_API_KEY        — OpenAI TTS (optional, falls back to macOS/mock)
  YOUTUBE_CLIENT_ID     — OAuth upload + analytics (BLOCKER for publishing)
  YOUTUBE_CLIENT_SECRET — OAuth upload + analytics (BLOCKER for publishing)

USAGE EXAMPLES
────────────────────────────────────
  source venv/bin/activate

  # Register a rights-cleared stock video and approve it
  python scripts/footage_catalog.py import stock \\
    --url "https://pixabay.com/videos/..." \\
    --local-path output/footage/my_clip.mp4
  python scripts/footage_catalog.py approve --id UUID

  # Clip it into a Short
  python scripts/pipeline.py clip --source-id UUID

  # Upload to YouTube (private)
  python scripts/pipeline.py upload --render-id 1

  # Demo without real footage
  python scripts/pipeline.py produce materazzi --tts macos
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── Make project root importable ──────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

import src.core.database as db_module
from src.core.database import init_db
from src.core.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("pipeline")


# ── Command implementations ───────────────────────────────────────────────────

def cmd_clip(args: argparse.Namespace) -> int:
    """Process an approved footage asset into a Short."""
    from src.clipping.transcriber import get_transcriber
    from src.clipping.clip_selector import select_clip
    from src.clipping.editor import ClipEditor
    from src.footage.catalog import FootageCatalog
    from src.footage.models import ApprovalStatus
    from src.planning.metadata_generator import generate_from_clip, AttributionEntry

    init_db()
    catalog = FootageCatalog()
    asset = catalog.get_asset(args.source_id)
    if asset is None:
        print(f"ERROR: Footage asset {args.source_id!r} not found in catalog.")
        return 1

    if asset.approval_status != ApprovalStatus.APPROVED:
        print(
            f"ERROR: Asset {args.source_id} is {asset.approval_status.value}, not APPROVED.\n"
            f"Run: python scripts/footage_catalog.py approve --id {args.source_id}"
        )
        return 1

    local_path = Path(asset.local_path)
    if not local_path.exists():
        print(f"ERROR: Local file not found: {local_path}")
        return 1

    # Transcribe
    transcriber = get_transcriber(args.transcriber if hasattr(args, "transcriber") else None)
    print(f"⟳  Transcribing {local_path.name} with {transcriber.name}…")
    transcript = transcriber.transcribe(local_path)
    print(f"   {len(transcript.segments)} segments, language={transcript.language}")

    # Select clip
    clip = select_clip(
        transcript=transcript,
        footage_asset_id=args.source_id,
        source_path=local_path,
        target_duration=float(getattr(args, "duration", 45)),
    )
    if clip is None:
        print("ERROR: No suitable highlight window found in this video.")
        return 1

    print(
        f"   Clip selected: {clip.start:.1f}s–{clip.end:.1f}s  "
        f"score={clip.score:.3f}  hook={clip.hook_text[:60]!r}"
    )

    # Edit
    output_path = Path(args.output) if getattr(args, "output", None) else None
    editor = ClipEditor()
    print("⟳  Editing (reframe → captions → audio)…")
    result = editor.edit(clip, output_path=output_path)

    if not result.success:
        print(f"ERROR: Edit failed: {result.failure_reason}")
        return 1

    # Metadata
    attributions = []
    if asset.attribution_required and asset.attribution_text:
        attributions.append(AttributionEntry(
            asset_description=asset.description or asset.source_url[:60],
            creator_name=asset.creator_name,
            license_type=asset.license_type.value,
            attribution_text=asset.attribution_text,
        ))
    metadata = generate_from_clip(
        source_title=asset.description or local_path.stem,
        hook_text=clip.hook_text,
        clip_duration_secs=clip.duration,
        attributions=attributions,
    )

    print(f"\n✓  Short ready: {result.output_path}")
    print(f"   QC passed={result.qc.passed}  "
          f"duration={result.qc.measured_duration_secs:.1f}s  "
          f"size={result.qc.file_size_bytes // 1024}KB")
    print(f"   Title: {metadata.title}")
    print(f"   Tags:  {', '.join(metadata.tags[:8])}")
    print(f"\n   Render DB id: {result.render_id}")
    print(f"   Upload:  python scripts/pipeline.py upload --render-id {result.render_id}")
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    """Automated discovery → clip → Short pipeline."""
    from src.clipping.transcriber import get_transcriber
    from src.clipping.clip_selector import select_clip
    from src.clipping.editor import ClipEditor
    from src.footage.catalog import FootageCatalog
    from src.footage.models import ApprovalStatus
    from src.trends.discovery import discover_shorts
    from src.trends.youtube_client import YouTubeClient
    from src.planning.metadata_generator import generate_from_clip

    init_db()

    # 1. Discover trending topics
    print("⟳  Discovering trends…")
    try:
        yt_client = YouTubeClient()
        shorts = discover_shorts(yt_client, queries=["football highlights"], max_per_query=20)
        print(f"   {len(shorts)} trending Shorts found")
    except Exception as exc:
        print(f"   Trend discovery failed ({exc}), continuing with catalog scan.")
        shorts = []

    # 2. Find approved footage
    catalog = FootageCatalog()
    approved = [
        a for a in catalog.list_assets()
        if a.approval_status == ApprovalStatus.APPROVED and a.local_path
    ]
    print(f"   {len(approved)} approved footage assets in catalog")

    if not approved:
        print(
            "\nBLOCKER: No approved footage assets found.\n"
            "To add stock footage:\n"
            "  python scripts/footage_catalog.py import stock --url URL --local-path FILE\n"
            "  python scripts/footage_catalog.py approve --id UUID\n"
            "\nTo add creator-authorized footage:\n"
            "  python scripts/footage_catalog.py request-permission --creator-url URL\n"
            "  (wait for written reply, then confirm and approve)"
        )
        return 1

    limit = int(getattr(args, "limit", 1))
    dry_run = getattr(args, "dry_run", False)
    produced = 0

    for asset in approved[:limit]:
        local = Path(asset.local_path)
        if not local.exists():
            print(f"   SKIP {asset.id[:8]}: local file missing at {local}")
            continue

        print(f"\n⟳  Processing {local.name} ({asset.id[:8]})…")
        if dry_run:
            print("   DRY RUN — skipping actual render")
            produced += 1
            continue

        transcriber = get_transcriber()
        transcript = transcriber.transcribe(local)
        clip = select_clip(transcript, asset.id, local)
        if clip is None:
            print(f"   SKIP: no highlight window found")
            continue

        result = ClipEditor().edit(clip)
        if result.success:
            print(f"   ✓  {result.output_path}  render_id={result.render_id}")
            produced += 1
        else:
            print(f"   FAIL: {result.failure_reason}")

    print(f"\nProduced {produced}/{min(limit, len(approved))} Short(s).")
    return 0 if produced > 0 else 1


def cmd_produce_materazzi(args: argparse.Namespace) -> int:
    """Produce the Materazzi demo Short using CC-BY photos (photo fallback path)."""
    from src.video.tts import get_tts_provider
    from src.video.producer import VideoProducer
    from src.video.photo_compositor import PhotoCompositor, build_scene_configs
    from src.video.ffmpeg_builder import pipe_frames_to_mp4, concatenate_audio
    from src.video.quality_control import run_qc
    from src.planning.script_generator import generate_zidane_headbutt_script
    from src.research.models import (
        ContentType, Storyboard, StoryboardScene, ResearchItem, SourceCitation
    )
    import hashlib, json, tempfile

    init_db()

    # Build a Storyboard from the hardcoded script
    script = generate_zidane_headbutt_script()
    # Convert script sections → StoryboardScene list
    t = 0.0
    scenes = []
    for i, sec in enumerate(script.sections):
        scenes.append(StoryboardScene(
            scene_number=i + 1,
            start_time=t,
            end_time=t + sec.duration_secs,
            narration=sec.text,
            on_screen_text=sec.name.upper(),
            visual_requirement="CC-BY photo",
            source_indices=[0],
        ))
        t += sec.duration_secs

    # Minimal Storyboard model
    research_items = [
        ResearchItem(
            fact="2006 FIFA World Cup Final: Zidane headbutt on Materazzi led to red card.",
            source=SourceCitation(
                url="https://en.wikipedia.org/wiki/2006_FIFA_World_Cup_Final",
                title="2006 FIFA World Cup Final",
                publisher="Wikipedia",
                date_published="",
            ),
            reliability="verified",
        )
    ]
    sb_data = {
        "title": script.idea_title,
        "content_type": "player_stories",
        "hook": "2006 World Cup Final. And Zidane completely lost it.",
        "scenes": [s.model_dump() for s in scenes],
        "total_duration": t,
        "proposed_titles": [
            "The Headbutt That Ended a Legend",
            "Zidane's Last Act: The 2006 World Cup Scandal",
            "What Materazzi Said to Make Zidane Snap",
        ],
        "hashtags": ["#Shorts", "#football", "#Zidane", "#WorldCup", "#footballstories"],
        "research_items": [item.model_dump() for item in research_items],
        "generated_by": "static",
    }
    storyboard = Storyboard.model_validate(sb_data)
    h = hashlib.sha256(json.dumps(sb_data).encode()).hexdigest()[:32]
    storyboard = Storyboard.model_validate({**storyboard.model_dump(), "script_hash": h})

    # Photo assignments
    photos_dir = _ROOT / "output" / "phase_b_materazzi" / "assets" / "photos"
    zidane_1 = photos_dir / "zidane_wcf2006_cc_by_2.0.jpg"
    zidane_2 = photos_dir / "zidane_thuram_final_cc_by_2.0.jpg"
    materazzi = photos_dir / "materazzi_hires_cc_by_2.0.jpg"

    photo_paths = [zidane_1, zidane_1, zidane_2, zidane_2, materazzi, zidane_1]
    effects = ["zoom_in", "pan_right", "zoom_in", "zoom_out", "slow_push", "zoom_out"]
    scene_configs = build_scene_configs(storyboard, photo_paths, effects)

    # TTS
    tts_name = getattr(args, "tts", "macos")
    tts = get_tts_provider(tts_name)
    print(f"⟳  TTS provider: {tts.name}")

    output_path = Path(getattr(args, "output", None) or
                       (_ROOT / "output" / "materazzi_youtube_short.mp4"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    compositor = PhotoCompositor(storyboard, scene_configs, fps=30)
    compositor.prepare()
    total_frames = compositor.total_frames()
    print(f"⟳  Rendering {total_frames} frames ({storyboard.total_duration:.0f}s)…")

    with tempfile.TemporaryDirectory(prefix="btp_materazzi_") as tmp:
        tmp_dir = Path(tmp)
        audio_dir = tmp_dir / "audio"
        audio_dir.mkdir()

        # TTS per scene
        audio_paths = []
        for i, scene in enumerate(storyboard.scenes):
            out_wav = audio_dir / f"scene_{i:02d}.wav"
            tts.synthesize(scene.narration, scene.duration, out_wav)
            audio_paths.append(out_wav)

        combined_wav = tmp_dir / "combined.wav"
        concatenate_audio(audio_paths, combined_wav)

        pipe_frames_to_mp4(
            frame_generator=compositor.generate_frames(),
            total_frames=total_frames,
            fps=30,
            combined_audio_path=combined_wav,
            output_path=output_path,
        )

    qc = run_qc(output_path, storyboard.total_duration, tts.name)
    print(f"\n{'✓' if qc.passed else '✗'}  QC: {qc.report()}")
    print(f"   Output: {output_path}")
    print(
        "\nAttributions required in description:\n"
        "  Photo: David Ruddell (Zidane shots) — CC BY 2.0\n"
        "  Photo: Oscar Federico Bodini (Materazzi) — CC BY 2.0\n"
        "\nNext: python scripts/pipeline.py upload --local-path " + str(output_path)
    )
    return 0 if qc.passed else 1


def cmd_upload(args: argparse.Namespace) -> int:
    """Upload a completed render to YouTube."""
    from src.youtube.uploader import YouTubeUploader
    from src.youtube.oauth import credentials_available

    if not credentials_available():
        print(
            "BLOCKER: YouTube OAuth credentials are not set.\n"
            "Add to .env:\n"
            "  YOUTUBE_CLIENT_ID=...\n"
            "  YOUTUBE_CLIENT_SECRET=...\n"
            "Create them at: Google Cloud Console → APIs & Services → Credentials\n"
            "  (Desktop application, YouTube Data API v3 scope)"
        )
        return 1

    init_db()

    # Resolve video path from render_id or local_path
    video_path: Path | None = None
    video_db_id: int | None = None

    if hasattr(args, "render_id") and args.render_id:
        with db_module._connect() as conn:
            row = conn.execute(
                "SELECT local_path, id FROM renders WHERE id=?",
                (args.render_id,)
            ).fetchone()
        if not row:
            print(f"ERROR: Render ID {args.render_id} not found.")
            return 1
        video_path = Path(row["local_path"])
    elif hasattr(args, "local_path") and args.local_path:
        video_path = Path(args.local_path)
    else:
        print("ERROR: Provide --render-id or --local-path")
        return 1

    if not video_path.exists():
        print(f"ERROR: Video file not found: {video_path}")
        return 1

    # Build metadata from CLI args or defaults
    from src.youtube.uploader import VideoMetadata
    visibility = getattr(args, "visibility", "private")
    title = getattr(args, "title", None) or video_path.stem.replace("_", " ").title()
    metadata = VideoMetadata(
        title=title[:100],
        description=f"Beyond The Pitch — Football stories you've forgotten.\n\n{video_path.name}",
        tags=["Shorts", "football", "soccer"],
        visibility=visibility,
    )

    uploader = YouTubeUploader()
    print(f"⟳  Uploading {video_path.name} as {visibility}…")
    result = uploader.upload(video_path, metadata, video_db_id=video_db_id)

    if result.is_duplicate:
        print("Already uploaded (duplicate). Skipping.")
        return 0
    if result.success:
        print(f"✓  Uploaded: https://www.youtube.com/watch?v={result.youtube_id}")
        return 0
    else:
        print(f"ERROR: {result.failure_reason}")
        return 1


def cmd_analytics(args: argparse.Namespace) -> int:
    """Fetch YouTube Analytics for all uploaded videos."""
    from src.analytics.collector import AnalyticsCollector, get_top_performing_topics
    from src.youtube.oauth import credentials_available

    if not credentials_available():
        print(
            "BLOCKER: YouTube OAuth credentials not set — analytics unavailable.\n"
            "Add YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET to .env."
        )
        return 1

    init_db()
    channel_id = getattr(args, "channel_id", "") or os.environ.get("YOUTUBE_CHANNEL_ID", "")
    collector = AnalyticsCollector(channel_id=channel_id)
    print("⟳  Fetching analytics…")
    results = collector.collect_all()
    if not results:
        print("No analytics data returned (videos may be too new).")
        return 0

    for m in results:
        print(
            f"  {m.youtube_id}  views={m.views:,}  "
            f"watch_time={m.watch_time_mins:.0f}min  "
            f"avg_ret={m.avg_view_pct:.1f}%  "
            f"subs+={m.subscribers_won}"
        )

    top = get_top_performing_topics(limit=5)
    if top:
        print("\nTop performing topics by retention:")
        for row in top:
            print(f"  {row['topic'][:60]}  avg_ret={row['avg_ret']:.1f}%  "
                  f"views={row['total_views']:,}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print DB summary."""
    init_db()
    with db_module._connect() as conn:
        footage_total = conn.execute("SELECT COUNT(*) FROM footage_assets").fetchone()[0]
        footage_approved = conn.execute(
            "SELECT COUNT(*) FROM footage_assets WHERE approval_status='APPROVED'"
        ).fetchone()[0]
        renders = conn.execute("SELECT COUNT(*) FROM renders").fetchone()[0]
        renders_qc = conn.execute(
            "SELECT COUNT(*) FROM renders WHERE qc_passed=1"
        ).fetchone()[0]
        uploads = conn.execute(
            "SELECT COUNT(*) FROM videos WHERE youtube_id IS NOT NULL"
        ).fetchone()[0]
        analytic_rows = conn.execute("SELECT COUNT(*) FROM analytics").fetchone()[0]

    print("Beyond The Pitch — Pipeline Status")
    print("────────────────────────────────────")
    print(f"Footage assets:   {footage_total:3d}  ({footage_approved} approved)")
    print(f"Renders:          {renders:3d}  ({renders_qc} passed QC)")
    print(f"YouTube uploads:  {uploads:3d}")
    print(f"Analytics rows:   {analytic_rows:3d}")
    print()

    # Blockers
    creds = {
        "YOUTUBE_API_KEY": os.environ.get("YOUTUBE_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "YOUTUBE_CLIENT_ID": os.environ.get("YOUTUBE_CLIENT_ID", ""),
        "YOUTUBE_CLIENT_SECRET": os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
    }
    print("Credentials:")
    for k, v in creds.items():
        status = "✓ set" if v else "✗ missing"
        print(f"  {k:<30} {status}")

    if footage_approved == 0:
        print(
            "\n⚠  No approved footage — the clip pipeline is blocked.\n"
            "   Import and approve a stock or creator-authorized video to unblock."
        )
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Beyond The Pitch — automated Short production pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # ── clip ──
    p_clip = sub.add_parser("clip", help="Process an approved footage asset into a Short")
    p_clip.add_argument("--source-id", required=True, help="Footage asset UUID")
    p_clip.add_argument("--output", help="Output MP4 path (optional)")
    p_clip.add_argument("--duration", type=float, default=45.0, help="Target clip duration (s)")
    p_clip.add_argument("--transcriber", default="faster_whisper",
                        choices=["faster_whisper", "mock"])

    # ── auto ──
    p_auto = sub.add_parser("auto", help="Automated discovery + clip pipeline")
    p_auto.add_argument("--limit", type=int, default=1, help="Max Shorts to produce")
    p_auto.add_argument("--dry-run", action="store_true")

    # ── produce ──
    p_produce = sub.add_parser("produce", help="Produce a named demo Short")
    p_produce.add_argument("story", choices=["materazzi"], help="Demo story name")
    p_produce.add_argument("--tts", default="macos", choices=["macos", "openai", "mock"])
    p_produce.add_argument("--output", help="Output MP4 path (optional)")

    # ── upload ──
    p_upload = sub.add_parser("upload", help="Upload a finished render to YouTube")
    p_upload.add_argument("--render-id", type=int, help="Render DB id")
    p_upload.add_argument("--local-path", help="Direct path to MP4 file")
    p_upload.add_argument("--visibility", default="private", choices=["private", "public"])
    p_upload.add_argument("--title", help="Override video title")

    # ── analytics ──
    p_analytics = sub.add_parser("analytics", help="Fetch YouTube Analytics")
    p_analytics.add_argument("--channel-id", default="",
                              help="YouTube channel ID (improves analytics accuracy)")

    # ── status ──
    sub.add_parser("status", help="Print pipeline status")

    args = parser.parse_args()

    if args.command == "clip":
        return cmd_clip(args)
    elif args.command == "auto":
        return cmd_auto(args)
    elif args.command == "produce":
        if args.story == "materazzi":
            return cmd_produce_materazzi(args)
        print(f"Unknown story: {args.story}")
        return 1
    elif args.command == "upload":
        return cmd_upload(args)
    elif args.command == "analytics":
        return cmd_analytics(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
