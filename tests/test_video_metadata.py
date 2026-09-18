"""Tests for video_metadata.py's in-place mvhd/mdhd creation_time patch.

Uses a small SYNTHETIC ISO-BMFF file built by hand (not a real video —
no large binary fixture, no personal data) that mimics just enough of a
real .mov's box structure (ftyp/moov/mvhd/trak/mdia/mdhd/mdat) to exercise
the real parsing and patching logic end to end.

Real-device validation (not re-run here, see PLAN.md): patching an actual
18.5MB iPhone video changed exactly the intended 64 bytes (8 boxes × 8
bytes), left the file size and every other ffprobe-reported property
byte-for-byte identical, and the result still decoded cleanly start to
finish.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.video_metadata import MAC_EPOCH, fix_creation_time


def _box(box_type: str, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type.encode("ascii")) + payload


def _mvhd_or_mdhd_payload(version: int, creation: int, modification: int) -> bytes:
    if version == 0:
        return struct.pack(">B3sII", 0, b"\x00\x00\x00", creation, modification) + b"\x00" * 20
    return struct.pack(">B3sQQ", 1, b"\x00\x00\x00", creation, modification) + b"\x00" * 20


def _build_synthetic_mov(mvhd_version: int = 0, mdhd_version: int = 0) -> bytes:
    mvhd = _box("mvhd", _mvhd_or_mdhd_payload(mvhd_version, 1000, 1000))
    mdhd = _box("mdhd", _mvhd_or_mdhd_payload(mdhd_version, 2000, 2000))
    mdia = _box("mdia", mdhd)
    trak = _box("trak", mdia)
    moov = _box("moov", mvhd + trak)
    ftyp = _box("ftyp", b"qt  " + b"\x00" * 12)
    mdat = _box("mdat", b"\xde\xad\xbe\xef" * 8)  # stand-in "media data" bytes
    return ftyp + moov + mdat


def test_fix_creation_time_patches_mvhd_and_mdhd(tmp_path):
    path = tmp_path / "synthetic.mov"
    path.write_bytes(_build_synthetic_mov())
    original_bytes = path.read_bytes()

    target = datetime(2025, 10, 13, 19, 6, 0, tzinfo=timezone.utc)
    assert fix_creation_time(path, target) is True

    patched_bytes = path.read_bytes()
    assert len(patched_bytes) == len(original_bytes)  # no resize

    expected_mac_time = int((target - MAC_EPOCH).total_seconds())

    # mvhd payload starts right after "ftyp" box (8 + 4 + 12 = 24 bytes)
    # + moov header (8 bytes) + mvhd header (8 bytes).
    ftyp_size = 8 + 16
    moov_header = 8
    mvhd_header = 8
    mvhd_payload_start = ftyp_size + moov_header + mvhd_header
    creation, modification = struct.unpack(
        ">II", patched_bytes[mvhd_payload_start + 4 : mvhd_payload_start + 12]
    )
    assert creation == expected_mac_time
    assert modification == expected_mac_time

    # Everything outside the two patched 8-byte windows must be untouched.
    diff_positions = [i for i in range(len(original_bytes)) if original_bytes[i] != patched_bytes[i]]
    assert len(diff_positions) == 16  # 8 bytes in mvhd + 8 bytes in mdhd


def test_fix_creation_time_handles_version_1_boxes(tmp_path):
    path = tmp_path / "synthetic_v1.mov"
    path.write_bytes(_build_synthetic_mov(mvhd_version=1, mdhd_version=1))

    target = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert fix_creation_time(path, target) is True

    expected_mac_time = int((target - MAC_EPOCH).total_seconds())
    ftyp_size, moov_header, mvhd_header = 24, 8, 8
    mvhd_payload_start = ftyp_size + moov_header + mvhd_header
    data = path.read_bytes()
    creation, modification = struct.unpack(
        ">QQ", data[mvhd_payload_start + 4 : mvhd_payload_start + 20]
    )
    assert creation == expected_mac_time
    assert modification == expected_mac_time


def test_fix_creation_time_returns_false_for_non_iso_bmff_file(tmp_path):
    path = tmp_path / "not_a_video.mov"
    path.write_bytes(b"\xff\xd8\xff\xe0plain jpeg-like bytes, no moov box here")
    original = path.read_bytes()

    assert fix_creation_time(path, datetime.now(timezone.utc)) is False
    assert path.read_bytes() == original  # untouched


def test_fix_creation_time_never_raises_on_garbage(tmp_path):
    path = tmp_path / "garbage.mov"
    path.write_bytes(b"\x00" * 4)  # truncated/malformed — shorter than one box header
    assert fix_creation_time(path, datetime.now(timezone.utc)) is False
