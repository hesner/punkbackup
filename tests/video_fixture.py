"""Builds a minimal real ISO-BMFF video: enough sample tables for the fingerprint
and for reading frames back, with the layout options Encode Media changes."""
import struct


def _box(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + name + payload


def _track(handler: bytes, sizes: list[int], offset: int) -> bytes:
    stsz = _box(b"stsz", struct.pack(">III", 0, 0, len(sizes)) + b"".join(struct.pack(">I", s) for s in sizes))
    stsc = _box(b"stsc", struct.pack(">IIIII", 0, 1, 1, len(sizes), 1))
    stco = _box(b"stco", struct.pack(">III", 0, 1, offset))
    hdlr = _box(b"hdlr", b"\x00" * 8 + handler + b"\x00" * 12)
    return _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz + stsc + stco))))


def make_video(frames: list[bytes], audio=b"\x07" * 40, moov_first: bool = False, padding: int = 0) -> bytes:
    """`moov_first` and `padding` move everything around without touching a frame,
    as a remux does. `audio` is one sample or a list of them, stored after the video
    frames in `mdat`."""
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    sizes = [len(frame) for frame in frames]
    video = b"".join(frames)
    audio_samples = [audio] if isinstance(audio, bytes) else audio
    audio_bytes = b"".join(audio_samples)
    payload = b"\x00" * padding + video + audio_bytes

    def moov(data_start: int) -> bytes:
        video_track = _track(b"vide", sizes, data_start + padding)
        audio_track = _track(b"soun", [len(s) for s in audio_samples], data_start + padding + len(video))
        return _box(b"moov", video_track + audio_track)

    mdat = _box(b"mdat", payload)
    if moov_first:
        length = len(moov(0))
        return ftyp + moov(len(ftyp) + length + 8) + mdat
    return ftyp + mdat + moov(len(ftyp) + 8)
