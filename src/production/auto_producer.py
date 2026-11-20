"""
AutoProducer: connects storyboard → footage → render → QC → upload.

Each call to produce_one() runs the full pipeline for a single Storyboard:
  1. Find an approved footage asset (prefers video over crowd-only assets)
  2. Select caption preset and beat-snap story beats
  3. Render animated captions via PIL frame-pipe
  4. LUFS normalise audio
  5. Optionally embed CC0 music bed
  6. Generate thumbnail
  7. Run QC
  8. Record render in DB
  9. Upload as private (unless auto_publish=True and all safety gates pass)
  10. Update DB with YouTube ID

Disk management: all large intermediates are written to output/shorts/_work/
and deleted immediately after the next step succeeds. The final MP4 is kept
in output/shorts/{slug}_{timestamp}.mp4. Old renders beyond keep_last=10 are
pruned automatically.

HARD LIMITS:
- Never publishes broadcast match footage (Content ID registered)
- Never publishes unverified factual claims
- Never publishes if QC fails
- Kill switch (config/kill_switch.flag) halts all activity immediately
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import src.core.database as db_module
from src.core.disk_monitor import check_minimum_space, disk_status_report, estimate_render_mb
from src.core.kill_switch import require_clear
from src.core.logger import get_logger
from src.editing.beat_detector import detect_beats
from src.editing.cc0_music import embed_cc0_music
from src.editing.effects import apply_effects, select_effects_config
from src.editing.music_library import get_track as get_music_track, is_placeholder
from src.editing.renderer import render_video_with_captions
from src.editing.style_selector import assign_story_beats_to_beats, select_caption_preset
from src.footage.catalog import FootageCatalog
from src.footage.models import ApprovalStatus
from src.planning.metadata_generator import AttributionEntry, generate_from_storyboard  # noqa: F401
from src.research.models import Storyboard
from src.video.quality_control import run_qc
from src.video.thumbnail import generate_thumbnail
from src.youtube.uploader import UploadResult, VideoMetadata, YouTubeUploader

logger = get_logger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "shorts"
WORK_DIR = OUTPUT_DIR / "_work"
_KEEP_LAST_RENDERS = 10


@dataclass
class ProduceResult:
    success: bool
    output_path: Path | None = None
    thumbnail_path: Path | None = None
    render_id: int | None = None
    youtube_id: str = ""
    youtube_url: str = ""
    failure_reason: str = ""
    stages_completed: list[str] = field(default_factory=list)


def _slug(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:40].strip("_")


def _prune_old_renders(keep: int = _KEEP_LAST_RENDERS) -> None:
    """Delete the oldest render MP4s beyond the keep limit."""
    mp4s = sorted(OUTPUT_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    for old in mp4s[:-keep]:
        try:
            old.unlink()
            logger.info("pruned_old_render", path=old.name)
        except Exception:
            pass


def _storyboard_to_story_beats(storyboard: Storyboard) -> list[tuple[float, float, str]]:
    """Convert storyboard scenes to (start, end, text) tuples."""
    beats = []
    for scene in storyboard.scenes:
        text = scene.on_screen_text or scene.narration[:50]
        beats.append((scene.start_time, scene.end_time, text))
    return beats


def _normalise_in_place(path: Path) -> None:
    tmp = path.with_suffix(".norm_tmp.mp4")
    ff = shutil.which("ffmpeg")
    result = subprocess.run(
        [ff, "-y", "-i", str(path),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         str(tmp)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"loudnorm failed: {result.stderr[-300:]}")
    path.unlink()
    tmp.rename(path)


class AutoProducer:
    """
    Fully automated Short producer.

    Parameters
    ----------
    auto_publish:
        When True, automatically publishes to YouTube after QC passes.
        Default False — always upload as private first for review.
    dry_run:
        When True, skip the render and upload steps (for testing the pipeline).
    """

    def __init__(
        self,
        auto_publish: bool = False,
        dry_run: bool = False,
        publish_at: str = "",
    ) -> None:
        self._auto_publish = auto_publish
        self._dry_run = dry_run
        self._publish_at = publish_at  # RFC 3339 UTC — schedules YouTube publication

    def _find_approved_footage(self) -> str | None:
        """Return the absolute local_path of an approved, downloadable footage asset."""
        catalog = FootageCatalog()
        assets = catalog.list_assets(status=ApprovalStatus.APPROVED)
        # Prefer assets that have a local file and commercial_use=True
        project_root = Path(__file__).resolve().parents[2]
        for asset in assets:
            if not (asset.local_path and asset.commercial_use and asset.monetization_allowed):
                continue
            p = Path(asset.local_path)
            if not p.is_absolute():
                p = project_root / p
            if p.exists():
                return str(p)
        return None

    def produce_one(self, storyboard: Storyboard) -> ProduceResult:
        """
        Run the full pipeline for one storyboard. Returns ProduceResult.
        Never raises — all failures are captured in ProduceResult.
        """
        result = ProduceResult(success=False)
        slug = _slug(storyboard.title)
        timestamp = datetime.now(tz=None).strftime("%Y%m%d_%H%M%S")
        final_name = f"{slug}_{timestamp}.mp4"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        WORK_DIR.mkdir(parents=True, exist_ok=True)

        final_path = OUTPUT_DIR / final_name
        vid_work = WORK_DIR / f"{slug}_{timestamp}_work.mp4"

        try:
            require_clear("AutoProducer.produce_one")

            # ── 0. Disk space check ───────────────────────────────────────
            required_mb = estimate_render_mb(storyboard.total_duration)
            check_minimum_space(required_mb)
            logger.debug("disk_check_passed", status=disk_status_report())

            # ── 1. Find footage ───────────────────────────────────────────
            footage_path = self._find_approved_footage()
            if not footage_path:
                result.failure_reason = (
                    "No approved footage asset available. "
                    "Import and approve footage with: "
                    "python scripts/footage_catalog.py approve --id UUID"
                )
                logger.error("auto_produce_no_footage", storyboard=storyboard.title[:60])
                return result
            result.stages_completed.append("footage_found")

            if self._dry_run:
                result.success = True
                result.failure_reason = "dry_run — render skipped"
                result.stages_completed.append("dry_run")
                return result

            # ── 2. Select caption preset ──────────────────────────────────
            story_type = storyboard.content_type or "football_moments"
            preset = select_caption_preset(
                story_type=story_type,
                mood="dramatic",
                has_speech=False,
                duration_secs=storyboard.total_duration,
            )
            result.stages_completed.append("preset_selected")

            # ── 3. Beat detection ─────────────────────────────────────────
            story_beats = _storyboard_to_story_beats(storyboard)
            try:
                beats, bpm = detect_beats(Path(footage_path))
                snapped = assign_story_beats_to_beats(story_beats, beats, snap_window=0.15)
            except Exception:
                snapped = story_beats
                bpm = 100.0
            result.stages_completed.append("beats_detected")

            # ── 4. Render animated captions ───────────────────────────────
            render_video_with_captions(
                video_path=Path(footage_path),
                story_beats=snapped,
                output_path=vid_work,
                preset=preset,
            )
            result.stages_completed.append("captions_rendered")

            # ── 5. LUFS normalise ─────────────────────────────────────────
            _normalise_in_place(vid_work)
            result.stages_completed.append("audio_normalised")

            # ── 5b. Video effects (zoom / color-grade / vignette) ─────────
            effects_cfg = select_effects_config(story_type, mood="dramatic")
            effects_out = vid_work.with_suffix(".fx.mp4")
            try:
                if apply_effects(vid_work, effects_out, effects_cfg,
                                 duration_secs=storyboard.total_duration, crf=28):
                    vid_work.unlink()
                    effects_out.rename(vid_work)
                    result.stages_completed.append("effects_applied")
                else:
                    effects_out.unlink(missing_ok=True)
                    logger.warning("effects_skipped", reason="apply_effects returned False")
            except Exception as exc:
                effects_out.unlink(missing_ok=True)
                logger.warning("effects_error", error=str(exc)[:200])

            # ── 6. Optionally embed licensed music bed ─────────────────────
            music_track = get_music_track(story_type, bpm_hint=bpm)
            if music_track:
                if is_placeholder(music_track):
                    logger.warning(
                        "music_placeholder_in_use",
                        filename=music_track.filename,
                        note="Replace with real CC0/licensed track before public launch",
                    )
                music_out = vid_work.with_suffix(".music.mp4")
                ok = embed_cc0_music(vid_work, music_track, music_out)  # type: ignore[arg-type]
                if ok:
                    vid_work.unlink()
                    music_out.rename(vid_work)
                    result.stages_completed.append("music_embedded")

            # Move to final destination
            shutil.move(str(vid_work), str(final_path))

            # ── 7. Generate thumbnail ─────────────────────────────────────
            thumb_path = final_path.with_suffix(".jpg")
            generate_thumbnail(
                video_path=final_path,
                title=storyboard.title,
                output_path=thumb_path,
            )
            result.thumbnail_path = thumb_path
            result.stages_completed.append("thumbnail_generated")

            # ── 7b. Factual source verification ───────────────────────────
            _verify_scene_sources(storyboard)
            result.stages_completed.append("sources_verified")

            # ── 8. QC ─────────────────────────────────────────────────────
            qc = run_qc(
                final_path,
                expected_duration_secs=storyboard.total_duration,
                tts_provider="none",
            )
            if not qc.passed:
                result.failure_reason = f"QC failed: {qc.report()}"
                logger.error("auto_produce_qc_failed", report=qc.report())
                return result
            result.stages_completed.append("qc_passed")

            # ── 9. Record in DB ───────────────────────────────────────────
            stat = final_path.stat()
            from src.youtube.uploader import video_file_hash  # noqa: PLC0415
            fhash = video_file_hash(final_path)
            render_id = db_module.insert_render(
                storyboard_hash=storyboard.script_hash,
                local_path=str(final_path),
                duration_secs=storyboard.total_duration,
                file_size_bytes=stat.st_size,
                width=1080,
                height=1920,
                tts_provider="none",
                qc_passed=True,
                qc_report=qc.report(),
                status="pending_review",
                file_hash=fhash,
            )
            result.render_id = render_id
            result.output_path = final_path
            result.stages_completed.append("db_recorded")

            # ── 10. Upload ────────────────────────────────────────────────
            try:
                metadata = _build_metadata(storyboard, publish_at=self._publish_at)
                uploader = YouTubeUploader()
                upload_result = uploader.upload(final_path, metadata, video_db_id=render_id)

                if upload_result.success and not upload_result.is_duplicate:
                    result.youtube_id = upload_result.youtube_id
                    result.youtube_url = f"https://youtu.be/{upload_result.youtube_id}"
                    result.stages_completed.append("uploaded_private")
                    logger.info(
                        "auto_produce_uploaded",
                        youtube_id=upload_result.youtube_id,
                        title=storyboard.title[:60],
                    )

                    if self._auto_publish:
                        _publish_public(upload_result.youtube_id)
                        result.stages_completed.append("published_public")

                elif upload_result.is_duplicate:
                    result.youtube_id = upload_result.youtube_id
                    result.stages_completed.append("upload_duplicate")
                else:
                    logger.warning(
                        "auto_produce_upload_failed",
                        reason=upload_result.failure_reason[:200],
                    )
            except EnvironmentError:
                # No YouTube credentials — that's OK, video is still produced
                logger.info("auto_produce_no_youtube_credentials")
                result.stages_completed.append("upload_skipped_no_credentials")

            result.success = True
            _prune_old_renders()
            return result

        except Exception as exc:
            result.failure_reason = str(exc)[:400]
            logger.error("auto_produce_failed", error=result.failure_reason)
            return result
        finally:
            # Always clean up work dir
            if vid_work.exists():
                vid_work.unlink(missing_ok=True)
            work_music = vid_work.with_suffix(".music.mp4")
            if work_music.exists():
                work_music.unlink(missing_ok=True)
            try:
                shutil.rmtree(WORK_DIR, ignore_errors=True)
            except Exception:
                pass


def _verify_scene_sources(storyboard: Storyboard) -> None:
    """
    Raise ValueError if any scene makes a factual claim with no source index.

    Scenes whose narration is 10 words or fewer (titles/labels) are exempt.
    Scenes with at least one valid source_index are verified.
    """
    n_items = len(storyboard.research_items)
    for i, scene in enumerate(storyboard.scenes):
        # Short display-text scenes (labels, titles) are exempt
        word_count = len((scene.narration or "").split())
        if word_count <= 10:
            continue
        # Check source indices exist and are in range
        valid_sources = [idx for idx in scene.source_indices if 0 <= idx < n_items]
        if not valid_sources:
            raise ValueError(
                f"Scene {i} ('{(scene.narration or '')[:60]}') makes a factual claim "
                f"but has no valid source_indices. Add Wikipedia or verified source "
                f"references to research_items and reference them via source_indices."
            )


def _build_metadata(storyboard: Storyboard, publish_at: str = "") -> VideoMetadata:
    # Collect unique attribution entries from research items
    seen_urls: set[str] = set()
    attribution_entries: list[AttributionEntry] = []
    for item in storyboard.research_items:
        url = item.source.url
        if url not in seen_urls:
            seen_urls.add(url)
            attribution_entries.append(
                AttributionEntry(
                    asset_description=item.source.title[:60],
                    creator_name=item.source.publisher,
                    license_type="",
                    source_url=url,
                )
            )

    meta = generate_from_storyboard(
        storyboard_title=storyboard.title,
        proposed_titles=storyboard.proposed_titles or [],
        hook=storyboard.hook or "",
        hashtags=storyboard.hashtags or [],
        attributions=attribution_entries,
        contains_ai=False,
        visibility="private",
    )
    if publish_at:
        meta.publish_at = publish_at
    return meta


def _publish_public(youtube_id: str) -> None:
    from src.youtube.oauth import build_youtube_client
    yt = build_youtube_client()
    yt.videos().update(
        part="status",
        body={
            "id": youtube_id,
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        },
    ).execute()
    logger.info("published_public", youtube_id=youtube_id)
