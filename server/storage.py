"""Core backup engine: where an incoming file ends up and what happens on
a name collision.

Rules (see PLAN.md section 5.1):
  1. Same filename + same content (sha256)  -> no-op, already backed up.
  2. Same filename + different content       -> keep BOTH, never overwrite.
  3. New filename                            -> copy normally.
Files are organized as ``<dest>/<YYYY>/<MM>/<filename>`` using the photo's
"taken at" date supplied by the iPhone Shortcut (falls back to the server's
current date if missing/unparseable).

This is one-directional: the iPhone is only ever read from by the Shortcut
that calls this API; nothing here ever talks back to delete or modify
anything on the phone.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional

from PIL import Image
import pillow_heif

from .manifest_db import ManifestDB
from .video_metadata import VIDEO_EXTENSIONS, content_signature, fix_creation_time

pillow_heif.register_heif_opener()  # lets PIL.Image.open() read .heic/.heif too

CHUNK_SIZE = 1024 * 1024  # 1 MiB — keeps memory use flat regardless of file size

# The GUI attaches a queue-backed handler to this logger to show live
# activity to the user; it is equally usable headless (just prints/logs
# normally if nothing is attached).
logger = logging.getLogger("backup_engine")

# Sniffs the REAL file format from its own bytes — used only when the
# Shortcut sends a filename with no extension at all. Seen in practice
# (2026-09-17/18) for a handful of Photos items — always the same ones
# that also arrive with no `taken_at` (see PLAN.md §5.4) — where
# Shortcuts' own "File Extension" attribute comes back empty. Detecting
# from content instead of trusting the client is strictly more robust:
# it doesn't depend on any particular Shortcuts attribute being reliable,
# for this case or any future one. Never overrides an extension the
# client DID send, even if it looks wrong — only fills in a MISSING one.
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
]
_FTYP_BRAND_EXTENSIONS = {
    b"qt  ": ".mov",
    b"heic": ".heic",
    b"heix": ".heic",
    b"hevc": ".heic",
    b"hevx": ".heic",
    b"mif1": ".heic",
    b"msf1": ".heic",
}


def _detect_extension(staging_path: Path) -> Optional[str]:
    try:
        with open(staging_path, "rb") as f:
            head = f.read(16)
    except OSError:
        return None
    for signature, ext in _MAGIC_SIGNATURES:
        if head.startswith(signature):
            return ext
    if head[4:8] == b"ftyp":
        return _FTYP_BRAND_EXTENSIONS.get(head[8:12], ".mp4")  # any other brand: some MP4-family video
    return None


def _read_exif_taken_at(staging_path: Path) -> Optional[str]:
    """Best-effort fallback for when the Shortcut sends no `taken_at` at
    all — reads the real capture date straight from the file's own EXIF
    (DateTimeOriginal), independent of whatever Shortcuts reported. Only
    works for formats that carry EXIF (JPEG/HEIC); returns None for
    anything else (e.g. video) rather than guessing — same items this
    tends to affect are documented in PLAN.md §5.4."""
    try:
        with Image.open(staging_path) as img:
            exif = img.getexif()
        raw = exif.get(36867) or exif.get(306)  # DateTimeOriginal, else DateTime
        if not raw:
            return None
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        return None


class BackupEngine:
    def __init__(self, dest_root: Path, db: ManifestDB):
        self.dest_root = Path(dest_root)
        self.db = db
        self.staging_dir = self.db.index_dir / "staging"
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _year_month_dir(self, taken_at: Optional[str]) -> Path:
        dt = None
        if taken_at:
            try:
                dt = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if dt is None:
            dt = datetime.now(timezone.utc)
        return self.dest_root / f"{dt.year:04d}" / f"{dt.month:02d}"

    def check_exists(self, filename: str, taken_at: Optional[str]) -> bool:
        """Lightweight pre-check used by /check: does the CURRENT destination
        already have a file at this exact name+date path? No file bytes are
        transferred for this, so switching to a different destination/USB
        naturally makes everything "missing" again instead of trusting a
        marker left on the phone (see PLAN.md section 5).

        This only checks presence by path, not content — iOS Shortcuts has
        no reliable way to hand over a raw byte count (its "File Size"
        property is always a locale-formatted string like "1,2 MB", which
        can't be parsed as a plain integer), so the cheap check trades a
        little precision for something the Shortcut can actually send.
        /upload remains the authority: it always hashes the real content
        and keeps both files on a genuine name+content conflict, so nothing
        is ever silently overwritten even if this cheap check is wrong."""
        safe_name = Path(filename).name
        candidate_path = self._year_month_dir(taken_at) / safe_name
        if candidate_path.exists():
            return True
        if not Path(safe_name).suffix:
            # The Shortcut sent no extension — if the server detected one
            # from content on a PRIOR /upload of this exact name (see
            # finalize_upload's _detect_extension), the path above can
            # never match again since the extension is never reflected
            # back to what the Shortcut sends. Fall back to the exact
            # original name this item resolved to last time it was really
            # uploaded — see manifest_db.find_by_original_filename's
            # docstring and PLAN.md section 5.4.2.
            return self.db.find_by_original_filename(safe_name) is not None
        return False

    def stage_bytes(self, src_file: BinaryIO) -> tuple[Path, str, int]:
        """Phase 1 of receiving an upload: stream `src_file` (anything with
        a sync .read(n)) into a staging file while hashing it. Split out
        from finalize_upload() so the API layer can also drive this from a
        raw async request body (see app.py's /upload — iOS Shortcuts has no
        reliable way to attach a Photos item as a real multipart file part,
        so the API accepts the file as the raw POST body instead)."""
        staging_path = self.staging_dir / f"{uuid.uuid4().hex}.part"
        hasher = hashlib.sha256()
        size = 0
        try:
            with open(staging_path, "wb") as out:
                while True:
                    chunk = src_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
        except Exception:
            # A failure partway through (e.g. disk full) can leave a
            # partial file behind — clean it up rather than leaking it into
            # the staging dir forever (a new UUID is used on every attempt,
            # so nothing here is ever overwritten/retried in place).
            staging_path.unlink(missing_ok=True)
            raise
        return staging_path, hasher.hexdigest(), size

    def process_upload(
        self,
        filename: str,
        src_file: BinaryIO,
        taken_at: Optional[str],
        run_id: Optional[str],
    ) -> dict:
        """Blocking. The API layer must call this via a thread pool so it
        never stalls the async event loop on large video files."""
        try:
            staging_path, sha256, size = self.stage_bytes(src_file)
        except OSError as exc:
            # Most common real cause: the destination drive filled up
            # mid-write (ENOSPC) — see app.py's /upload for why this must
            # never be recorded as backed up (so /check keeps reporting it
            # missing and a later run retries once space is freed).
            self.db.bump_run(run_id, "files_error")
            logger.error("x %s: could not write to disk (%s), requesting the file again", filename, exc)
            raise ValueError(f'"{filename}" could not be saved (disk write failed: {exc}) — will retry on the next run.') from exc
        except Exception as exc:
            self.db.bump_run(run_id, "files_error")
            logger.error("ERROR receiving %s: %s", filename, exc)
            raise
        return self.finalize_upload(filename, staging_path, sha256, size, taken_at, run_id)

    def finalize_upload(
        self,
        filename: str,
        staging_path: Path,
        sha256: str,
        size: int,
        taken_at: Optional[str],
        run_id: Optional[str],
    ) -> dict:
        """Phase 2: staging_path already holds the full, hashed content —
        decide where it lands (new / duplicate-skip / keep-both-conflict)."""
        if size == 0:
            # A genuinely empty upload — seen in practice when Shortcuts runs
            # in the background and can't fetch a large video's full bytes
            # from iCloud in time (Content-Length: 0 on the wire, confirmed
            # via a debug capture). Refusing to record this as "backed up"
            # is what makes the system self-healing: /check keeps reporting
            # it as missing, so a later run (ideally in the foreground, with
            # the asset already downloaded) retries it automatically instead
            # of the empty file silently poisoning the record forever.
            staging_path.unlink(missing_ok=True)
            self.db.mark_error(run_id, Path(filename).name)
            logger.error("x %s: received 0 bytes, requesting the file again", filename)
            raise ValueError(f'"{filename}" arrived empty (0 bytes) — not recorded, will retry on the next run.')

        safe_name = Path(filename).name  # strip any path components — never trust client paths
        original_name = safe_name  # pre-extension-fix name — mark_error() on a 0-byte retry used this
        if not Path(safe_name).suffix:
            detected_ext = _detect_extension(staging_path)
            if detected_ext:
                logger.warning("%s: no extension from the Shortcut, detected %s from content", safe_name, detected_ext)
                safe_name = f"{safe_name}{detected_ext}"
        if not taken_at:
            taken_at = _read_exif_taken_at(staging_path)

        target_dir = self._year_month_dir(taken_at)
        target_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = target_dir / safe_name

        try:
            if candidate_path.exists():
                if self._hash_existing(candidate_path) == sha256:
                    if original_name != safe_name:
                        self.db.backfill_original_filename(str(candidate_path), original_name)
                    self._resolve_error_both(run_id, safe_name, original_name)
                    self.db.bump_run(run_id, "files_skipped")
                    logger.info("= %s already backed up, skipped", safe_name)
                    return {"status": "skipped_duplicate", "dest_path": str(candidate_path)}

                if candidate_path.suffix.lower() in VIDEO_EXTENSIONS:
                    # Raw sha256 differs, but Shortcuts' "Encode Media" 0-byte
                    # retry re-stamps the container's own metadata on every
                    # pass over the SAME source video, changing its hash every
                    # time with no real content change (confirmed 2026-09-22
                    # against 54 real duplicate copies — see
                    # video_metadata.content_signature's docstring). Compare
                    # by actual sample data (mdat) before concluding
                    # "different content, keep both".
                    existing_sig = content_signature(candidate_path)
                    if existing_sig is not None and existing_sig == content_signature(staging_path):
                        if original_name != safe_name:
                            self.db.backfill_original_filename(str(candidate_path), original_name)
                        self._resolve_error_both(run_id, safe_name, original_name)
                        self.db.bump_run(run_id, "files_skipped")
                        logger.info("= %s already backed up (re-encoded copy, content unchanged), skipped", safe_name)
                        return {"status": "skipped_duplicate", "dest_path": str(candidate_path)}

                final_path = self._next_conflict_name(target_dir, candidate_path)
                shutil.move(str(staging_path), str(final_path))
                self.db.record_file(safe_name, sha256, taken_at, str(final_path), size, original_name)
                self._resolve_error_both(run_id, safe_name, original_name)
                self.db.bump_run(run_id, "files_conflict")
                self._maybe_fix_video_creation_time(final_path, taken_at)
                logger.warning("! %s: name conflict, kept both -> %s", safe_name, final_path.name)
                return {"status": "conflict_kept_both", "dest_path": str(final_path)}

            shutil.move(str(staging_path), str(candidate_path))
            self.db.record_file(safe_name, sha256, taken_at, str(candidate_path), size, original_name)
            self._resolve_error_both(run_id, safe_name, original_name)
            self.db.bump_run(run_id, "files_new")
            self._maybe_fix_video_creation_time(candidate_path, taken_at)
            logger.info("+ %s backed up (%.1f MB)", safe_name, size / (1024 * 1024))
            return {"status": "new", "dest_path": str(candidate_path)}
        finally:
            staging_path.unlink(missing_ok=True)  # no-op once moved

    def _maybe_fix_video_creation_time(self, path: Path, taken_at: Optional[str]) -> None:
        """Best-effort — see video_metadata.py's docstring for why this
        exists. Only worth attempting for video containers, and only when
        a real taken_at is known (writing "now" into the file would just
        recreate the same problem for a different reason)."""
        if not taken_at or path.suffix.lower() not in VIDEO_EXTENSIONS:
            return
        try:
            dt = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except ValueError:
            return
        fix_creation_time(path, dt)

    def _resolve_error_both(self, run_id: Optional[str], safe_name: str, original_name: str) -> None:
        """resolve_error() under both names a same-run mark_error() could
        have used — a 0-byte retry marks the error under the name it was
        UPLOADED with, which may be the pre-extension-detection name (see
        finalize_upload's `original_name`)."""
        self.db.resolve_error(run_id, safe_name)
        if original_name != safe_name:
            self.db.resolve_error(run_id, original_name)

    @staticmethod
    def _next_conflict_name(target_dir: Path, candidate_path: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        stem, suffix = candidate_path.stem, candidate_path.suffix
        final_path = target_dir / f"{stem}__{stamp}{suffix}"
        n = 1
        while final_path.exists():
            final_path = target_dir / f"{stem}__{stamp}-{n}{suffix}"
            n += 1
        return final_path

    @staticmethod
    def _hash_existing(path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
