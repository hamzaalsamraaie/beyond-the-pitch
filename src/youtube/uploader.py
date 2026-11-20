"""
YouTube video uploader with retry, duplicate prevention, and DB logging.

Upload is always private first (DEFAULT_UPLOAD_VISIBILITY=private).
Public publishing requires a separate explicit call.

Requires OAuth credentials — see src/youtube/oauth.py.

Quota cost: videos.insert costs 1600 units (counts against 10,000/day).
Daily upload cap enforced from .env DAILY_UPLOAD_CAP (default 3).
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path

import src.core.database as db_module
from src.core.logger import get_logger
from src.youtube.oauth import build_youtube_client, credentials_available

logger = get_logger(__name__)

_UPLOAD_QUOTA_COST = 1600   # YouTube Data API v3 cost for videos.insert
_MAX_RETRIES = 3
_RETRY_DELAY_SECS = 10
_CHUNK_SIZE_BYTES = 256 * 1024   # 256 KB resumable upload chunks


@dataclass
class UploadResult:
    success: bool
    youtube_id: str = ""
    failure_reason: str = ""
    is_duplicate: bool = False


@dataclass
class VideoMetadata:
    title: str
    description: str
    tags: list[str]
    category_id: str = "17"            # 17 = Sports
    visibility: str = "private"
    made_for_kids: bool = False
    contains_ai_generated: bool = False  # toggles AI disclosure in Studio
    publish_at: str = ""                 # RFC 3339 UTC — if set, video is scheduled (privacyStatus stays private until then)


# ── Daily upload cap ──────────────────────────────────────────────────────────

def _uploads_today() -> int:
    with db_module._connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM videos
               WHERE DATE(published_at) = DATE('now')
               AND youtube_id IS NOT NULL""",
        ).fetchone()
    return row["cnt"] if row else 0


def _check_daily_cap() -> None:
    cap = int(os.environ.get("DAILY_UPLOAD_CAP", "3"))
    used = _uploads_today()
    if used >= cap:
        raise RuntimeError(
            f"Daily upload cap reached: {used}/{cap} videos uploaded today. "
            "Increase DAILY_UPLOAD_CAP in .env or wait until tomorrow."
        )


# ── Duplicate detection ───────────────────────────────────────────────────────

def video_file_hash(path: Path) -> str:
    """Return SHA-256 hex digest of a video file (stable content identifier)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_duplicate_file_hash(file_hash: str) -> str | None:
    """Return youtube_id if a render with this file hash was already uploaded, else None."""
    if not file_hash:
        return None
    with db_module._connect() as conn:
        try:
            row = conn.execute(
                "SELECT youtube_id FROM renders WHERE file_hash=? AND youtube_id IS NOT NULL",
                (file_hash,),
            ).fetchone()
        except Exception:
            return None
    return row["youtube_id"] if row else None


def _is_duplicate_local_path(local_path: str) -> bool:
    """Return True if a video at this local path is already uploaded.

    Checks both absolute and relative forms of the path so that the DB rows
    created with relative paths and upload calls using absolute paths (or vice
    versa) are still matched correctly.
    """
    p = Path(local_path)
    candidates = [str(p)]
    try:
        candidates.append(str(p.resolve()))  # absolute form
    except Exception:
        pass
    if p.is_absolute():
        try:
            from pathlib import PurePosixPath  # noqa: PLC0415
            # Also try relative form from project root
            rel = str(p.relative_to(db_module.DB_PATH.parents[1]))
            candidates.append(rel)
        except Exception:
            pass

    with db_module._connect() as conn:
        for candidate in candidates:
            row = conn.execute(
                "SELECT youtube_id FROM renders WHERE local_path=? AND youtube_id IS NOT NULL",
                (candidate,),
            ).fetchone()
            if row:
                return True
            row = conn.execute(
                "SELECT youtube_id FROM videos WHERE local_path=? AND youtube_id IS NOT NULL",
                (candidate,),
            ).fetchone()
            if row:
                return True
    return False


# ── Uploader ──────────────────────────────────────────────────────────────────

class YouTubeUploader:
    """
    Uploads a local MP4 to YouTube using the Data API v3.

    Usage:
        uploader = YouTubeUploader()
        result = uploader.upload(video_path, metadata)
        if result.success:
            print(result.youtube_id)
    """

    def __init__(self) -> None:
        if not credentials_available():
            raise EnvironmentError(
                "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are not set.\n"
                "BLOCKER: Set these in .env to enable uploads.\n"
                "Create them at: Google Cloud Console → APIs & Services → Credentials."
            )

    def upload(
        self,
        video_path: Path,
        metadata: VideoMetadata,
        video_db_id: int | None = None,
    ) -> UploadResult:
        """
        Upload video_path to YouTube as a private video.

        Returns UploadResult. Never raises — failures are captured in result.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult(
                success=False,
                failure_reason=f"Video file not found: {video_path}",
            )

        # Duplicate check — file content hash first (most reliable), then path
        try:
            fhash = video_file_hash(video_path)
        except Exception:
            fhash = ""

        prior_youtube_id = _is_duplicate_file_hash(fhash)
        if prior_youtube_id:
            logger.warning("upload_duplicate_by_hash", hash=fhash[:16], prior=prior_youtube_id)
            return UploadResult(success=True, is_duplicate=True, youtube_id=prior_youtube_id)

        if _is_duplicate_local_path(str(video_path)):
            logger.warning("upload_duplicate_skipped", path=str(video_path))
            return UploadResult(success=True, is_duplicate=True, youtube_id="DUPLICATE")

        # Daily cap
        try:
            _check_daily_cap()
        except RuntimeError as exc:
            return UploadResult(success=False, failure_reason=str(exc))

        youtube = build_youtube_client()

        body = {
            "snippet": {
                "title": metadata.title[:100],
                "description": metadata.description[:5000],
                "tags": metadata.tags[:500],
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.visibility,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
            },
        }
        if metadata.contains_ai_generated:
            body["status"]["containsSyntheticMedia"] = True
        if metadata.publish_at:
            # publishAt requires privacyStatus="private" — the video stays private
            # until the scheduled time, then YouTube auto-publishes it.
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = metadata.publish_at
            logger.info("upload_scheduled", publish_at=metadata.publish_at)

        try:
            from googleapiclient.http import MediaFileUpload  # noqa: PLC0415
            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                chunksize=_CHUNK_SIZE_BYTES,
                resumable=True,
            )
        except ImportError as exc:
            return UploadResult(
                success=False,
                failure_reason=f"google-api-python-client not installed: {exc}",
            )

        logger.info(
            "upload_start",
            title=metadata.title[:60],
            visibility=metadata.visibility,
            path=video_path.name,
        )

        youtube_id: str = ""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                request = youtube.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media,
                )

                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        logger.info(
                            "upload_progress",
                            pct=int(status.progress() * 100),
                            attempt=attempt,
                        )

                youtube_id = response["id"]
                youtube_url = f"https://youtu.be/{youtube_id}"
                logger.info("upload_success", youtube_id=youtube_id)
                break  # upload succeeded — exit retry loop immediately

            except Exception as exc:
                logger.warning(
                    "upload_attempt_failed",
                    attempt=attempt, error=str(exc)[:200],
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SECS * attempt)
                else:
                    return UploadResult(
                        success=False,
                        failure_reason=f"Upload failed after {_MAX_RETRIES} attempts: {exc}",
                    )

        if not youtube_id:
            return UploadResult(success=False, failure_reason="Exhausted retries")

        # DB record — in a separate block so failure here does NOT trigger re-upload
        try:
            with db_module._connect() as conn:
                # Ensure file_hash column exists
                try:
                    conn.execute("ALTER TABLE renders ADD COLUMN file_hash TEXT DEFAULT ''")
                except Exception:
                    pass
                if video_db_id:
                    conn.execute(
                        "UPDATE renders SET youtube_id=?, youtube_url=?, "
                        "uploaded_at=datetime('now'), status=?, file_hash=? WHERE id=?",
                        (youtube_id, youtube_url, metadata.visibility, fhash, video_db_id),
                    )
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO videos "
                            "(title, local_path, youtube_id, visibility, "
                            "status, published_at) "
                            "VALUES (?, "
                            "(SELECT local_path FROM renders WHERE id=?), "
                            "?, ?, 'uploaded', datetime('now'))",
                            (metadata.title, video_db_id, youtube_id, metadata.visibility),
                        )
                    except Exception:
                        pass  # videos mirror is best-effort
                try:
                    # Pass None — video_db_id is a renders.id, not videos.id
                    db_module.log_production(
                        conn, None, "youtube_upload", "success", youtube_id
                    )
                except Exception:
                    pass
            db_module.record_api_usage(
                "youtube_data_api", _UPLOAD_QUOTA_COST,
                f"videos.insert {youtube_id}"
            )
        except Exception as exc:
            logger.warning("upload_db_record_failed", error=str(exc)[:200])
            # Upload succeeded — return success even if DB record failed

        return UploadResult(success=True, youtube_id=youtube_id)
