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

from .manifest_db import ManifestDB

CHUNK_SIZE = 1024 * 1024  # 1 MiB — keeps memory use flat regardless of file size

# The GUI attaches a queue-backed handler to this logger to show live
# activity to the user; it is equally usable headless (just prints/logs
# normally if nothing is attached).
logger = logging.getLogger("backup_engine")


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
        return candidate_path.exists()

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
        with open(staging_path, "wb") as out:
            while True:
                chunk = src_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                out.write(chunk)
                size += len(chunk)
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
        target_dir = self._year_month_dir(taken_at)
        target_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = target_dir / safe_name

        try:
            if candidate_path.exists():
                if self._hash_existing(candidate_path) == sha256:
                    self.db.resolve_error(run_id, safe_name)
                    self.db.bump_run(run_id, "files_skipped")
                    logger.info("= %s already backed up, skipped", safe_name)
                    return {"status": "skipped_duplicate", "dest_path": str(candidate_path)}

                final_path = self._next_conflict_name(target_dir, candidate_path)
                shutil.move(str(staging_path), str(final_path))
                self.db.record_file(safe_name, sha256, taken_at, str(final_path), size)
                self.db.resolve_error(run_id, safe_name)
                self.db.bump_run(run_id, "files_conflict")
                logger.warning("! %s: name conflict, kept both -> %s", safe_name, final_path.name)
                return {"status": "conflict_kept_both", "dest_path": str(final_path)}

            shutil.move(str(staging_path), str(candidate_path))
            self.db.record_file(safe_name, sha256, taken_at, str(candidate_path), size)
            self.db.resolve_error(run_id, safe_name)
            self.db.bump_run(run_id, "files_new")
            logger.info("+ %s backed up (%.1f MB)", safe_name, size / (1024 * 1024))
            return {"status": "new", "dest_path": str(candidate_path)}
        finally:
            staging_path.unlink(missing_ok=True)  # no-op once moved

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
