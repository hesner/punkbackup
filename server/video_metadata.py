"""Fixes a real, confirmed side effect of the video 0-byte retry (see
PLAN.md §5.1): when Shortcuts' "Encode Media" (Size: Passthrough) rebuilds
a video's container, it stamps the container's own `creation_time` fields
with the moment of the ENCODE (today), not the real capture date — even
though PunkBackup's own `taken_at` (captured independently from Shortcuts
before the video is ever touched) and folder placement are correct the
whole time. External tools that read the file's own embedded metadata
(PhotoPrism, Finder, etc.) show the wrong date as a result.

Patches the ISO-BMFF ("QuickTime"/MP4) container's `mvhd` box and every
`trak/mdia/mdhd` box's `creation_time`/`modification_time` fields in
place — no resize, no re-encode, nothing else in the file changes.
Confirmed via a byte-level diff against a real device video: exactly the
intended 8-byte-per-box fields change (64 bytes total on a 7-track,
18.5MB file), file size identical, full re-decode with ffmpeg clean, and
every other ffprobe-reported property byte-for-byte identical.

Box layout reference (ISO/IEC 14496-12):
    [4B size][4B type][payload...]
      size==0 -> box extends to EOF
      size==1 -> next 8B is the real 64-bit size ("largesize")
    mvhd/mdhd payload: [1B version][3B flags]
      version 0: [4B creation_time][4B modification_time][4B timescale]...
      version 1: [8B creation_time][8B modification_time][4B timescale]...
    Times are seconds since 1904-01-01T00:00:00Z (the "Mac epoch"), not
    the Unix epoch.
"""
from __future__ import annotations

import hashlib
import logging
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

logger = logging.getLogger("backup_engine")

MAC_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

# Extensions worth even attempting this on — the ISO-BMFF/QuickTime family.
# Trying on anything else (JPEG, PNG, HEIC...) would just fail the "moov
# box not found" check below, harmlessly, but there's no reason to open
# every photo file to find that out.
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}


def _to_mac_time(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((dt - MAC_EPOCH).total_seconds())


def _iter_boxes(f: BinaryIO, start: int, end: int) -> Iterator[tuple[str, int, int]]:
    """Yields (box_type, payload_start, payload_end) for each direct
    child box in [start, end)."""
    pos = start
    while pos < end:
        f.seek(pos)
        header = f.read(8)
        if len(header) < 8:
            break
        size, box_type_bytes = struct.unpack(">I4s", header)
        box_type = box_type_bytes.decode("ascii", errors="replace")
        header_len = 8
        if size == 1:
            largesize_bytes = f.read(8)
            if len(largesize_bytes) < 8:
                break
            size = struct.unpack(">Q", largesize_bytes)[0]
            header_len = 16
        elif size == 0:
            size = end - pos
        if size < header_len:
            break  # malformed — bail rather than loop forever or read garbage
        yield box_type, pos + header_len, pos + size
        pos += size


def _patch_time_fields(f: BinaryIO, payload_start: int, mac_time: int) -> None:
    f.seek(payload_start)
    version_byte = f.read(1)
    if not version_byte:
        raise ValueError("empty mvhd/mdhd payload")
    version = version_byte[0]
    if version == 0:
        f.seek(payload_start + 4)
        f.write(struct.pack(">I", mac_time))
        f.seek(payload_start + 8)
        f.write(struct.pack(">I", mac_time))
    elif version == 1:
        f.seek(payload_start + 4)
        f.write(struct.pack(">Q", mac_time))
        f.seek(payload_start + 12)
        f.write(struct.pack(">Q", mac_time))
    else:
        raise ValueError(f"unexpected mvhd/mdhd version: {version}")


def fix_creation_time(path: Path, real_taken_at: datetime) -> bool:
    """Best-effort — never raises. Returns True if at least the mvhd box
    was found and patched, False otherwise (not a recognizable ISO-BMFF
    container, or anything unexpected about its structure). A False
    return, or any exception, must never affect the surrounding upload —
    this is a correctness nicety for external tools, not a guarantee this
    project makes about the file itself."""
    try:
        mac_time = _to_mac_time(real_taken_at)
        patched_any = False
        with open(path, "r+b") as f:
            file_size = f.seek(0, 2)
            moov = None
            for box_type, p_start, p_end in _iter_boxes(f, 0, file_size):
                if box_type == "moov":
                    moov = (p_start, p_end)
                    break
            if moov is None:
                return False
            moov_start, moov_end = moov

            for box_type, p_start, p_end in _iter_boxes(f, moov_start, moov_end):
                if box_type == "mvhd":
                    _patch_time_fields(f, p_start, mac_time)
                    patched_any = True
                elif box_type == "trak":
                    for t_type, t_start, t_end in _iter_boxes(f, p_start, p_end):
                        if t_type != "mdia":
                            continue
                        for m_type, m_start, m_end in _iter_boxes(f, t_start, t_end):
                            if m_type == "mdhd":
                                _patch_time_fields(f, m_start, mac_time)
                                patched_any = True
        return patched_any
    except Exception as exc:
        logger.warning("Could not fix video creation_time for %s: %s", path, exc)
        return False


def content_signature(path: Path) -> Optional[str]:
    """sha256 of just the file's `mdat` box(es) — the actual audio/video
    sample data — ignoring the entire surrounding container (ftyp/moov,
    every timestamp field anywhere inside it) . i.e. "same video content,
    regardless of what Encode Media last re-stamped in the container".

    This is deliberately NOT "hash everything except mvhd/mdhd's
    creation_time/modification_time": an earlier version of this function
    tried exactly that and still produced 55 distinct signatures for 55
    real duplicate copies of the same source video (2026-09-22) — Encode
    Media's passthrough re-encode rewrites more of `moov` than just those
    two fields (unidentified further — didn't matter once mdat-only
    comparison was tried). Real-evidence check on that same set of 54/55
    duplicates confirmed the fix that matters: `mdat` was 100% byte
    identical on every single pair, and every differing byte fell inside
    `moov` — so mdat-only comparison is both correct (an actual content
    change still changes mdat, see storage.py's tests) and robust to
    however much of the container Apple's encoder chooses to touch.

    Returns None for anything without a top-level `mdat` box (not a
    recognizable ISO-BMFF container, or unreadable) — callers must fall
    back to a plain content hash in that case, never treat None as a
    match."""
    try:
        hasher = hashlib.sha256()
        found_any = False
        with open(path, "rb") as f:
            file_size = f.seek(0, 2)
            for box_type, p_start, p_end in _iter_boxes(f, 0, file_size):
                if box_type != "mdat":
                    continue
                found_any = True
                f.seek(p_start)
                remaining = p_end - p_start
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    hasher.update(chunk)
                    remaining -= len(chunk)
        if not found_any:
            return None
        return hasher.hexdigest()
    except Exception as exc:
        logger.warning("Could not compute content_signature for %s: %s", path, exc)
        return None
