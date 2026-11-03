"""Each WiFi file is committed once, with its row and its run's counter together.
Every commit is a real wait on a USB drive. See PLAN.md W8.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.manifest_db import ManifestDB
from server.storage import BackupEngine

TAKEN_AT = "2026-03-05T10:00:00"


def _engine(dest: Path) -> tuple[BackupEngine, list[str]]:
    db = ManifestDB(dest)
    commits: list[str] = []
    db._conn.set_trace_callback(lambda sql: commits.append(sql) if sql.strip().upper() == "COMMIT" else None)
    return BackupEngine(dest, db), commits


def _committed(dest: Path, sql: str, args=()) -> list:
    """What another connection sees: only what was really committed."""
    conn = sqlite3.connect(dest / ".iphone_backup_index" / "index.sqlite")
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_a_new_file_and_its_counter_are_committed_together_once(tmp_path):
    engine, commits = _engine(tmp_path)
    run_id = engine.db.start_run()
    commits.clear()
    result = engine.process_upload("IMG_1.HEIC", io.BytesIO(b"the photo"), TAKEN_AT, run_id)
    assert result["status"] == "new"
    assert len(commits) == 1
    assert len(_committed(tmp_path, "SELECT 1 FROM backed_up_files WHERE filename = 'IMG_1.HEIC'")) == 1
    assert _committed(tmp_path, "SELECT files_new FROM runs WHERE id = ?", (run_id,)) == [(1,)]


def test_a_duplicate_under_another_name_is_committed_once(tmp_path):
    engine, commits = _engine(tmp_path)
    run_id = engine.db.start_run()
    engine.process_upload("IMG_1.HEIC", io.BytesIO(b"the photo"), TAKEN_AT, run_id)
    commits.clear()
    result = engine.process_upload("abc-uuid.heic", io.BytesIO(b"the photo"), TAKEN_AT, run_id)
    assert result["status"] == "skipped_duplicate"
    assert len(commits) == 1
    # The alias that stops /check asking for this name, and the counter, both landed.
    assert engine.check_exists("abc-uuid.heic", TAKEN_AT) is True
    assert _committed(tmp_path, "SELECT files_skipped FROM runs WHERE id = ?", (run_id,)) == [(1,)]


def test_a_retry_that_clears_an_error_is_still_one_commit(tmp_path):
    engine, commits = _engine(tmp_path)
    run_id = engine.db.start_run()
    try:
        engine.process_upload("IMG_2.MOV", io.BytesIO(b""), TAKEN_AT, run_id)
    except ValueError:
        pass
    commits.clear()
    engine.process_upload("IMG_2.MOV", io.BytesIO(b"a video, really"), TAKEN_AT, run_id)
    assert len(commits) == 1
    assert _committed(tmp_path, "SELECT files_new, files_error FROM runs WHERE id = ?", (run_id,)) == [(1, 0)]


def test_a_caller_that_batches_gets_no_commit(tmp_path):
    """The cable import passes commit=False and commits every so many files itself."""
    engine, commits = _engine(tmp_path)
    staging, sha, size = engine.stage_bytes(io.BytesIO(b"by cable"))
    commits.clear()
    engine.finalize_upload("IMG_3.HEIC", staging, sha, size, TAKEN_AT, None, commit=False)
    assert commits == []
    engine.db.commit()
    assert len(_committed(tmp_path, "SELECT 1 FROM backed_up_files WHERE filename = 'IMG_3.HEIC'")) == 1
