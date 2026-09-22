"""Unit tests for the core backup engine — the rules that matter most:
no-op on identical duplicate, keep-both on name collision with different
content, one-directional writes, and index persistence.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

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


def test_reap_logs_a_warning_distinct_from_a_real_run_finish(tmp_path, caplog):
    """A reaped run must be visibly distinguishable in the activity log
    from a genuine /run/finish call — otherwise there's no way to tell
    afterward whether a run actually completed on its own or was just
    auto-closed because the app got closed mid-run (confirmed source of
    real user confusion, 2026-09-18)."""
    dest = tmp_path / "dest"
    dest.mkdir()
    db1 = ManifestDB(dest)
    run_id = db1.start_run()
    db1.close()

    with caplog.at_level("WARNING", logger="backup_engine"):
        ManifestDB(dest)

    assert any(run_id in record.getMessage() for record in caplog.records)
    assert any("previous session" in record.getMessage() for record in caplog.records)


def test_reap_dangling_runs_false_never_touches_a_genuinely_live_run(tmp_path):
    """Found live, 2026-09-22: server/mirror.py's sync needs to open a
    SECOND ManifestDB on the SAME primary dest_root, from within the SAME
    still-running app process, to read the primary index -- while a real
    /run/start from the phone might genuinely still be in progress (NOT
    left over from a previous process lifetime, the one case reaping is
    meant to handle). Without reap_dangling_runs=False, that second open
    reaped the live run right out from under the phone's own still-
    uploading Shortcut, making the backup look stalled in the GUI even
    though files kept landing on disk."""
    dest = tmp_path / "dest"
    dest.mkdir()
    db1 = ManifestDB(dest)
    run_id = db1.start_run()  # NOT closed -- simulates a genuinely in-progress run

    db2 = ManifestDB(dest, reap_dangling_runs=False)  # e.g. the mirror sync's read-only-ish open
    assert db2.get_status()["last_run"]["finished_at"] is None  # untouched

    # The original run is still exactly as live as it was -- db1 (or a
    # fresh default-True open, simulating the real app reopening later)
    # still sees it as unfinished, not silently closed by db2.
    assert db1.get_status()["last_run"]["id"] == run_id
    assert db1.get_status()["last_run"]["finished_at"] is None


def _fake_jpeg_bytes(exif_datetime_original: str | None = None) -> bytes:
    """A real, tiny, valid JPEG — optionally with a DateTimeOriginal EXIF
    tag — for testing the content-sniffing/EXIF-fallback paths without a
    real photo file. See PLAN.md §5.4 for why this matters: some Photos
    items arrive with neither a filename extension nor a `taken_at`."""
    from PIL import Image

    img = Image.new("RGB", (2, 2), color="red")
    buf = io.BytesIO()
    if exif_datetime_original:
        exif = img.getexif()
        exif[36867] = exif_datetime_original  # DateTimeOriginal
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def _synthetic_mov(mvhd_creation: int, mdhd_creation: int, mdat: bytes) -> bytes:
    """Same box builder as test_video_metadata.py's _build_synthetic_mov,
    parameterized so tests here can vary just the timestamp fields or just
    the media payload."""
    import struct

    def box(box_type: str, payload: bytes) -> bytes:
        return struct.pack(">I4s", 8 + len(payload), box_type.encode("ascii")) + payload

    def hdr(version0_creation: int) -> bytes:
        return struct.pack(">B3sII", 0, b"\x00\x00\x00", version0_creation, version0_creation) + b"\x00" * 20

    mvhd = box("mvhd", hdr(mvhd_creation))
    mdhd = box("mdhd", hdr(mdhd_creation))
    mdia = box("mdia", mdhd)
    trak = box("trak", mdia)
    moov = box("moov", mvhd + trak)
    ftyp = box("ftyp", b"qt  " + b"\x00" * 12)
    return ftyp + moov + box("mdat", mdat)


def test_reencoded_video_with_same_content_is_deduped_not_kept_both(tmp_path):
    """The real bug (2026-09-22, 54 duplicate copies / 2.46GB wasted):
    Shortcuts' "Encode Media" 0-byte retry re-stamps the container's own
    creation_time on every pass over the SAME source video, so its raw
    sha256 differs each time even though the actual video content is
    unchanged. Two "encode passes" of the same source must be treated as
    the same backed-up file, not kept as separate copies."""
    engine = make_engine(tmp_path)
    mdat = b"\xde\xad\xbe\xef" * 8
    pass_1 = _synthetic_mov(mvhd_creation=1000, mdhd_creation=2000, mdat=mdat)
    pass_2 = _synthetic_mov(mvhd_creation=9999999, mdhd_creation=8888888, mdat=mdat)
    assert pass_1 != pass_2  # genuinely different bytes, same content

    first = engine.process_upload("ScreenRecording_01-01-2026.mov", io.BytesIO(pass_1), None, None)
    second = engine.process_upload("ScreenRecording_01-01-2026.mov", io.BytesIO(pass_2), None, None)

    assert first["status"] == "new"
    assert second["status"] == "skipped_duplicate"
    files = list((Path(engine.dest_root)).rglob("ScreenRecording_01-01-2026*"))
    assert len(files) == 1  # no wasted duplicate copy


def test_reencoded_video_with_different_content_still_kept_both(tmp_path):
    """A genuine content difference in an mdat-bearing video must still be
    kept as a separate file — content_signature must not be over-broad."""
    engine = make_engine(tmp_path)
    pass_1 = _synthetic_mov(mvhd_creation=1000, mdhd_creation=2000, mdat=b"\xde\xad\xbe\xef" * 8)
    pass_2 = _synthetic_mov(mvhd_creation=1000, mdhd_creation=2000, mdat=b"\xff\xff\xff\xff" * 8)

    first = engine.process_upload("ScreenRecording_02-02-2026.mov", io.BytesIO(pass_1), None, None)
    second = engine.process_upload("ScreenRecording_02-02-2026.mov", io.BytesIO(pass_2), None, None)

    assert first["status"] == "new"
    assert second["status"] == "conflict_kept_both"


def test_missing_extension_is_detected_from_jpeg_content(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.process_upload("IMG_9001", io.BytesIO(_fake_jpeg_bytes()), "2026-05-01T00:00:00", None)
    assert result["dest_path"].endswith("IMG_9001.jpg")


def test_missing_extension_is_detected_from_video_content(tmp_path):
    engine = make_engine(tmp_path)
    # Real QuickTime .mov signature (confirmed against an actual
    # ScreenRecording file) padded out to a non-trivial size.
    fake_mov = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00" + b"\x00" * 64
    result = engine.process_upload("ScreenRecording_01-01-2026", io.BytesIO(fake_mov), "2026-05-01T00:00:00", None)
    assert result["dest_path"].endswith("ScreenRecording_01-01-2026.mov")


def test_extension_is_never_overridden_when_already_present(tmp_path):
    """Content-sniffing only fills in a MISSING extension — it must never
    second-guess or replace one the client actually sent, even if the
    real bytes look like a different format."""
    engine = make_engine(tmp_path)
    result = engine.process_upload("photo.png", io.BytesIO(_fake_jpeg_bytes()), "2026-05-01T00:00:00", None)
    assert result["dest_path"].endswith("photo.png")


def test_missing_taken_at_falls_back_to_exif_date_when_present(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.process_upload(
        "IMG_9002.jpg", io.BytesIO(_fake_jpeg_bytes("2019:03:15 08:00:00")), None, None
    )
    assert result["status"] == "new"
    assert str(Path(result["dest_path"]).parent).endswith(str(Path("2019") / "03"))


class _DiskFullFile:
    """Wraps a REAL file object so open() genuinely creates a file on disk
    (exactly as it would in production), but write() fails immediately
    after — simulating a drive that fills up mid-write (ENOSPC). This
    lets the test verify the leftover partial file actually gets deleted,
    not just that a mock never touched disk in the first place."""

    def __init__(self, real_file):
        self._real_file = real_file

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._real_file.close()
        return False

    def write(self, data):
        raise OSError(28, "No space left on device")


def test_disk_full_during_write_is_not_recorded_as_backed_up(tmp_path, monkeypatch):
    """Found via design review while planning the second-USB mirror feature
    (2026-09-21): a disk filling up mid-write used to propagate as a raw,
    unhandled exception instead of the same graceful "not recorded, retry
    later" pattern already used for a 0-byte upload — see app.py's /upload
    for why an ungraceful failure here matters (a non-2xx response silently
    aborts the rest of the Shortcut's loop, AGENTS.md lesson 11). Also
    covers the leftover .part file this same fix cleans up."""
    import server.storage as storage_module

    engine = make_engine(tmp_path)
    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        if str(path).endswith(".part"):
            return _DiskFullFile(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(storage_module, "open", failing_open, raising=False)

    with pytest.raises(ValueError, match="could not be saved"):
        engine.process_upload("IMG_9003.jpg", io.BytesIO(b"some real bytes"), "2026-05-01T00:00:00", None)

    # Not recorded as backed up -> a later run (once space is freed) retries it.
    assert engine.db.get_status()["total_files_backed_up"] == 0
    # The real 0-byte partial file that open() created got cleaned up, not
    # left behind in the staging dir forever.
    assert list(engine.staging_dir.glob("*.part")) == []
