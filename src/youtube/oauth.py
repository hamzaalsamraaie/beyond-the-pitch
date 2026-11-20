"""
YouTube OAuth 2.0 flow.

On first use, opens a browser for consent, then caches the token to
data/youtube_token.json (chmod 600 enforced at write time).

Subsequent calls refresh the token automatically.

Required env vars (from .env):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET

Scopes:
  youtube.upload   — upload videos
  youtube.readonly — read channel info, check duplicates
  yt-analytics.readonly — fetch video performance metrics
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_TOKEN_PATH = Path(__file__).resolve().parents[2] / "data" / "youtube_token.json"
_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _require_google_auth() -> None:
    """Raise EnvironmentError if google-auth-oauthlib is not installed."""
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError as exc:
        raise EnvironmentError(
            "google-auth-oauthlib or google-api-python-client not installed.\n"
            "Run: pip install google-auth-oauthlib google-api-python-client\n"
            f"Import error: {exc}"
        ) from exc


def _client_config() -> dict:
    """Build the OAuth client config from env vars."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env.\n"
            "BLOCKER: YouTube OAuth upload unavailable without these credentials.\n"
            "To create them: Google Cloud Console → APIs & Services → Credentials → "
            "Create OAuth 2.0 Client ID (Desktop application)."
        )
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }


def _save_token(creds) -> None:
    """Write credentials JSON to _TOKEN_PATH with strict file permissions."""
    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    _TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    logger.info("youtube_token_saved", path=str(_TOKEN_PATH))


def _load_token():
    """Load cached credentials or return None."""
    if not _TOKEN_PATH.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials  # noqa: PLC0415
        data = json.loads(_TOKEN_PATH.read_text())
        creds = Credentials.from_authorized_user_info(data)
        return creds
    except Exception as exc:
        logger.warning("youtube_token_load_failed", error=str(exc))
        return None


def get_credentials():
    """
    Return valid OAuth2 credentials for YouTube API.

    If a cached token exists and is valid (or refreshable), returns it.
    Otherwise runs the browser-based consent flow interactively.

    Raises EnvironmentError if credentials env vars are missing.
    """
    _require_google_auth()

    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

    creds = _load_token()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception as exc:
            logger.warning("youtube_token_refresh_failed", error=str(exc))
            raise EnvironmentError(
                f"YouTube token refresh failed — network unavailable or token revoked. "
                f"Re-run `python scripts/pipeline.py upload --render-id ID` while online "
                f"to trigger a new browser login. ({exc})"
            ) from exc

    # Interactive consent flow (manual/CLI use only — not reachable from automated pipeline)
    config = _client_config()
    flow = InstalledAppFlow.from_client_config(config, scopes=_SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    _save_token(creds)
    return creds


def build_youtube_client(service: str = "youtube", version: str = "v3"):
    """Return an authenticated googleapiclient service resource."""
    _require_google_auth()
    from googleapiclient.discovery import build  # noqa: PLC0415
    creds = get_credentials()
    return build(service, version, credentials=creds)


def build_analytics_client():
    """Return an authenticated youtubeAnalytics v2 client."""
    return build_youtube_client("youtubeAnalytics", "v2")


def credentials_available() -> bool:
    """Return True if OAuth credentials are configured (not necessarily valid)."""
    return bool(
        os.environ.get("YOUTUBE_CLIENT_ID")
        and os.environ.get("YOUTUBE_CLIENT_SECRET")
    )
