"""Backup by cable, driven through a simulated phone: same rules as WiFi, no
duplicates across differently named copies, and honest reporting when the
phone or the drive fails. See PLAN.md section 26.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import hashlib
import io
import re
import shutil
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import cable_import
from server.cable_import import CablePlan, analyze_device, run_cable_import
from server.device_source import DeviceItem, DeviceReadError
from server.manifest_db import ManifestDB
from server.storage import BackupEngine
from tests.video_fixture import make_video


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(cable_import.time, "sleep", lambda _s: None)


class FakePhone:
    def __init__(self, files: dict[str, tuple[bytes, str]]):
        self.files = files
        self.reads: list[str] = []
        self.fail_reads: dict[str, int] = {}  # name -> how many reads fail first
        self.wrong_bytes: dict[str, int] = {}  # name -> how many reads return another file
        self.gone = False
        self.reopens = 0
        self.closed = False

    def list_items(self, on_progress=None, cancel=None):
        items = [DeviceItem(name, name, len(data), date) for name, (data, date) in self.files.items()]
        for i, _item in enumerate(items, start=1):
            if on_progress:
                on_progress(i)
        return items

    def open_reader(self, item):
        self.reads.append(item.name)
        if self.gone:
            raise DeviceReadError("device not found")
        if self.fail_reads.get(item.name, 0) > 0:
            self.fail_reads[item.name] -= 1
            raise DeviceReadError("resource in use")
        if self.wrong_bytes.get(item.name, 0) > 0:
            self.wrong_bytes[item.name] -= 1
            return io.BytesIO(b"somebody else's file")
        return io.BytesIO(self.files[item.name][0])

    def reopen(self):
        self.reopens += 1

    def close(self):
        self.closed = True


def _cable_backup(phone, dest, **kwargs):
    plan = analyze_device(phone, dest)
    return plan, run_cable_import(phone, plan, dest, **kwargs)


def _files_on_disk(dest: Path) -> list[Path]:
    return [p for p in dest.rglob("*") if p.is_file() and ".iphone_backup_index" not in p.parts]


def _wifi_upload(dest: Path, name: str, data: bytes, date: str) -> None:
    db = ManifestDB(dest)
    BackupEngine(dest, db).process_upload(name, io.BytesIO(data), date, None)
    db.close()


def _rows(dest: Path) -> int:
    db = ManifestDB(dest, reap_dangling_runs=False)
    try:
        return db.get_status()["total_files_backed_up"]
    finally:
        db.close()


def test_new_files_land_in_year_month_and_are_recorded(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    plan, result = _cable_backup(phone, tmp_path)
    assert (plan.total_on_device, plan.already, len(plan.pending)) == (1, 0, 1)
    assert result.copied == 1 and result.failed == 0
    assert (tmp_path / "2026" / "03" / "IMG_1.HEIC").read_bytes() == b"photo"
    assert _rows(tmp_path) == 1


def test_running_it_again_copies_and_reads_nothing(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    _cable_backup(phone, tmp_path)
    phone.reads.clear()
    plan, result = _cable_backup(phone, tmp_path)
    assert (plan.already, plan.pending) == (1, [])
    assert result.copied == 0 and phone.reads == []
    assert len(_files_on_disk(tmp_path)) == 1


def test_what_wifi_already_saved_with_the_same_name_is_recognized_without_reading(tmp_path):
    _wifi_upload(tmp_path, "IMG_1.heic", b"photo", "2026-03-05T10:00:00")
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    plan, _result = _cable_backup(phone, tmp_path)
    assert plan.already == 1 and phone.reads == []
    assert len(_files_on_disk(tmp_path)) == 1


def test_same_content_under_another_name_is_not_stored_twice_and_is_remembered(tmp_path):
    _wifi_upload(tmp_path, "ced9b322.jpeg", b"whatsapp photo", "2026-09-14T18:08:17")
    phone = FakePhone({"DFTN0869.JPG": (b"whatsapp photo", "2026-09-14T18:08:17")})

    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 0 and result.already_had == 1
    assert len(_files_on_disk(tmp_path)) == 1

    phone.reads.clear()
    plan, _result = _cable_backup(phone, tmp_path)
    assert plan.already == 1 and phone.reads == []


def test_reencoded_video_under_another_name_is_recognized_by_its_frames(tmp_path):
    frames = [bytes([i]) * (100 + i) for i in range(30)]
    _wifi_upload(tmp_path, "abc.mp4", make_video(frames, moov_first=True), "2026-05-16T21:10:05")
    phone = FakePhone({"MOHR7868.MP4": (make_video(frames), "2026-05-16T21:24:00")})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.already_had == 1 and len(_files_on_disk(tmp_path)) == 1


def test_different_video_on_the_same_day_is_copied(tmp_path):
    _wifi_upload(tmp_path, "abc.mp4", make_video([bytes([i]) * (100 + i) for i in range(30)]), "2026-05-16T21:10:05")
    phone = FakePhone({"OTHER.MP4": (make_video([bytes([i]) * (300 - i) for i in range(30)]), "2026-05-16T22:00:00")})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 1 and len(_files_on_disk(tmp_path)) == 2


def test_same_name_different_content_keeps_both(tmp_path):
    _wifi_upload(tmp_path, "IMG_7568.HEIC", b"edited version", "2026-05-27T16:03:55")
    phone = FakePhone({"IMG_7568.HEIC": (b"the much longer original", "2026-05-27T16:03:55")})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.conflicts == 1
    contents = {p.read_bytes() for p in _files_on_disk(tmp_path)}
    assert contents == {b"edited version", b"the much longer original"}


def test_edit_recipes_are_skipped_but_edited_pictures_are_kept(tmp_path):
    phone = FakePhone({
        "IMG_1.AAE": (b"<plist/>", "2026-03-05T10:00:00"),
        "IMG_E1.HEIC": (b"edited", "2026-03-05T10:00:00"),
    })
    plan, result = _cable_backup(phone, tmp_path)
    assert plan.total_on_device == 1
    assert result.copied == 1
    assert [p.name for p in _files_on_disk(tmp_path)] == ["IMG_E1.HEIC"]


def test_a_recorded_file_that_was_deleted_from_the_destination_is_copied_again(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    _cable_backup(phone, tmp_path)
    (tmp_path / "2026" / "03" / "IMG_1.HEIC").unlink()
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 1


def test_a_file_that_landed_without_a_row_gets_its_row_on_the_next_run(tmp_path):
    (tmp_path / "2026" / "03").mkdir(parents=True)
    (tmp_path / "2026" / "03" / "IMG_1.HEIC").write_bytes(b"photo")
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    plan = CablePlan(pending=[DeviceItem("IMG_1.HEIC", "IMG_1.HEIC", 5, "2026-03-05T10:00:00")])
    result = run_cable_import(phone, plan, tmp_path)
    assert result.already_had == 1 and _rows(tmp_path) == 1


def test_transient_read_errors_are_retried_with_a_fresh_session(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    phone.fail_reads["IMG_1.HEIC"] = 2
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 1 and result.failed == 0
    assert phone.reopens == 2


def test_bytes_of_the_wrong_size_are_never_accepted(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"the real photo", "2026-03-05T10:00:00")})
    phone.wrong_bytes["IMG_1.HEIC"] = 1
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 1
    assert (tmp_path / "2026" / "03" / "IMG_1.HEIC").read_bytes() == b"the real photo"


def test_a_file_that_never_reads_correctly_is_reported_and_not_recorded(tmp_path):
    phone = FakePhone({
        "BAD.HEIC": (b"bad", "2026-03-06T10:00:00"),
        "OK.HEIC": (b"fine", "2026-03-05T10:00:00"),
    })
    phone.wrong_bytes["BAD.HEIC"] = 99
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.failed == 1 and result.failed_names == ["BAD.HEIC"]
    assert result.copied == 1 and result.stopped_with_error is None
    assert not (tmp_path / "2026" / "03" / "BAD.HEIC").exists()
    assert _rows(tmp_path) == 1


def test_a_disconnected_phone_stops_the_copy_instead_of_failing_thousands(tmp_path):
    phone = FakePhone({f"IMG_{i}.HEIC": (b"x%d" % i, "2026-03-05T10:00:00") for i in range(40)})
    plan = analyze_device(phone, tmp_path)
    phone.gone = True
    result = run_cable_import(phone, plan, tmp_path)
    assert result.stopped_with_error == "device"
    assert result.failed == cable_import.MAX_CONSECUTIVE_FAILURES


def test_a_full_drive_stops_cleanly_and_leaves_nothing_behind(tmp_path, monkeypatch):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    plan = analyze_device(phone, tmp_path)
    real_open = open

    class FullFile:
        def __init__(self, f):
            self.f = f

        def write(self, _chunk):
            raise OSError(28, "No space left on device")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.f.close()

    def fake_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        return FullFile(handle) if str(path).endswith(".part") and "w" in mode else handle

    monkeypatch.setattr("builtins.open", fake_open)
    result = run_cable_import(phone, plan, tmp_path)
    monkeypatch.undo()
    assert "No space left" in result.stopped_with_error
    assert result.copied == 0
    assert not list((tmp_path / ".iphone_backup_index" / "staging").iterdir())
    assert _rows(tmp_path) == 0


def test_cancelling_keeps_what_was_copied_and_resuming_finishes_the_rest(tmp_path):
    phone = FakePhone({f"IMG_{i}.HEIC": (b"x%d" % i, "2026-03-05T10:00:00") for i in range(10)})
    cancel = threading.Event()
    plan = analyze_device(phone, tmp_path)

    def stop_after_three(done, _total, _failed, _bytes):
        if done >= 3:
            cancel.set()

    result = run_cable_import(phone, plan, tmp_path, progress_callback=stop_after_three, cancel_event=cancel)
    assert result.cancelled and result.copied == 3
    assert _rows(tmp_path) == 3

    _plan, resumed = _cable_backup(phone, tmp_path)
    assert resumed.copied == 7 and len(_files_on_disk(tmp_path)) == 10


def test_progress_counts_only_confirmed_files_and_is_cumulative(tmp_path):
    _wifi_upload(tmp_path, "OLD.HEIC", b"old", "2026-03-01T10:00:00")
    phone = FakePhone({
        "OLD.HEIC": (b"old", "2026-03-01T10:00:00"),
        "BAD.HEIC": (b"bad", "2026-03-03T10:00:00"),
        "NEW.HEIC": (b"new", "2026-03-02T10:00:00"),
    })
    phone.wrong_bytes["BAD.HEIC"] = 99
    seen = []
    _cable_backup(phone, tmp_path, progress_callback=lambda d, t, f, _b: seen.append((d, t, f)))
    assert seen == [(1, 3, 1), (2, 3, 1)]


def test_the_run_is_recorded_as_a_finished_cable_run(tmp_path):
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    _cable_backup(phone, tmp_path)
    db = ManifestDB(tmp_path, reap_dangling_runs=False)
    last_run = db.get_status()["last_run"]
    db.close()
    assert last_run["source"] == "cable"
    assert last_run["finished_at"] is not None
    assert last_run["files_new"] == 1


def test_opening_an_older_index_adds_the_new_column_and_keeps_its_runs(tmp_path):
    import sqlite3

    index = tmp_path / ".iphone_backup_index"
    index.mkdir()
    conn = sqlite3.connect(index / "index.sqlite")
    conn.executescript(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,"
        " files_new INTEGER NOT NULL DEFAULT 0, files_skipped INTEGER NOT NULL DEFAULT 0,"
        " files_conflict INTEGER NOT NULL DEFAULT 0, files_error INTEGER NOT NULL DEFAULT 0);"
        " INSERT INTO runs (id, started_at, finished_at) VALUES ('old', '2026-01-01', '2026-01-02');"
    )
    conn.commit()
    conn.close()
    db = ManifestDB(tmp_path)
    assert db.get_status()["last_run"]["source"] == "wifi"
    db.close()


def test_an_unusable_destination_is_reported_not_raised(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    phone = FakePhone({"IMG_1.HEIC": (b"photo", "2026-03-05T10:00:00")})
    plan = analyze_device(phone, blocker / "dest")
    assert plan.fatal_error
    assert run_cable_import(phone, CablePlan(pending=[]), blocker / "dest").fatal_error


def test_an_empty_file_on_the_phone_fails_alone_and_the_copy_continues(tmp_path):
    phone = FakePhone({
        "EMPTY.HEIC": (b"", "2026-03-06T10:00:00"),
        "OK.HEIC": (b"fine", "2026-03-05T10:00:00"),
    })
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.fatal_error is None
    assert result.failed_names == ["EMPTY.HEIC"] and result.copied == 1


def test_same_name_and_content_in_another_month_is_not_stored_twice(tmp_path):
    # Older rows stored taken_at in UTC, so a late-night photo sits in the next month.
    _wifi_upload(tmp_path, "IMG_1.HEIC", b"new year's eve", "2026-02-01T04:00:00+00:00")
    phone = FakePhone({"IMG_1.HEIC": (b"new year's eve", "2026-01-31T23:00:00")})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 0 and result.already_had == 1
    assert len(_files_on_disk(tmp_path)) == 1

    phone.reads.clear()
    assert analyze_device(phone, tmp_path).pending == [] and phone.reads == []


def test_a_file_with_no_date_already_backed_up_elsewhere_is_not_stored_again(tmp_path):
    # With no date it would fall back to "now", a different folder on every month.
    _wifi_upload(tmp_path, "NODATE.PNG", b"no date at all", "2020-01-01T00:00:00")
    phone = FakePhone({"NODATE.PNG": (b"no date at all", None)})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.copied == 0 and len(_files_on_disk(tmp_path)) == 1


def test_a_reencoded_video_with_the_same_name_is_only_read_once(tmp_path):
    frames = [bytes([i]) * (100 + i) for i in range(30)]
    _wifi_upload(tmp_path, "IMG_1.MOV", make_video(frames, moov_first=True), "2026-05-16T21:10:05")
    phone = FakePhone({"IMG_1.MOV": (make_video(frames, padding=40), "2026-05-16T21:10:05")})
    _plan, result = _cable_backup(phone, tmp_path)
    assert result.already_had == 1 and len(_files_on_disk(tmp_path)) == 1

    phone.reads.clear()
    assert analyze_device(phone, tmp_path).pending == [] and phone.reads == []


def test_an_empty_file_counts_as_one_error_in_the_run(tmp_path):
    phone = FakePhone({"EMPTY.HEIC": (b"", "2026-03-06T10:00:00")})
    _cable_backup(phone, tmp_path)
    db = ManifestDB(tmp_path, reap_dangling_runs=False)
    assert db.get_status()["last_run"]["files_error"] == 1
    db.close()


def test_a_drive_failing_every_verification_stops_the_copy(tmp_path, monkeypatch):
    phone = FakePhone({f"IMG_{i}.HEIC": (b"x%d" % i, "2026-03-05T10:00:00") for i in range(30)})
    plan = analyze_device(phone, tmp_path)
    monkeypatch.setattr(BackupEngine, "_hash_existing", staticmethod(lambda _path: "corrupted"))
    seen = []
    result = run_cable_import(phone, plan, tmp_path, progress_callback=lambda d, t, f, _b: seen.append(f))
    assert result.failed == cable_import.MAX_CONSECUTIVE_FAILURES
    assert result.stopped_with_error == "verification"
    assert seen == [1, 2, 3, 4]


def test_objects_the_phone_wont_describe_are_reported(tmp_path):
    phone = FakePhone({"OK.HEIC": (b"fine", "2026-03-05T10:00:00")})
    phone.unreadable = 3
    assert analyze_device(phone, tmp_path).unreadable == 3


def test_a_phone_listing_nothing_is_an_error_not_all_backed_up(tmp_path):
    plan = analyze_device(FakePhone({}), tmp_path)
    assert plan.fatal_error and plan.pending == []


def test_the_device_code_only_ever_opens_for_reading():
    source = (Path(__file__).resolve().parent.parent / "server" / "device_source.py").read_text(encoding="utf-8")
    assert "GENERIC_READ = 0x80000000" in source
    assert "GENERIC_WRITE" not in source
    for write_call in ("CreateObjectWithPropertiesAndData", "CreateObjectWithPropertiesOnly", ".Delete(", ".Move(", ".Copy("):
        assert write_call not in source
    assert len(re.findall(r"SetUnsignedIntegerValue\(", source)) == 1
