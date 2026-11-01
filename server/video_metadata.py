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
from collections import Counter
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

MIN_FINGERPRINT_FRAMES = 10  # a clip this short has too little in it to tell two apart
# How far two copies of one video can differ in total size, as a cheap first check.
MAX_SIZE_RATIO_SAME_VIDEO = 1.02
# Encoders stamp a byte or two into the first frame: 7 pairs of the same video in
# a real library differed by 1-2 bytes there and nowhere else.
MAX_FIRST_FRAME_BYTES_DIFFERING = 16
MAX_AUDIO_SAMPLES_TRIMMED = 8  # 2 in the real pairs measured
MIN_AUDIO_SAMPLES_SHARED = 0.98  # the lowest real pair was 0.991


def _to_mac_time(dt: datetime) -> int:
    """A date with no zone is local time: that's what the Shortcut sends. These
    fields are UTC, so storing it unconverted showed every video 5 hours early in
    other apps from Colombia (found 2026-10-31, PLAN.md W1). A video recorded in
    another time zone comes out off by the difference, since the date doesn't say."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
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


def _box(f: BinaryIO, start: int, end: int, name: str) -> Optional[tuple[int, int]]:
    for box, box_start, box_end in _iter_boxes(f, start, end):
        if box == name:
            return box_start, box_end
    return None


def _tracks(f: BinaryIO, handler: bytes) -> list[tuple[int, int]]:
    """(start, end) of the sample table of each track of this kind."""
    size = f.seek(0, 2)
    moov = _box(f, 0, size, "moov")
    if moov is None:
        return []
    tables = []
    for box, trak_start, trak_end in _iter_boxes(f, *moov):
        if box != "trak":
            continue
        mdia = _box(f, trak_start, trak_end, "mdia")
        hdlr = _box(f, *mdia, "hdlr") if mdia else None
        if hdlr is None:
            continue
        f.seek(hdlr[0] + 8)
        if f.read(4) == handler:
            tables.append(_box(f, *_box(f, *mdia, "minf"), "stbl"))
    return tables


def video_fingerprint(path: Path) -> Optional[str]:
    """Identifies a video across containers: a hash of how many bytes each video
    frame takes. Encode Media rewrites the container and even changes `mdat` (it
    interleaves samples differently, and sometimes trims audio), so
    content_signature misses a video that came by cable against the same one sent
    by the Shortcut — 9 of 9 on a real iPhone, 2026-10-30. Frame sizes survive.

    Only a filter, never proof: it can't see a damaged copy, whose frames keep
    their sizes (real case, PLAN.md section 26.2). same_video() is the proof.

    Reads only `moov`, not the video, so it stays cheap on a USB drive. Returns
    None when it can't identify the video with confidence (not a video, constant
    frame size, too few frames); a caller must never treat None as a match."""
    try:
        with open(path, "rb") as f:
            tables = []
            for stbl in _tracks(f, b"vide"):
                f.seek(_box(f, *stbl, "stsz")[0])
                _, sample_size, count = struct.unpack(">III", f.read(12))
                if sample_size != 0:
                    return None
                tables.append(struct.pack(">I", count) + f.read(4 * count))
    except Exception:  # whatever a malformed file does, it just can't be identified
        return None
    hasher = hashlib.sha256()
    frames = 0
    for table in sorted(tables):
        count = struct.unpack(">I", table[:4])[0]
        frames = max(frames, count)
        hasher.update(table)
    return hasher.hexdigest() if frames >= MIN_FINGERPRINT_FRAMES else None


def _track_samples(f: BinaryIO, stbl: tuple[int, int]) -> tuple[tuple[int, ...], list[int]]:
    """(sample sizes, sample offsets), from a track's sample tables."""
    f.seek(_box(f, *stbl, "stsz")[0] + 4)
    _, count = struct.unpack(">II", f.read(8))
    sizes = struct.unpack(f">{count}I", f.read(4 * count))

    f.seek(_box(f, *stbl, "stsc")[0] + 4)
    entries = struct.unpack(">I", f.read(4))[0]
    stsc = [struct.unpack(">III", f.read(12)) for _ in range(entries)]

    stco = _box(f, *stbl, "stco")
    f.seek((stco or _box(f, *stbl, "co64"))[0] + 4)
    chunks_count = struct.unpack(">I", f.read(4))[0]
    fmt, width = ("I", 4) if stco else ("Q", 8)
    chunks = struct.unpack(f">{chunks_count}{fmt}", f.read(width * chunks_count))

    offsets: list[int] = []
    for number, chunk_offset in enumerate(chunks, start=1):
        per_chunk = next(entry[1] for entry in reversed(stsc) if entry[0] <= number)
        position = chunk_offset
        for _ in range(per_chunk):
            if len(offsets) == count:
                break
            sample_size = sizes[len(offsets)]
            offsets.append(position)
            position += sample_size
    return sizes, offsets


def _audio_sample_hashes(f: BinaryIO, stbl: tuple[int, int]) -> list[bytes]:
    hashes = []
    sizes, offsets = _track_samples(f, stbl)
    for length, offset in zip(sizes, offsets):
        f.seek(offset)
        hashes.append(hashlib.sha1(f.read(length)).digest())
    return hashes


def _same_audio(a: BinaryIO, b: BinaryIO) -> bool:
    """Encode Media drops a couple of audio samples and can change one more, so an
    exact comparison would miss real copies: across 9 real pairs of a video sent by
    cable and by the Shortcut, 99.1-100% of the samples matched, with 0-2 fewer.
    Muted or replaced audio shares almost none, and that's a different video even
    with identical frames, so both copies stay."""
    tracks_a = sorted((_audio_sample_hashes(a, stbl) for stbl in _tracks(a, b"soun")), key=len)
    tracks_b = sorted((_audio_sample_hashes(b, stbl) for stbl in _tracks(b, b"soun")), key=len)
    if len(tracks_a) != len(tracks_b):
        return False
    for track_a, track_b in zip(tracks_a, tracks_b):
        short, long = sorted((track_a, track_b), key=len)
        if len(long) - len(short) > MAX_AUDIO_SAMPLES_TRIMMED:
            return False
        available = Counter(long)
        shared = 0
        for sample in short:
            if available[sample] > 0:
                available[sample] -= 1
                shared += 1
        if shared < len(short) * MIN_AUDIO_SAMPLES_SHARED:
            return False
    return True


def same_video(first: Path, second: Path) -> bool:
    """Compares the actual frames of two videos, in whatever order their
    containers keep them. Reads both completely, which is fine: a caller only gets
    here after video_fingerprint matched, and then the file is never read again.

    The price of being wrong is a video that looks backed up and isn't, so anything
    unclear is "not the same": then both copies are kept. Never raises."""
    try:
        size_a, size_b = first.stat().st_size, second.stat().st_size
        if max(size_a, size_b) > min(size_a, size_b) * MAX_SIZE_RATIO_SAME_VIDEO:
            return False
        with open(first, "rb") as a, open(second, "rb") as b:
            tracks_a = sorted((_track_samples(a, stbl) for stbl in _tracks(a, b"vide")), key=lambda t: t[0])
            tracks_b = sorted((_track_samples(b, stbl) for stbl in _tracks(b, b"vide")), key=lambda t: t[0])
            if not tracks_a or len(tracks_a) != len(tracks_b):
                return False
            for (sizes, offsets_a), (sizes_b, offsets_b) in zip(tracks_a, tracks_b):
                if sizes != sizes_b or len(offsets_a) != len(sizes) or len(offsets_b) != len(sizes):
                    return False
                for index, (length, offset_a, offset_b) in enumerate(zip(sizes, offsets_a, offsets_b)):
                    a.seek(offset_a)
                    b.seek(offset_b)
                    frame_a, frame_b = a.read(length), b.read(length)
                    if len(frame_a) != length or len(frame_b) != length:
                        return False
                    if frame_a == frame_b:
                        continue
                    differing = sum(x != y for x, y in zip(frame_a, frame_b))
                    if index != 0 or differing > MAX_FIRST_FRAME_BYTES_DIFFERING:
                        return False
            return _same_audio(a, b)
    except Exception as exc:
        logger.warning("Could not compare videos %s and %s: %s", first, second, exc)
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
