"""
SQLite database: initialise schema and provide helpers for video tracking.
All writes are transactional; duplicates are detected before upload.
"""

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "football_shorts.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                topic           TEXT,
                script_hash     TEXT UNIQUE,       -- prevents duplicate scripts
                local_path      TEXT,
                youtube_id      TEXT UNIQUE,
                visibility      TEXT DEFAULT 'private',
                duration_secs   REAL,
                status          TEXT DEFAULT 'pending',
                created_at      TEXT DEFAULT (datetime('now')),
                published_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS ideas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                score           REAL,
                used            INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS production_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id        INTEGER REFERENCES videos(id),
                stage           TEXT NOT NULL,
                outcome         TEXT NOT NULL,  -- success | failure
                detail          TEXT,
                logged_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analytics (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id        INTEGER REFERENCES videos(id),
                fetched_at      TEXT DEFAULT (datetime('now')),
                views           INTEGER,
                watch_time_mins REAL,
                subscribers_won INTEGER,
                avg_view_pct    REAL
            );

            -- Phase 2: storyboards and topic deduplication ------------------

            CREATE TABLE IF NOT EXISTS storyboards (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                content_type    TEXT NOT NULL,
                script_hash     TEXT UNIQUE,
                storyboard_json TEXT NOT NULL,
                total_score     REAL,
                generated_by    TEXT,
                status          TEXT DEFAULT 'pending_review',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS topic_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT NOT NULL,
                content_type    TEXT,
                used_at         TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS api_usage (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                provider        TEXT NOT NULL,
                tokens_used     INTEGER DEFAULT 0,
                request_date    TEXT DEFAULT (date('now')),
                detail          TEXT
            );

            -- Phase 4: trend discovery and planning ----------------------

            CREATE TABLE IF NOT EXISTS video_ideas (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                title               TEXT NOT NULL,
                hook                TEXT,
                concept_summary     TEXT,
                content_type        TEXT,
                trend_strength      REAL,
                originality         REAL,
                production_feasibility REAL,
                licensing_feasibility  REAL,
                audience_interest   REAL,
                hook_quality        REAL,
                total_score         REAL,
                production_status   TEXT DEFAULT 'blocked',
                blocking_reason     TEXT,
                target_duration_secs INTEGER,
                created_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS production_plans (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id             INTEGER REFERENCES video_ideas(id),
                full_script         TEXT,
                total_duration_secs REAL,
                production_status   TEXT DEFAULT 'blocked',
                blocked_shots_json  TEXT,
                notes               TEXT,
                plan_json           TEXT,
                created_at          TEXT DEFAULT (datetime('now'))
            );

            -- Phase 5: footage catalog -----------------------------------

            CREATE TABLE IF NOT EXISTS footage_assets (
                id                   TEXT PRIMARY KEY,
                asset_tier           TEXT NOT NULL,
                source_url           TEXT NOT NULL,
                license_type         TEXT NOT NULL DEFAULT 'UNKNOWN',
                license_url          TEXT,
                permission_evidence  TEXT,
                commercial_use       INTEGER NOT NULL DEFAULT 0,
                monetization_allowed INTEGER NOT NULL DEFAULT 0,
                attribution_required INTEGER NOT NULL DEFAULT 0,
                attribution_text     TEXT,
                modifications_allowed INTEGER NOT NULL DEFAULT 1,
                expiry_date          TEXT,
                approval_status      TEXT NOT NULL DEFAULT 'NOT_APPROVED',
                approval_reason      TEXT,
                content_id_risk      TEXT NOT NULL DEFAULT 'UNKNOWN',
                creator_name         TEXT,
                creator_url          TEXT,
                local_path           TEXT,
                file_hash            TEXT,
                duration_secs        REAL,
                resolution           TEXT,
                description          TEXT,
                tags                 TEXT,
                notes                TEXT,
                created_at           TEXT DEFAULT (datetime('now')),
                updated_at           TEXT DEFAULT (datetime('now'))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_footage_source_url
                ON footage_assets(source_url);

            CREATE INDEX IF NOT EXISTS idx_footage_file_hash
                ON footage_assets(file_hash)
                WHERE file_hash IS NOT NULL AND file_hash != '';

            CREATE INDEX IF NOT EXISTS idx_footage_approval
                ON footage_assets(approval_status);

            CREATE TABLE IF NOT EXISTS permission_requests (
                id                   TEXT PRIMARY KEY,
                creator_name         TEXT NOT NULL,
                creator_url          TEXT NOT NULL,
                channel_id           TEXT,
                request_method       TEXT NOT NULL DEFAULT 'email',
                request_sent_at      TEXT,
                response_received_at TEXT,
                response_status      TEXT NOT NULL DEFAULT 'pending',
                permission_scope     TEXT,
                evidence_text        TEXT,
                footage_asset_ids    TEXT,
                created_at           TEXT DEFAULT (datetime('now'))
            );

            -- Phase 3: rendered videos -----------------------------------

            CREATE TABLE IF NOT EXISTS renders (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                storyboard_hash     TEXT NOT NULL,
                local_path          TEXT NOT NULL,
                duration_secs       REAL,
                file_size_bytes     INTEGER,
                width               INTEGER,
                height              INTEGER,
                tts_provider        TEXT,
                qc_passed           INTEGER DEFAULT 0,
                qc_report           TEXT,
                status              TEXT DEFAULT 'pending_review',
                created_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS stories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                headline        TEXT NOT NULL,
                source_url      TEXT,
                source_name     TEXT,
                story_type      TEXT,
                priority_score  REAL DEFAULT 0.0,
                used            INTEGER DEFAULT 0,
                discovered_at   TEXT DEFAULT (datetime('now'))
            );
        """)
        # Non-destructive migrations for existing DBs
        for col_def in [
            "ALTER TABLE renders ADD COLUMN youtube_id TEXT",
            "ALTER TABLE renders ADD COLUMN youtube_url TEXT",
            "ALTER TABLE renders ADD COLUMN uploaded_at TEXT",
            "ALTER TABLE renders ADD COLUMN story_id INTEGER REFERENCES stories(id)",
            "ALTER TABLE renders ADD COLUMN music_track TEXT",
            "ALTER TABLE renders ADD COLUMN thumbnail_path TEXT",
        ]:
            try:
                conn.execute(col_def)
            except Exception:
                pass  # column already exists


def log_production(
    conn: sqlite3.Connection,
    video_id: Optional[int],
    stage: str,
    outcome: str,
    detail: str = "",
) -> None:
    conn.execute(
        "INSERT INTO production_log (video_id, stage, outcome, detail) VALUES (?,?,?,?)",
        (video_id, stage, outcome, detail),
    )


def script_hash_exists(script_hash: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM videos WHERE script_hash = ?", (script_hash,)
        ).fetchone()
    return row is not None


def insert_video(
    title: str,
    topic: str,
    script_hash: str,
    local_path: str,
    duration_secs: float,
    status: str = "pending",
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO videos (title, topic, script_hash, local_path, duration_secs, status)
               VALUES (?,?,?,?,?,?)""",
            (title, topic, script_hash, local_path, duration_secs, status),
        )
        video_id = cur.lastrowid
        log_production(conn, video_id, "insert", "success", local_path)
    return video_id


def get_video(video_id: int) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()


# ── Phase 2: storyboard helpers ───────────────────────────────────────────────

def insert_storyboard(
    topic: str,
    content_type: str,
    script_hash: str,
    storyboard_json: str,
    total_score: float,
    generated_by: str,
    status: str = "pending_review",
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO storyboards
               (topic, content_type, script_hash, storyboard_json, total_score, generated_by, status)
               VALUES (?,?,?,?,?,?,?)""",
            (topic, content_type, script_hash, storyboard_json, total_score, generated_by, status),
        )
        sb_id = cur.lastrowid
        log_production(conn, None, "storyboard_insert", "success", topic)
    return sb_id


def storyboard_hash_exists(script_hash: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM storyboards WHERE script_hash = ?", (script_hash,)
        ).fetchone()
    return row is not None


def record_topic_used(topic: str, content_type: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO topic_history (topic, content_type) VALUES (?,?)",
            (topic, content_type),
        )


def get_recent_topics(days: int = 90) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """SELECT topic, content_type, used_at FROM topic_history
               WHERE used_at >= datetime('now', ? || ' days')
               ORDER BY used_at DESC""",
            (f"-{days}",),
        ).fetchall()


def count_api_requests_today(provider: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM api_usage
               WHERE provider = ? AND request_date = date('now')""",
            (provider,),
        ).fetchone()
    return row["cnt"] if row else 0


def record_api_usage(provider: str, tokens_used: int, detail: str = "") -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO api_usage (provider, tokens_used, detail) VALUES (?,?,?)",
            (provider, tokens_used, detail),
        )


# ── Phase 3: render helpers ───────────────────────────────────────────────────

def render_hash_exists(storyboard_hash: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM renders WHERE storyboard_hash = ?", (storyboard_hash,)
        ).fetchone()
    return row is not None


def insert_render(
    storyboard_hash: str,
    local_path: str,
    duration_secs: float,
    file_size_bytes: int,
    width: int,
    height: int,
    tts_provider: str,
    qc_passed: bool,
    qc_report: str,
    status: str = "pending_review",
    file_hash: str = "",
) -> int:
    with _connect() as conn:
        # Ensure file_hash column exists (added after initial schema)
        try:
            conn.execute("ALTER TABLE renders ADD COLUMN file_hash TEXT DEFAULT ''")
        except Exception:
            pass  # already exists
        cur = conn.execute(
            """INSERT INTO renders
               (storyboard_hash, local_path, duration_secs, file_size_bytes,
                width, height, tts_provider, qc_passed, qc_report, status, file_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                storyboard_hash, local_path, duration_secs, file_size_bytes,
                width, height, tts_provider, int(qc_passed), qc_report, status,
                file_hash,
            ),
        )
        render_id = cur.lastrowid
        log_production(conn, None, "render_insert", "success", local_path)
    return render_id


def get_storyboard_status(script_hash: str) -> Optional[str]:
    """Return the status field of a storyboard by its script_hash, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM storyboards WHERE script_hash = ?", (script_hash,)
        ).fetchone()
    return row["status"] if row else None


def approve_storyboard(script_hash: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE storyboards SET status = 'approved' WHERE script_hash = ?",
            (script_hash,),
        )
