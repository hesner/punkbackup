"""What an abrupt stop really leaves behind: a real process, killed outright
while writing, for both the WiFi path (a commit per file) and the cable path
(batched commits). Asserts on the disk and the database afterwards.

Doesn't simulate a power cut: killing a process leaves the OS write cache
alive, so this says nothing about bytes that never reached the drive.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import hashlib
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.cable_import import analyze_device, run_cable_import
from server.device_source import DeviceItem
from server.manifest_db import ManifestDB, path_key
from server.storage import BackupEngine

WRITER = r"""
import io, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from server.manifest_db import ManifestDB
from server.storage import BackupEngine
dest, commit = Path(sys.argv[2]), sys.argv[3] == "batch"
db = ManifestDB(dest)
engine = BackupEngine(dest, db)
run = db.start_run()
for i in range(100000):
    staged, sha, size = engine.stage_bytes(io.BytesIO(bytes([i % 251]) * 300000 + str(i).encode()))
    engine.finalize_upload(f"IMG_{i}.HEIC", staged, sha, size, "2026-03-05T10:00:00", run, commit=not commit)
    if commit and i % 25 == 24:
        db.commit()
    print(i, flush=True)
"""


def _kill_while_writing(dest: Path, mode: str, after_files: int = 60) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", WRITER, str(ROOT), str(dest), mode], stdout=subprocess.PIPE, text=True,
    )
    for _ in range(after_files):
        process.stdout.readline()
    time.sleep(0.013)  # land anywhere inside the next file
    process.kill()
    process.wait()
    process.stdout.close()


def _inspect(dest: Path) -> dict:
    conn = sqlite3.connect(dest / ".iphone_backup_index" / "index.sqlite")
    check = conn.execute("PRAGMA integrity_check").fetchone()[0]
    rows = conn.execute("SELECT dest_path, sha256 FROM backed_up_files").fetchall()
    conn.close()
    files = [p for p in dest.rglob("*.HEIC") if p.is_file()]
    return {"check": check, "rows": rows, "files": files}


@pytest.mark.parametrize("mode", ["per_file", "batch"])
@pytest.mark.parametrize("attempt", range(3))
def test_killing_the_process_never_corrupts_or_lies(tmp_path, mode, attempt):
    _kill_while_writing(tmp_path, mode, after_files=60 + attempt * 7)
    state = _inspect(tmp_path)

    assert state["check"] == "ok"
    assert state["rows"], "nothing was committed before the kill"
    for dest_path, sha256 in state["rows"]:  # a row always means a whole file
        assert hashlib.sha256(Path(dest_path).read_bytes()).hexdigest() == sha256

    # A file on disk is always whole, with or without a row: it only appears
    # in its final place by a rename, after it was completely written.
    for path in state["files"]:
        assert path.stat().st_size >= 300000

    # Leftovers: the partial file is removed the next time the folder is opened.
    db = ManifestDB(tmp_path)
    BackupEngine(tmp_path, db).clear_staging(older_than_seconds=0)
    assert list((tmp_path / ".iphone_backup_index" / "staging").glob("*.part")) == []
    assert db.get_status()["state"] == "idle"  # the dangling run was closed
    db.close()


def test_batched_writes_lose_at_most_one_batch_of_rows_and_the_cable_heals_them(tmp_path):
    _kill_while_writing(tmp_path, "batch", after_files=60)
    state = _inspect(tmp_path)
    indexed = {path_key(path) for path, _sha in state["rows"]}
    orphans = [p for p in state["files"] if path_key(p) not in indexed]
    assert 0 < len(orphans) <= 25

    class Phone:
        def list_items(self, on_progress=None, cancel=None):
            return [DeviceItem(p.name, p.name, p.stat().st_size, "2026-03-05T10:00:00") for p in state["files"]]

        def open_reader(self, item):
            return open(tmp_path / "2026" / "03" / item.name, "rb")

        def reopen(self):
            pass

    plan = analyze_device(Phone(), tmp_path)
    assert len(plan.pending) == len(orphans)  # only those need reading
    result = run_cable_import(Phone(), plan, tmp_path)
    assert result.already_had == len(orphans) and result.copied == 0

    healed = _inspect(tmp_path)
    assert len(healed["rows"]) == len(state["files"])
    assert len({path_key(p) for p, _s in healed["rows"]}) == len(healed["rows"])  # no double rows
    assert analyze_device(Phone(), tmp_path).pending == []


def test_a_healed_video_row_gets_the_hash_of_the_file_on_disk(tmp_path):
    """Found on a real iPhone: resuming after a kill recorded the phone's hash
    for a video whose landed copy had already had its container patched."""
    def video(stamp: bytes) -> bytes:
        return (16).to_bytes(4, "big") + b"moov" + stamp + (16).to_bytes(4, "big") + b"mdat" + b"frames!!"

    (tmp_path / "2026" / "03").mkdir(parents=True)
    landed = tmp_path / "2026" / "03" / "IMG_1.MOV"
    landed.write_bytes(video(b"\x01" * 8))
    original = video(b"\x02" * 8)

    class Phone:
        def list_items(self, on_progress=None, cancel=None):
            return [DeviceItem("IMG_1.MOV", "IMG_1.MOV", len(original), "2026-03-05T10:00:00")]

        def open_reader(self, item):
            import io

            return io.BytesIO(original)

        def reopen(self):
            pass

    run_cable_import(Phone(), analyze_device(Phone(), tmp_path), tmp_path)
    conn = sqlite3.connect(tmp_path / ".iphone_backup_index" / "index.sqlite")
    recorded = conn.execute("SELECT sha256 FROM backed_up_files").fetchone()[0]
    conn.close()
    assert recorded == hashlib.sha256(landed.read_bytes()).hexdigest()


def test_an_existing_row_with_different_name_case_is_not_recorded_twice(tmp_path):
    (tmp_path / "2026" / "03").mkdir(parents=True)
    video = tmp_path / "2026" / "03" / "IMG_1.mov"
    video.write_bytes(b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00" + b"\x00\x00\x00\x10mdat12345678")
    db = ManifestDB(tmp_path)
    db.record_file("IMG_1.mov", "stale-hash", "2026-03-05T10:00:00", str(video), video.stat().st_size)
    db.close()

    class Phone:
        def list_items(self, on_progress=None, cancel=None):
            return [DeviceItem("IMG_1.MOV", "IMG_1.MOV", video.stat().st_size + 2, "2026-03-05T10:00:00")]

        def open_reader(self, item):
            import io

            return io.BytesIO(b"\x00\x00\x00\x12ftypisom\x00\x00\x00\x00\x00\x00" + b"\x00\x00\x00\x10mdat12345678")

        def reopen(self):
            pass

    run_cable_import(Phone(), analyze_device(Phone(), tmp_path), tmp_path)
    assert len(_inspect_rows(tmp_path)) == 1


def _inspect_rows(dest: Path) -> list:
    conn = sqlite3.connect(dest / ".iphone_backup_index" / "index.sqlite")
    rows = conn.execute("SELECT dest_path FROM backed_up_files").fetchall()
    conn.close()
    return rows
