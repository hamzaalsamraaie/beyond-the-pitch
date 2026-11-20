"""
Clip editor: orchestrates reframing → captions → audio → QC into a finished Short.

Pipeline per ClipSpec:
  1. Verify footage gate (APPROVED + commercial_use + monetization_allowed)
  2. Reframe to 1080×1920
  3. Write ASS caption file from transcript words
  4. Burn captions into reframed video
  5. Normalise audio
  6. Optionally mix music bed
  7. Run QC
  8. Record render in DB
  9. Return EditResult

No publishing occurs here. Output is always a local MP4 at private_output_path.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.clipping.audio_mixer import mix_music_bed, normalise_audio
from src.clipping.caption_renderer import burn_captions, write_ass_file
from src.clipping.models import ClipSpec
from src.clipping.reframer import reframe_clip
from src.core.database import init_db, insert_render, log_production
from src.core.logger import get_logger
from src.footage.catalog import FootageCatalog
from src.footage.gate import FootageGate, FootageGateError
from src.video.quality_control import QCResult, run_qc

logger = get_logger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "shorts"


@dataclass
class EditResult:
    success: bool
    output_path: Path | None
    qc: QCResult | None
    render_id: int | None
    failure_reason: str = ""


class ClipEditor:
    """
    Assembles a finished 1080×1920 Short from an approved ClipSpec.

    Parameters
    ----------
    music_path:
        Optional path to a rights-cleared music WAV/MP3 for the bed mix.
        None → no music, commentary only.
    bypass_gate:
        True only for integration tests that use fixture video.
    """

    def __init__(
        self,
        music_path: Path | None = None,
        bypass_gate: bool = False,
    ) -> None:
        self._music_path = music_path
        self._bypass_gate = bypass_gate

    # ── Gate check ────────────────────────────────────────────────────────────

    def _check_gate(self, clip: ClipSpec) -> str | None:
        if self._bypass_gate:
            return None
        catalog = FootageCatalog()
        gate = FootageGate(catalog)
        try:
            gate.check_all([clip.footage_asset_id])
        except FootageGateError as exc:
            return str(exc)
        return None

    # ── Main edit ─────────────────────────────────────────────────────────────

    def edit(
        self,
        clip: ClipSpec,
        output_path: Path | None = None,
        storyboard_hash: str = "",
    ) -> EditResult:
        init_db()

        # 1. Gate
        gate_error = self._check_gate(clip)
        if gate_error:
            logger.error("editor_gate_blocked", reason=gate_error)
            return EditResult(
                success=False, output_path=None, qc=None, render_id=None,
                failure_reason=gate_error,
            )

        # 2. Output path
        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            slug = clip.source_path.stem[:40].lower()
            slug = "".join(c if c.isalnum() else "_" for c in slug).strip("_")
            output_path = OUTPUT_DIR / f"{slug}_short.mp4"

        logger.info(
            "editor_start",
            source=clip.source_path.name,
            duration=round(clip.duration, 1),
            score=round(clip.score, 3),
        )

        with tempfile.TemporaryDirectory(prefix="btp_edit_") as tmp:
            tmp_dir = Path(tmp)

            # 3. Reframe
            reframed = tmp_dir / "reframed.mp4"
            try:
                reframe_clip(clip, reframed)
            except Exception as exc:
                return EditResult(
                    success=False, output_path=None, qc=None, render_id=None,
                    failure_reason=f"Reframe failed: {exc}",
                )

            # 4. Captions
            ass_path = tmp_dir / "captions.ass"
            captioned = tmp_dir / "captioned.mp4"
            try:
                write_ass_file(
                    words=clip.transcript_words,
                    clip_start=clip.start,
                    clip_end=clip.end,
                    output_path=ass_path,
                )
                burn_captions(reframed, ass_path, captioned)
            except Exception as exc:
                # Captions failure: use reframed without captions and log warning
                logger.warning("captions_failed_using_uncaptioned", error=str(exc))
                captioned = reframed

            # 5. Audio normalise
            normalised = tmp_dir / "normalised.mp4"
            try:
                normalise_audio(captioned, normalised)
            except Exception as exc:
                logger.warning("audio_normalise_failed_using_prev", error=str(exc))
                normalised = captioned

            # 6. Music bed (optional)
            mixed = tmp_dir / "mixed.mp4"
            if self._music_path and self._music_path.exists():
                try:
                    mix_music_bed(normalised, self._music_path, mixed)
                except Exception as exc:
                    logger.warning("music_mix_failed_skipping", error=str(exc))
                    mixed = normalised
            else:
                mixed = normalised

            # 7. Copy final file to output location
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(mixed), str(output_path))

        # 8. QC
        qc = run_qc(
            video_path=output_path,
            expected_duration_secs=clip.duration,
            tts_provider="clip_editor",
        )
        logger.info("editor_qc", passed=qc.passed, report=qc.report())

        # 9. Record in DB
        render_id = insert_render(
            storyboard_hash=storyboard_hash or f"clip_{clip.footage_asset_id[:16]}",
            local_path=str(output_path),
            duration_secs=qc.measured_duration_secs or clip.duration,
            file_size_bytes=qc.file_size_bytes,
            width=qc.measured_width,
            height=qc.measured_height,
            tts_provider="clip_editor",
            qc_passed=qc.passed,
            qc_report=qc.report(),
        )

        logger.info(
            "editor_done",
            render_id=render_id,
            output=str(output_path),
            qc_passed=qc.passed,
        )

        return EditResult(
            success=qc.passed,
            output_path=output_path,
            qc=qc,
            render_id=render_id,
        )
