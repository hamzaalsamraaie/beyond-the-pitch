"""
VideoProducer — Phase 3 orchestrator.

Storyboard → TTS synthesis → Frame compositor → FFmpeg assembly → QC → DB record

Guards:
  - Kill switch checked before any work begins
  - Duplicate render detected via storyboard script_hash in DB
  - Human review gate: storyboard must have status='approved' in DB
    (bypass with bypass_review=True for demo/testing only)
  - QC runs after every render; result stored in DB

No YouTube uploading or publishing occurs in Phase 3.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.core.config import get_section
from src.core.database import (
    approve_storyboard,
    get_storyboard_status,
    init_db,
    insert_render,
    insert_storyboard,
    log_production,
    render_hash_exists,
)
from src.core.kill_switch import require_clear
from src.core.logger import configure_logging, get_logger
from src.research.models import Storyboard
from src.video.assets import AssetManifest
from src.video.compositor import VideoCompositor
from src.video.ffmpeg_builder import concatenate_audio, pipe_frames_to_mp4
from src.video.quality_control import QCResult, run_qc
from src.video.tts import BaseTTSProvider, MockTTSProvider, get_tts_provider

logger = get_logger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


@dataclass
class ProductionResult:
    success: bool
    output_path: Path | None
    qc: QCResult | None
    render_id: int | None
    failure_reason: str = ""


class VideoProducer:
    def __init__(
        self,
        tts_provider: BaseTTSProvider | None = None,
        manifest: AssetManifest | None = None,
        bypass_review: bool = False,
        fps: int = 30,
    ) -> None:
        cfg = get_section("production")
        self._tts = tts_provider or get_tts_provider()
        self._manifest = manifest or AssetManifest()
        self._bypass_review = bypass_review
        self._fps = fps
        self._prevent_dupes = cfg.get("prevent_duplicate_renders", True)
        self._require_approval = cfg.get("require_storyboard_approval", True)

    # ── Guard checks ──────────────────────────────────────────────────────────

    def _check_guards(self, storyboard: Storyboard) -> str | None:
        """Return an error string if any guard fails, else None."""
        # 1. Kill switch
        try:
            require_clear("VideoProducer")
        except RuntimeError as exc:
            return str(exc)

        # 2. Duplicate render
        if self._prevent_dupes and render_hash_exists(storyboard.script_hash):
            return (
                f"Duplicate render: storyboard hash {storyboard.script_hash[:16]} "
                "already exists in renders table. "
                "Delete the existing render record to re-render."
            )

        # 3. Human review gate
        if self._require_approval and not self._bypass_review:
            status = get_storyboard_status(storyboard.script_hash)
            if status != "approved":
                return (
                    f"Storyboard status is '{status}' (need 'approved'). "
                    "Approve the storyboard in the DB, or use bypass_review=True for demos."
                )

        return None

    # ── TTS synthesis ─────────────────────────────────────────────────────────

    def _synthesize_audio(
        self, storyboard: Storyboard, audio_dir: Path
    ) -> list[Path]:
        """Return one WAV per scene, in order."""
        audio_paths: list[Path] = []
        for i, scene in enumerate(storyboard.scenes):
            out = audio_dir / f"scene_{i:02d}.wav"
            result = self._tts.synthesize(
                text=scene.narration,
                target_duration_secs=scene.duration,
                output_path=out,
            )
            audio_paths.append(result.audio_path)
        return audio_paths

    # ── Main produce method ───────────────────────────────────────────────────

    def produce(
        self,
        storyboard: Storyboard,
        output_path: Path | None = None,
    ) -> ProductionResult:
        configure_logging()
        init_db()

        # ── Guards ──────────────────────────────────────────────────────────
        error = self._check_guards(storyboard)
        if error:
            logger.warning("producer_guard_failed", reason=error)
            return ProductionResult(
                success=False, output_path=None, qc=None, render_id=None,
                failure_reason=error,
            )

        # ── Output path ──────────────────────────────────────────────────────
        if output_path is None:
            OUTPUT_DIR.mkdir(exist_ok=True)
            slug = storyboard.title[:40].lower()
            slug = "".join(c if c.isalnum() else "_" for c in slug).strip("_")
            output_path = OUTPUT_DIR / f"{slug}.mp4"

        logger.info(
            "producer_start",
            title=storyboard.title[:60],
            scenes=len(storyboard.scenes),
            duration=storyboard.total_duration,
            tts=self._tts.name,
        )

        with tempfile.TemporaryDirectory(prefix="btp_produce_") as tmp:
            tmp_dir = Path(tmp)
            audio_dir = tmp_dir / "audio"
            audio_dir.mkdir()

            # ── Stage 1: TTS synthesis ───────────────────────────────────────
            logger.info("stage_tts_start")
            try:
                scene_audio = self._synthesize_audio(storyboard, audio_dir)
            except Exception as exc:
                return ProductionResult(
                    success=False, output_path=None, qc=None, render_id=None,
                    failure_reason=f"TTS failed: {exc}",
                )

            # ── Stage 2: Audio concatenation ─────────────────────────────────
            combined_audio = tmp_dir / "combined.wav"
            try:
                concatenate_audio(scene_audio, combined_audio)
            except Exception as exc:
                return ProductionResult(
                    success=False, output_path=None, qc=None, render_id=None,
                    failure_reason=f"Audio concat failed: {exc}",
                )

            # ── Stage 3: Frame composition ────────────────────────────────────
            logger.info("stage_compositor_start")
            compositor = VideoCompositor(
                storyboard=storyboard,
                fps=self._fps,
                manifest=self._manifest,
            )
            compositor.prepare()
            total_frames = compositor.total_frames()
            logger.info("compositor_prepared", total_frames=total_frames)

            # ── Stage 4: FFmpeg assembly ──────────────────────────────────────
            logger.info("stage_ffmpeg_start")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                pipe_frames_to_mp4(
                    frame_generator=compositor.generate_frames(),
                    total_frames=total_frames,
                    fps=self._fps,
                    combined_audio_path=combined_audio,
                    output_path=output_path,
                )
            except Exception as exc:
                return ProductionResult(
                    success=False, output_path=None, qc=None, render_id=None,
                    failure_reason=f"FFmpeg assembly failed: {exc}",
                )

        # ── Stage 5: Quality control ──────────────────────────────────────────
        logger.info("stage_qc_start")
        qc = run_qc(
            video_path=output_path,
            expected_duration_secs=storyboard.total_duration,
            tts_provider=self._tts.name,
        )
        logger.info("stage_qc_done", passed=qc.passed, report=qc.report())

        if not qc.passed:
            logger.error("qc_failed", failures=qc.failures)

        # ── Stage 6: Record in DB ─────────────────────────────────────────────
        render_id = insert_render(
            storyboard_hash=storyboard.script_hash,
            local_path=str(output_path),
            duration_secs=qc.measured_duration_secs or storyboard.total_duration,
            file_size_bytes=qc.file_size_bytes,
            width=qc.measured_width,
            height=qc.measured_height,
            tts_provider=self._tts.name,
            qc_passed=qc.passed,
            qc_report=qc.report(),
        )

        logger.info(
            "producer_complete",
            render_id=render_id,
            path=str(output_path),
            qc_passed=qc.passed,
        )

        return ProductionResult(
            success=qc.passed,
            output_path=output_path,
            qc=qc,
            render_id=render_id,
        )
