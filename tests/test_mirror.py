"""Tests for the optional second-copy (mirror) sync engine.

Same style as test_backup_engine.py: real files under tmp_path, no
device or FastAPI needed — server/mirror.py has no HTTP dependency at
all, by design (see its module docstring).

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.manifest_db import ManifestDB
from server.mirror import get_mirror_status, sync_mirror
from server.storage import BackupEngine


def make_engine(tmp_path: Path, name: str = "primary") -> BackupEngine:
    dest = tmp_path / name
    dest.mkdir()
    return BackupEngine(dest, ManifestDB(dest))


def test_first_sync_copies_everything_newest_first(tmp_path):
    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"older"), "2026-01-01T00:00:00", None)
    engine.process_upload("B.jpg", io.BytesIO(b"newest"), "2026-06-01T00:00:00", None)
    engine.process_upload("C.jpg", io.BytesIO(b"middle"), "2026-03-01T00:00:00", None)

    mirror_root = tmp_path / "mirror"
    seen_order = []
    result = sync_mirror(
        engine.dest_root, engine.db, mirror_root,
        progress_callback=lambda done, total, failed: seen_order.append(done),
    )

    assert result.copied == 3
    assert result.pending_before == 3
    assert result.verify_failed == 0
    assert seen_order == [1, 2, 3]

    mirror_db = ManifestDB(mirror_root)
    assert mirror_db.all_sha256s() == engine.db.all_sha256s()
    # Newest-first order: B (June) landed before C (March) before A (January).
    rows = mirror_db.iter_files_by_recency()
    assert [r["filename"] for r in rows] == ["B.jpg", "C.jpg", "A.jpg"]
    contents_by_filename = {"A.jpg": b"older", "B.jpg": b"newest", "C.jpg": b"middle"}
    for r in rows:
        dest = Path(r["dest_path"])
        assert dest.exists()
        assert dest.read_bytes() == contents_by_filename[r["filename"]]


def test_second_sync_with_no_changes_copies_nothing(tmp_path):
    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    first = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert first.copied == 1

    second = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert second.copied == 0
    assert second.pending_before == 0


def test_progress_is_cumulative_not_reset_to_one_on_a_resumed_sync(tmp_path):
    """User-reported (2026-09-21): after 128 files were already synced, a
    later run's progress showed "1/6885" with no visible sign the 128
    already there -- looked like it had reset to zero even though nothing
    was lost. Progress must count from where the mirror already stood."""
    engine = make_engine(tmp_path)
    for i in range(3):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"
    sync_mirror(engine.dest_root, engine.db, mirror_root)  # 3 files already copied+verified

    engine.process_upload("IMG_new.jpg", io.BytesIO(b"brand new"), "2026-02-01T00:00:00", None)
    seen = []
    sync_mirror(
        engine.dest_root, engine.db, mirror_root,
        progress_callback=lambda done, total, failed: seen.append((done, total)),
    )

    # 1 file pending, but reported against the 3 already there -> "4 of 4", never "1 of 1".
    assert seen == [(4, 4)]


def test_only_the_new_file_is_copied_on_a_later_sync(tmp_path):
    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"
    sync_mirror(engine.dest_root, engine.db, mirror_root)

    engine.process_upload("B.jpg", io.BytesIO(b"world"), "2026-02-01T00:00:00", None)
    result = sync_mirror(engine.dest_root, engine.db, mirror_root)

    assert result.pending_before == 1
    assert result.copied == 1
    mirror_db = ManifestDB(mirror_root)
    assert {r["filename"] for r in mirror_db.iter_files_by_recency()} == {"A.jpg", "B.jpg"}


def test_corrupted_copy_is_not_recorded_and_is_retried(tmp_path, monkeypatch):
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"real content"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    # Simulate a bad USB write: the copy "succeeds" but the bytes on the
    # mirror don't match what was actually sent.
    real_copy2 = mirror_module.shutil.copy2

    def corrupting_copy2(src, dst, *a, **kw):
        real_copy2(src, dst, *a, **kw)
        Path(dst).write_bytes(b"corrupted!!")

    monkeypatch.setattr(mirror_module.shutil, "copy2", corrupting_copy2)

    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.copied == 0
    assert result.verify_failed == 1
    mirror_db = ManifestDB(mirror_root)
    assert mirror_db.all_sha256s() == set()
    # The bad file must not be left behind either.
    assert list(mirror_root.rglob("A.jpg")) == []

    # Retry, without the corruption this time -> succeeds.
    monkeypatch.setattr(mirror_module.shutil, "copy2", real_copy2)
    retry = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert retry.copied == 1


def test_progress_callback_reports_real_successes_not_attempts(tmp_path, monkeypatch):
    """The real bug (2026-09-23): under real drive contention, a sync can
    attempt many files while almost all of them fail verification -- the
    progress callback used to report the ATTEMPT count, so `done` kept
    climbing while the mirror gained zero real files, making a
    near-completely-failing sync indistinguishable from a healthy one.
    `done` must only ever advance on a genuine success; `failed` must
    track verify failures separately."""
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    # B and D will fail verification; A and C will succeed.
    for name in ["A.jpg", "B.jpg", "C.jpg", "D.jpg"]:
        engine.process_upload(name, io.BytesIO(f"real-{name}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    real_copy2 = mirror_module.shutil.copy2

    def flaky_copy2(src, dst, *a, **kw):
        real_copy2(src, dst, *a, **kw)
        if Path(src).name in ("B.jpg", "D.jpg"):
            Path(dst).write_bytes(b"corrupted!!")

    monkeypatch.setattr(mirror_module.shutil, "copy2", flaky_copy2)

    seen = []  # (done, total, failed) after each attempt, in order

    def on_progress(done, total, failed):
        seen.append((done, total, failed))

    result = sync_mirror(engine.dest_root, engine.db, mirror_root, progress_callback=on_progress)

    assert result.copied == 2
    assert result.verify_failed == 2
    # `done` must never exceed the real number of successes so far, and
    # must never go backwards; `failed` must reach 2 by the end.
    dones = [d for d, _, _ in seen]
    assert dones == sorted(dones)
    assert max(dones) == 2  # never climbed past the real success count
    assert seen[-1][2] == 2  # failed count reflects both corrupted files by the end


def test_reconnecting_a_partially_synced_mirror_resumes_incrementally(tmp_path):
    """Simulates disconnecting the mirror USB partway through a big sync
    and reconnecting later -- the next call must only copy what's still
    missing, never redo completed work (PLAN.md 13.3)."""
    engine = make_engine(tmp_path)
    for i in range(5):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    # Sync once fully, then delete a couple of rows straight out of the
    # mirror's own index -- simulates "USB reconnected but these two
    # files never actually made it across" -- and confirm the next sync
    # catches up on exactly those, not everything.
    sync_mirror(engine.dest_root, engine.db, mirror_root)
    mirror_db = ManifestDB(mirror_root)
    rows = mirror_db.iter_files_by_recency()
    assert len(rows) == 5
    # Drop 2 files straight out of the mirror's own index, as if they'd
    # never been copied in a first, interrupted attempt.
    import sqlite3
    conn = sqlite3.connect(str(mirror_db.db_path))
    conn.execute("DELETE FROM backed_up_files WHERE filename IN ('IMG_0.jpg', 'IMG_1.jpg')")
    conn.commit()
    conn.close()
    mirror_db.close()

    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.pending_before == 2
    assert result.copied == 2


def test_sync_batches_commits_instead_of_one_fsync_per_file(tmp_path, monkeypatch):
    """The actual optimization (2026-09-23, PLAN.md's mirror-speed
    write-up): commit() is real disk work (fsync) and was measured as
    ~81% of total mirror-sync time on real USB media when called once per
    file. This must now be called far less often than once per file for a
    sync bigger than one batch."""
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    for i in range(mirror_module.COMMIT_BATCH_SIZE * 2 + 3):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    commit_calls = []
    real_commit = ManifestDB.commit

    def counting_commit(self):
        commit_calls.append(1)
        real_commit(self)

    monkeypatch.setattr(ManifestDB, "commit", counting_commit)

    total_files = mirror_module.COMMIT_BATCH_SIZE * 2 + 3
    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.copied == total_files

    # 2 full batches + 1 final flush for the 3 leftover files -- NOT one
    # commit per file (which would be `total_files` calls).
    assert len(commit_calls) == 3
    assert len(commit_calls) < total_files

    # And correctness is untouched: every file is really there, verified.
    mirror_db = ManifestDB(mirror_root)
    assert mirror_db.all_sha256s() == engine.db.all_sha256s()


def test_interrupted_batch_self_heals_without_losing_or_duplicating_anything(tmp_path):
    """Simulates the real failure mode batching introduces: the app gets
    killed (not gracefully closed) after some files in the CURRENT batch
    were copied+verified but before that batch's commit() ran. Those rows
    must simply not exist yet -- never partially there, never marked done
    without really being committed -- and the next sync must pick them
    back up cleanly, with no duplicate rows and no leftover partial files."""
    engine = make_engine(tmp_path)
    for i in range(5):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"
    mirror_root.mkdir()

    # Manually replay what sync_mirror's loop does for 3 of the 5 files,
    # but WITHOUT ever calling commit() -- then close the connection
    # exactly like a hard process kill would (no clean shutdown, no final
    # flush), to prove the rows really never landed.
    mirror_db = ManifestDB(mirror_root)
    rows = engine.db.iter_files_by_recency()[:3]
    for row in rows:
        dest = mirror_root / Path(row["dest_path"]).relative_to(engine.dest_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(row["dest_path"]).read_bytes())
        mirror_db.record_file(row["filename"], row["sha256"], row["taken_at"], str(dest), row["size_bytes"], commit=False)
    mirror_db._conn.close()  # raw close, bypassing ManifestDB.close()/commit() -- simulates a hard kill

    # Reopening confirms the uncommitted rows are genuinely gone, not just
    # hidden -- SQLite's own rollback-on-close, not anything this project
    # implements itself.
    reopened = ManifestDB(mirror_root)
    assert reopened.all_sha256s() == set()
    reopened.close()

    # A real sync now must cleanly pick up all 5 (including the 3 "ghost"
    # files whose bytes are still sitting on disk from the simulated
    # crash) -- overwriting the leftover partial files harmlessly, no
    # duplicates, no crash.
    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.copied == 5
    assert result.pending_before == 5
    final_db = ManifestDB(mirror_root)
    assert final_db.all_sha256s() == engine.db.all_sha256s()
    assert len(final_db.iter_files_by_recency()) == 5  # no duplicate rows


def test_cancelled_sync_still_commits_the_partial_batch(tmp_path):
    """A cancellation (e.g. to safely eject the drive) must flush whatever
    was already verified in the current, not-yet-full batch -- otherwise
    batching would make Cancel lose more progress than it used to."""
    engine = make_engine(tmp_path)
    for i in range(4):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    cancel_event = threading.Event()
    seen = []

    def on_progress(done, total, failed):
        seen.append(done)
        if done == 2:  # well short of COMMIT_BATCH_SIZE -- a partial batch
            cancel_event.set()

    result = sync_mirror(
        engine.dest_root, engine.db, mirror_root,
        progress_callback=on_progress, cancel_event=cancel_event,
    )
    assert result.cancelled is True
    assert result.copied == 2

    # Even though 2 is far short of a full batch, it must already be
    # durably recorded -- not lost because the sync stopped early.
    mirror_db = ManifestDB(mirror_root)
    assert len(mirror_db.all_sha256s()) == 2


def test_replacing_mirror_with_a_different_empty_folder_is_a_full_fresh_sync(tmp_path):
    """Swapping the physical drive at the configured mirror path for a
    different, empty one must never be treated as 'already synced' --
    the index lives on the drive itself, not in any remembered flag."""
    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)

    old_mirror = tmp_path / "mirror-old"
    sync_mirror(engine.dest_root, engine.db, old_mirror)

    new_mirror = tmp_path / "mirror-new"  # a totally different, empty folder
    result = sync_mirror(engine.dest_root, engine.db, new_mirror)
    assert result.copied == 1
    assert result.pending_before == 1


def test_insufficient_space_still_copies_newest_first_until_full(tmp_path, monkeypatch):
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    engine.process_upload("old.jpg", io.BytesIO(b"x" * 100), "2026-01-01T00:00:00", None)
    engine.process_upload("newest.jpg", io.BytesIO(b"y" * 100), "2026-06-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"
    mirror_root.mkdir()

    class _TinyDisk:
        free = 100  # only room for one of the two 100-byte files

    monkeypatch.setattr(mirror_module.shutil, "disk_usage", lambda path: _TinyDisk())

    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.insufficient_space_warning is True
    # The warning doesn't block the sync -- it still proceeds and copies
    # what it can (the real per-file OSError-on-full-disk path is covered
    # by test_disk_fills_up_mid_copy_stops_gracefully below; disk_usage
    # here is only used for the up-front warning, not to actually cap
    # writes, so both files fit on the real tmp_path filesystem).
    assert result.copied == 2
    mirror_db = ManifestDB(mirror_root)
    rows = mirror_db.iter_files_by_recency()
    assert rows[0]["filename"] == "newest.jpg"  # newest copied first


def test_disk_fills_up_mid_copy_stops_gracefully(tmp_path, monkeypatch):
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    def failing_copy2(src, dst, *a, **kw):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mirror_module.shutil, "copy2", failing_copy2)

    result = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result.stopped_with_error is not None
    assert result.fatal_error is None  # a per-file failure, not a total sync crash
    assert result.copied == 0
    # No partial file left behind.
    assert list(mirror_root.rglob("A.jpg")) == []


def test_drive_disconnected_mid_copy_reports_error_not_a_crash(tmp_path, monkeypatch):
    """The scenario a real device raised: yanking the mirror USB instead
    of safely ejecting it, mid-copy. sync_mirror() must come back with a
    result (never raise), so the GUI's background worker always re-enables
    its button and shows something, instead of getting stuck on
    "Syncing..." forever with no visible error."""
    import server.mirror as mirror_module

    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    def device_removed_copy2(src, dst, *a, **kw):
        raise OSError(21, "The device is not ready")  # WinError 21-style

    monkeypatch.setattr(mirror_module.shutil, "copy2", device_removed_copy2)
    # Also simulate the drive being fully gone: even cleanup can't touch it.
    real_unlink = Path.unlink

    def failing_unlink(self, *a, **kw):
        if self.name == "A.jpg":
            raise OSError(21, "The device is not ready")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    result = sync_mirror(engine.dest_root, engine.db, mirror_root)  # must not raise
    assert result.stopped_with_error is not None
    assert result.copied == 0


def test_cancelling_mid_sync_stops_cleanly_and_resumes_later(tmp_path):
    """User-requested (2026-09-21): a way to stop a sync early, e.g. to
    safely eject the drive. Cancellation is only checked BETWEEN files, so
    whatever's already copied+verified stays valid and nothing is left
    half-written."""
    engine = make_engine(tmp_path)
    for i in range(5):
        engine.process_upload(f"IMG_{i}.jpg", io.BytesIO(f"content-{i}".encode()), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    cancel_event = threading.Event()
    seen = []

    def progress(done, total, failed):
        seen.append(done)
        if done == 2:
            cancel_event.set()  # ask to stop right after the 2nd file lands

    result = sync_mirror(engine.dest_root, engine.db, mirror_root, progress_callback=progress, cancel_event=cancel_event)
    assert result.cancelled is True
    assert result.copied == 2
    assert result.fatal_error is None
    assert result.stopped_with_error is None

    mirror_db = ManifestDB(mirror_root)
    assert len(mirror_db.iter_files_by_recency()) == 2
    mirror_db.close()

    # A later sync (fresh Event, nothing cancelled) picks up the rest.
    result2 = sync_mirror(engine.dest_root, engine.db, mirror_root)
    assert result2.copied == 3
    assert result2.cancelled is False


def test_get_mirror_status_reflects_real_progress_without_opening_manifestdb(tmp_path):
    engine = make_engine(tmp_path)
    engine.process_upload("A.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)
    mirror_root = tmp_path / "mirror"

    # Not connected yet -> None, not an error.
    assert get_mirror_status(str(mirror_root)) is None

    sync_mirror(engine.dest_root, engine.db, mirror_root)
    status = get_mirror_status(str(mirror_root))
    assert status["total_files"] == 1
    assert status["total_bytes"] is not None and status["total_bytes"] > 0
    assert status["free_bytes"] is not None and status["free_bytes"] >= 0


def test_mirror_promoted_to_primary_reports_correct_missing_files(tmp_path):
    """The core promise of the design (PLAN.md 13.2): once B has its own
    real index, pointing a profile's destination_dir straight at B needs
    NO extra reconciliation step -- /check-equivalent logic must already
    see exactly what B has and nothing more."""
    engine_a = make_engine(tmp_path, "A")
    engine_a.process_upload("kept.jpg", io.BytesIO(b"kept"), "2026-01-01T00:00:00", None)
    engine_a.process_upload("also_new.jpg", io.BytesIO(b"also new"), "2026-02-01T00:00:00", None)

    mirror_root = tmp_path / "B"
    sync_mirror(engine_a.dest_root, engine_a.db, mirror_root)  # B now has both files, verified

    # A gets one MORE file that never made it to B.
    engine_a.process_upload("never_mirrored.jpg", io.BytesIO(b"new on A only"), "2026-03-01T00:00:00", None)

    # "Promote" B: just open a fresh engine rooted at B, exactly like the
    # GUI's "Elegir carpeta..." would after set_destination() + forget_profile().
    engine_b_as_primary = BackupEngine(mirror_root, ManifestDB(mirror_root))
    assert engine_b_as_primary.check_exists("kept.jpg", "2026-01-01T00:00:00") is True
    assert engine_b_as_primary.check_exists("also_new.jpg", "2026-02-01T00:00:00") is True
    assert engine_b_as_primary.check_exists("never_mirrored.jpg", "2026-03-01T00:00:00") is False
