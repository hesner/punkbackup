"""Cable and WiFi living together: each recognizes what the other already stored,
under any name. See PLAN.md section 26.2.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.manifest_db import ManifestDB
from server.storage import BackupEngine
from server.video_metadata import same_video, video_fingerprint
from tests.video_fixture import make_video

FRAMES = [bytes([i]) * (200 + i) for i in range(40)]


def _engine(dest: Path) -> BackupEngine:
    return BackupEngine(dest, ManifestDB(dest))


def _files(dest: Path) -> list[Path]:
    return [p for p in dest.rglob("*") if p.is_file() and ".iphone_backup_index" not in p.parts]


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_a_photo_stored_by_cable_isnt_stored_again_by_wifi_and_isnt_asked_for_again(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("DFTN0869.JPG", io.BytesIO(b"same photo"), "2026-09-14T18:08:17", None)

    assert engine.check_exists("ced9b322.jpeg", "2026-09-14T18:08:00") is False
    outcome = engine.process_upload("ced9b322.jpeg", io.BytesIO(b"same photo"), "2026-09-14T18:08:00", None)

    assert outcome["status"] == "skipped_duplicate"
    assert [p.name for p in _files(tmp_path)] == ["DFTN0869.JPG"]
    assert engine.check_exists("ced9b322.jpeg", "2026-09-14T18:08:00") is True


def test_a_video_reencoded_by_the_shortcut_is_recognized_in_both_directions(tmp_path):
    samples = [bytes([i]) * 20 for i in range(30)]
    original = make_video(FRAMES, audio=samples)
    encoded = make_video(FRAMES, audio=samples[:-2], moov_first=True)  # Encode Media trims 2 audio samples
    engine = _engine(tmp_path)
    engine.process_upload("RTER1485.MP4", io.BytesIO(original), "2026-10-30T18:34:50", None)

    outcome = engine.process_upload("f72673a9.mp4", io.BytesIO(encoded), "2026-10-30T18:20:00", None)

    assert outcome["status"] == "skipped_duplicate"
    assert len(_files(tmp_path)) == 1


def test_a_mislabeled_video_is_still_recognized(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("IMG_E2105.MOV", io.BytesIO(make_video(FRAMES)), "2026-10-30T21:59:55", None)
    outcome = engine.process_upload("IMG_2105.jpeg", io.BytesIO(make_video(FRAMES, moov_first=True)), "2026-10-30T21:59:00", None)
    assert outcome["status"] == "skipped_duplicate"


def test_audio_with_two_samples_dropped_and_one_changed_is_still_the_same_video(tmp_path):
    """The real shape: 160 samples vs 162, 99.4% shared."""
    samples = [bytes([i]) * 8 for i in range(160)]
    changed = [b"\xee" * 8, *samples[1:]]
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=[*samples, b"\xaa" * 8, b"\xbb" * 8]))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=changed, moov_first=True))
    assert same_video(a, b) is True


def test_audio_sharing_too_few_samples_is_a_different_video(tmp_path):
    samples = [bytes([i]) * 8 for i in range(100)]
    replaced = [*samples[:90], *[bytes([200 + i]) * 8 for i in range(10)]]
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=samples))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=replaced))
    assert same_video(a, b) is False


def test_same_name_with_different_content_still_keeps_both(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("IMG_1.HEIC", io.BytesIO(b"first"), "2026-03-05T10:00:00", None)
    outcome = engine.process_upload("IMG_1.HEIC", io.BytesIO(b"second"), "2026-03-05T10:00:00", None)
    assert outcome["status"] == "conflict_kept_both"
    assert len(_files(tmp_path)) == 2


def test_a_reused_camera_name_on_another_date_is_not_hidden_by_an_alias(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("KEEP.JPG", io.BytesIO(b"old photo"), "2018-01-01T10:00:00", None)
    engine.process_upload("IMG_0001.JPG", io.BytesIO(b"old photo"), "2018-01-01T10:00:00", None)
    assert engine.check_exists("IMG_0001.JPG", "2018-01-01T10:00:00") is True
    assert engine.check_exists("IMG_0001.JPG", "2026-10-30T10:00:00") is False


def test_a_new_photo_equal_to_a_deleted_file_is_stored_again(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("A.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    (tmp_path / "2026" / "03" / "A.JPG").unlink()
    outcome = engine.process_upload("B.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    assert outcome["status"] == "new"


def test_an_alias_to_a_deleted_file_asks_for_it_again(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("A.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    engine.process_upload("B.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    assert engine.check_exists("B.JPG", "2026-03-05T10:00:00") is True
    (tmp_path / "2026" / "03" / "A.JPG").unlink()
    assert engine.check_exists("B.JPG", "2026-03-05T10:00:00") is False


def test_a_duplicate_doesnt_create_an_empty_month_folder(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("A.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    engine.process_upload("B.JPG", io.BytesIO(b"photo"), "2025-01-05T10:00:00", None)
    assert not (tmp_path / "2025").exists()


def test_a_damaged_copy_with_the_same_frame_sizes_is_not_taken_for_the_video(tmp_path):
    """Real case: VIDEO0044, same size and frame sizes, 1,112 frames different."""
    damaged = [frame if i < 30 else b"\xff" * len(frame) for i, frame in enumerate(FRAMES)]
    good = _write(tmp_path, "good.mp4", make_video(FRAMES))
    bad = _write(tmp_path, "bad.mp4", make_video(damaged))
    assert video_fingerprint(good) == video_fingerprint(bad)
    assert same_video(good, bad) is False

    dest = tmp_path / "dest"
    engine = _engine(dest)
    engine.process_upload("VIDEO0044.mp4", io.BytesIO(bad.read_bytes()), "2015-03-01T10:00:00", None)
    outcome = engine.process_upload("other.mp4", io.BytesIO(good.read_bytes()), "2015-03-01T10:00:00", None)
    assert outcome["status"] == "new"


def test_a_byte_or_two_in_the_first_frame_is_still_the_same_video(tmp_path):
    """Real case: 7 pairs of the same video differed only there."""
    stamped = [b"\x99\x98" + FRAMES[0][2:], *FRAMES[1:]]
    assert same_video(_write(tmp_path, "a.mp4", make_video(FRAMES)), _write(tmp_path, "b.mp4", make_video(stamped)))


def test_a_small_difference_past_the_first_frame_is_a_different_video(tmp_path):
    changed = [*FRAMES[:5], b"\x99" + FRAMES[5][1:], *FRAMES[6:]]
    assert not same_video(_write(tmp_path, "a.mp4", make_video(FRAMES)), _write(tmp_path, "b.mp4", make_video(changed)))


def test_same_frames_with_clearly_different_audio_keeps_both(tmp_path):
    """Real case: 56 identical frames, 161 KB vs 178 KB."""
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=b"\x07" * 100))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=b"\x07" * 3000))
    assert video_fingerprint(a) == video_fingerprint(b)
    assert same_video(a, b) is False


def test_clips_too_short_to_identify_get_no_fingerprint(tmp_path):
    assert video_fingerprint(_write(tmp_path, "a.mp4", make_video(FRAMES[:5]))) is None


def test_files_that_arent_videos_get_no_fingerprint(tmp_path):
    assert video_fingerprint(_write(tmp_path, "a.jpg", b"\xff\xd8\xff" + b"x" * 500)) is None
    assert same_video(tmp_path / "missing.mp4", tmp_path / "also-missing.mp4") is False


def test_same_frames_with_replaced_audio_of_the_same_length_keeps_both(tmp_path):
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=b"\x07" * 100))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=b"\x08" * 100))
    assert same_video(a, b) is False


def test_a_damaged_copy_doesnt_make_a_good_upload_get_discarded(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("IMG_1.HEIC", io.BytesIO(b"the good photo"), "2024-05-05T10:00:00", None)
    (tmp_path / "2024" / "05" / "IMG_1.HEIC").write_bytes(b"the damaged!!!")

    same_name = engine.process_upload("IMG_1.HEIC", io.BytesIO(b"the good photo"), "2024-05-05T10:00:00", None)
    assert same_name["status"] == "conflict_kept_both"

    (tmp_path / "2024" / "05").joinpath(Path(same_name["dest_path"]).name).write_bytes(b"also damaged!!")
    other_name = engine.process_upload("abc.jpeg", io.BytesIO(b"the good photo"), "2024-05-05T10:00:00", None)
    assert other_name["status"] == "new"


def test_a_file_on_another_drive_doesnt_count_as_being_in_this_destination(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    engine = _engine(old)
    engine.process_upload("A.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    engine.db.close()
    (new / ".iphone_backup_index").mkdir(parents=True)
    (old / ".iphone_backup_index" / "index.sqlite").replace(new / ".iphone_backup_index" / "index.sqlite")

    outcome = _engine(new).process_upload("B.JPG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    assert outcome["status"] == "new"


def test_no_alias_is_recorded_without_a_date(tmp_path):
    engine = _engine(tmp_path)
    engine.process_upload("A.PNG", io.BytesIO(b"photo"), "2026-03-05T10:00:00", None)
    engine.process_upload("IMG_0001.PNG", io.BytesIO(b"photo"), None, None)
    assert engine.check_exists("IMG_0001.PNG", None) is False


def test_recent_staged_files_survive_and_old_ones_are_cleared(tmp_path):
    import os
    import time

    engine = _engine(tmp_path)
    recent, old = engine.staging_dir / "recent.part", engine.staging_dir / "old.part"
    recent.write_bytes(b"x")
    old.write_bytes(b"x")
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    engine.clear_staging()
    assert recent.exists() and not old.exists()


def test_a_malformed_container_gets_no_fingerprint_instead_of_an_error(tmp_path):
    huge = (1).to_bytes(4, "big") + b"moov" + (2**62).to_bytes(8, "big") + b"x" * 40
    assert video_fingerprint(_write(tmp_path, "a.mp4", huge)) is None
