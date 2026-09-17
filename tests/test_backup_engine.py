"""Unit tests for the core backup engine — the rules that matter most:
no-op on identical duplicate, keep-both on name collision with different
content, one-directional writes, and index persistence.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.manifest_db import ManifestDB
from server.storage import BackupEngine


def make_engine(tmp_path: Path) -> BackupEngine:
    dest = tmp_path / "dest"
    dest.mkdir()
    db = ManifestDB(dest)
    return BackupEngine(dest, db)


def test_new_file_is_copied(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.process_upload(
        "IMG_0001.HEIC", io.BytesIO(b"hello world"), "2026-01-15T10:00:00", None
    )
    assert result["status"] == "new"
    dest_path = Path(result["dest_path"])
    assert dest_path.exists()
    assert dest_path.parent.name == "01"
    assert dest_path.parent.parent.name == "2026"
    assert dest_path.read_bytes() == b"hello world"


def test_identical_file_is_skipped_not_duplicated(tmp_path):
    engine = make_engine(tmp_path)
    engine.process_upload("IMG_0002.HEIC", io.BytesIO(b"same content"), "2026-02-01T00:00:00", None)
    result = engine.process_upload(
        "IMG_0002.HEIC", io.BytesIO(b"same content"), "2026-02-01T00:00:00", None
    )
    assert result["status"] == "skipped_duplicate"
    # Only one file should exist in that folder — no duplicate written.
    files = list((Path(engine.dest_root) / "2026" / "02").glob("IMG_0002*"))
    assert len(files) == 1


def test_same_name_different_content_keeps_both(tmp_path):
    engine = make_engine(tmp_path)
    first = engine.process_upload(
        "IMG_0003.HEIC", io.BytesIO(b"version A"), "2026-03-01T00:00:00", None
    )
    second = engine.process_upload(
        "IMG_0003.HEIC", io.BytesIO(b"version B - different!"), "2026-03-01T00:00:00", None
    )
    assert first["status"] == "new"
    assert second["status"] == "conflict_kept_both"
    assert Path(first["dest_path"]).exists()
    assert Path(second["dest_path"]).exists()
    assert first["dest_path"] != second["dest_path"]
    # The original file must be untouched (never overwritten).
    assert Path(first["dest_path"]).read_bytes() == b"version A"
    assert Path(second["dest_path"]).read_bytes() == b"version B - different!"


def test_missing_taken_at_falls_back_to_now(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.process_upload("IMG_0004.MOV", io.BytesIO(b"video bytes"), None, None)
    assert result["status"] == "new"
    assert Path(result["dest_path"]).exists()


def test_index_survives_reopening_same_destination(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    db1 = ManifestDB(dest)
    engine1 = BackupEngine(dest, db1)
    engine1.process_upload("IMG_0005.HEIC", io.BytesIO(b"persisted"), "2026-04-01T00:00:00", None)
    db1.close()

    # Re-open the same destination (simulating reconnecting the same USB drive).
    db2 = ManifestDB(dest)
    engine2 = BackupEngine(dest, db2)
    result = engine2.process_upload(
        "IMG_0005.HEIC", io.BytesIO(b"persisted"), "2026-04-01T00:00:00", None
    )
    assert result["status"] == "skipped_duplicate"


def test_check_exists_reflects_actual_destination_contents(tmp_path):
    """This is the property the user specifically asked for: the check must
    be grounded in what's ACTUALLY in the current destination, not in any
    marker kept on the phone — so pointing at a fresh/different folder
    naturally reports everything as missing again. (No size_bytes param —
    iOS Shortcuts can't reliably hand over a raw byte count, see
    check_exists' docstring — /upload's hash check is the real authority.)"""
    engine = make_engine(tmp_path)
    assert engine.check_exists("IMG_0006.HEIC", "2026-07-01T00:00:00") is False

    engine.process_upload("IMG_0006.HEIC", io.BytesIO(b"hello"), "2026-07-01T00:00:00", None)
    assert engine.check_exists("IMG_0006.HEIC", "2026-07-01T00:00:00") is True

    # A brand new destination (e.g. a different USB drive) has none of this.
    other_root = tmp_path / "other-drive"
    other_root.mkdir()
    other_engine = make_engine(other_root)
    assert other_engine.check_exists("IMG_0006.HEIC", "2026-07-01T00:00:00") is False


def test_run_tracking_counts_new_skipped_and_conflict(tmp_path):
    engine = make_engine(tmp_path)
    run_id = engine.db.start_run()

    engine.process_upload("A.jpg", io.BytesIO(b"1"), "2026-05-01T00:00:00", run_id)  # new
    engine.process_upload("A.jpg", io.BytesIO(b"1"), "2026-05-01T00:00:00", run_id)  # skipped
    engine.process_upload("A.jpg", io.BytesIO(b"2"), "2026-05-01T00:00:00", run_id)  # conflict

    summary = engine.db.finish_run(run_id)
    assert summary["files_new"] == 1
    assert summary["files_skipped"] == 1
    assert summary["files_conflict"] == 1

    status = engine.db.get_status()
    assert status["state"] == "idle"
    assert status["total_files_backed_up"] == 2  # new + conflict, not the skipped one


def test_reopening_reaps_a_run_left_running_by_a_previous_process(tmp_path):
    """A run's finished_at can only be set by /run/finish from the SAME
    process that started it (RunID never survives past one Shortcut
    execution) — so a run still "running" when the app closes/crashes is
    permanently orphaned. Re-opening the DB (simulating the app being
    reopened) must close it out, otherwise get_status() reports "running"
    forever and falsely trips the GUI's idle-backup notice on every future
    launch, even with zero real activity that session."""
    dest = tmp_path / "dest"
    dest.mkdir()
    db1 = ManifestDB(dest)
    run_id = db1.start_run()
    db1.close()  # simulate the app closing mid-run, /run/finish never called

    db2 = ManifestDB(dest)  # simulate the app being reopened later
    assert db2.get_status()["state"] == "idle"
    assert db2.get_status()["last_run"]["id"] == run_id
    assert db2.get_status()["last_run"]["finished_at"] is not None
