"""Videos whose audio has one size for every sample (no size table in stsz), v1.8.11.

A real 29.6 MB MP4 (not from the camera) came like this. The old reader ignored
that size and took the bytes after the box as a table, so same_video hashed
thousands of "samples" of up to 4 GB and a cable backup sat on that one file for
hours, at full CPU, without moving on."""
import io
import struct
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.manifest_db import ManifestDB
from server.storage import BackupEngine
from server.video_metadata import _box, _track_samples, _tracks, same_video
from tests.video_fixture import make_video

FRAMES = [bytes([i]) * (200 + i) for i in range(40)]
AUDIO = [bytes([i]) * 24 for i in range(30)]  # every sample 24 bytes, as the stsz box says


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_the_same_video_with_constant_size_audio_is_recognized(tmp_path):
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=AUDIO, constant_audio_size=True))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=AUDIO, constant_audio_size=True, moov_first=True))
    assert same_video(a, b) is True


def test_constant_size_audio_that_was_replaced_is_a_different_video(tmp_path):
    replaced = [bytes([100 + i]) * 24 for i in range(30)]
    a = _write(tmp_path, "a.mp4", make_video(FRAMES, audio=AUDIO, constant_audio_size=True))
    b = _write(tmp_path, "b.mp4", make_video(FRAMES, audio=replaced, constant_audio_size=True))
    assert same_video(a, b) is False


def test_the_engine_doesnt_store_it_twice(tmp_path):
    engine = BackupEngine(tmp_path, ManifestDB(tmp_path))
    engine.process_upload("VQED0424.MP4", io.BytesIO(make_video(FRAMES, audio=AUDIO, constant_audio_size=True)),
                          "2026-11-18T11:12:00", None)
    encoded = make_video(FRAMES, audio=AUDIO, constant_audio_size=True, moov_first=True)

    outcome = engine.process_upload("782a91af.mp4", io.BytesIO(encoded), "2026-11-18T11:12:00", None)

    assert outcome["status"] == "skipped_duplicate"


def _with_audio_sample_size(data: bytes, new_size: int) -> bytes:
    """The video with its audio stsz rewritten to claim `new_size` bytes per sample."""
    path = io.BytesIO(data)
    stbl = _tracks(path, b"soun")[0]
    stsz_start = _box(path, *stbl, "stsz")[0]
    return data[:stsz_start + 4] + struct.pack(">I", new_size) + data[stsz_start + 8:]


def test_a_sample_past_the_end_of_the_file_is_refused_without_reading_it(tmp_path):
    data = _with_audio_sample_size(make_video(FRAMES, audio=AUDIO, constant_audio_size=True), 0xFFFFFFF0)
    path = _write(tmp_path, "broken.mp4", data)
    with open(path, "rb") as f:
        with pytest.raises(ValueError):
            _track_samples(f, _tracks(f, b"soun")[0])
    started = time.monotonic()
    assert same_video(path, path) is False
    assert time.monotonic() - started < 2


def test_a_size_table_longer_than_its_box_is_refused(tmp_path):
    data = make_video(FRAMES, audio=AUDIO)
    f = io.BytesIO(data)
    stsz_start = _box(f, *_tracks(f, b"soun")[0], "stsz")[0]
    count_at = stsz_start + 8
    data = data[:count_at] + struct.pack(">I", 100_000) + data[count_at + 4:]  # claims far more than it holds
    path = _write(tmp_path, "long_table.mp4", data)
    with open(path, "rb") as f:
        with pytest.raises(ValueError):
            _track_samples(f, _tracks(f, b"soun")[0])
    assert same_video(path, path) is False
