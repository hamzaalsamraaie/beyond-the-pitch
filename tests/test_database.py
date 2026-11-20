import os
import tempfile
from pathlib import Path
import pytest

# Point the DB at a temp file so tests never touch the real database.
_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("_TEST_DB_OVERRIDE", _tmp)

import src.core.database as db_module

db_module.DB_PATH = Path(_tmp)


def setup_module():
    db_module.init_db()


def teardown_module():
    Path(_tmp).unlink(missing_ok=True)


def test_init_creates_tables():
    import sqlite3
    conn = sqlite3.connect(_tmp)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"videos", "ideas", "production_log", "analytics"}.issubset(tables)


def test_insert_and_retrieve_video():
    vid_id = db_module.insert_video(
        title="Test Short",
        topic="test",
        script_hash="abc123",
        local_path="/tmp/test.mp4",
        duration_secs=30.0,
    )
    assert isinstance(vid_id, int)
    row = db_module.get_video(vid_id)
    assert row["title"] == "Test Short"
    assert row["status"] == "pending"


def test_duplicate_script_hash_detected():
    db_module.insert_video(
        title="Dupe Short",
        topic="test",
        script_hash="unique_hash_xyz",
        local_path="/tmp/dupe.mp4",
        duration_secs=25.0,
    )
    assert db_module.script_hash_exists("unique_hash_xyz")
    assert not db_module.script_hash_exists("nonexistent_hash")
