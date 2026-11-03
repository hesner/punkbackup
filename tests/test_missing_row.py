"""A whole file on disk without its row (a cut between the move and the commit):
/check asks for it again and /upload writes the row for the file already there,
so the mirror sees it too. See PLAN.md W6.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import hashlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import storage
from server.manifest_db import ManifestDB
from server.storage import BackupEngine
from tests.video_fixture import make_video

FRAMES = [bytes([i]) * (200 + i) for i in range(40)]
TAKEN_AT = "2026-03-05T10:00:00"


def _engine(dest: Path) -> BackupEngine:
    return BackupEngine(dest, ManifestDB(dest))


def _files(dest: Path) -> list[Path]:
    return [p for p in dest.rglob("*") if p.is_file() and ".iphone_backup_index" not in p.parts]


def _landed_without_row(dest: Path, name: str, data: bytes) -> Path:
    folder = dest / "2026" / "03"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return folder / name


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_photo_without_its_row_is_asked_for_again_and_gets_its_row(tmp_path):
    engine = _engine(tmp_path)
    landed = _landed_without_row(tmp_path, "IMG_1.HEIC", b"the photo")
    assert engine.check_exists("IMG_1.HEIC", TAKEN_AT) is False

    outcome = engine.process_upload("IMG_1.HEIC", io.BytesIO(b"the photo"), TAKEN_AT, None)

    assert outcome["status"] == "skipped_duplicate"
    assert _files(tmp_path) == [landed]
    assert engine.db.find_by_dest_path(str(landed))["sha256"] == _sha(landed)
    assert engine.check_exists("IMG_1.HEIC", TAKEN_AT) is True


def test_a_video_without_its_row_gets_it_when_the_shortcut_resends_a_reencoded_copy(tmp_path):
    samples = [bytes([i]) * 20 for i in range(30)]
    engine = _engine(tmp_path)
    landed = _landed_without_row(tmp_path, "IMG_2.MOV", make_video(FRAMES, audio=samples))
    before = landed.read_bytes()
    encoded = make_video(FRAMES, audio=samples[:-2], moov_first=True)  # what Encode Media sends
    assert engine.check_exists("IMG_2.MOV", TAKEN_AT) is False

    outcome = engine.process_upload("IMG_2.MOV", io.BytesIO(encoded), TAKEN_AT, None)

    assert outcome["status"] == "skipped_duplicate"
    assert _files(tmp_path) == [landed]
    assert landed.read_bytes() == before  # kept as it was
    assert engine.db.find_by_dest_path(str(landed))["sha256"] == _sha(landed)
    assert engine.check_exists("IMG_2.MOV", TAKEN_AT) is True


def test_a_different_file_put_there_by_hand_is_kept_and_not_asked_for_forever(tmp_path):
    engine = _engine(tmp_path)
    by_hand = _landed_without_row(tmp_path, "IMG_3.HEIC", b"someone else's photo")

    first = engine.process_upload("IMG_3.HEIC", io.BytesIO(b"the real photo"), TAKEN_AT, None)
    assert first["status"] == "conflict_kept_both"
    assert by_hand.read_bytes() == b"someone else's photo"
    assert engine.check_exists("IMG_3.HEIC", TAKEN_AT) is True

    again = engine.process_upload("IMG_3.HEIC", io.BytesIO(b"the real photo"), TAKEN_AT, None)
    assert again["status"] == "skipped_duplicate"
    assert len(_files(tmp_path)) == 2


def test_a_row_under_another_drive_letter_or_name_case_still_counts(tmp_path):
    engine = _engine(tmp_path)
    landed = _landed_without_row(tmp_path, "IMG_4.HEIC", b"photo")
    engine.db.record_file("IMG_4.heic", _sha(landed), TAKEN_AT, r"Z:\old\2026\03\img_4.heic", 5)

    assert engine.check_exists("IMG_4.HEIC", TAKEN_AT) is True
    engine.process_upload("IMG_4.HEIC", io.BytesIO(b"photo"), TAKEN_AT, None)
    assert len(engine.db._conn.execute("SELECT * FROM backed_up_files").fetchall()) == 1


def test_a_video_reaches_its_folder_with_its_date_already_fixed(tmp_path, monkeypatch):
    """A cut right after the move can't leave a video with Encode Media's date:
    the patch happens in staging, so the moved file is already what gets recorded."""
    moved = []
    real_move = storage.shutil.move
    monkeypatch.setattr(storage.shutil, "move", lambda src, dst: (moved.append(_sha(Path(src))), real_move(src, dst))[1])
    engine = _engine(tmp_path)
    sent = make_video(FRAMES)

    outcome = engine.process_upload("IMG_5.MOV", io.BytesIO(sent), TAKEN_AT, None)

    recorded = engine.db.find_by_dest_path(outcome["dest_path"])["sha256"]
    assert recorded != hashlib.sha256(sent).hexdigest()  # the date really was patched
    assert moved == [recorded]
