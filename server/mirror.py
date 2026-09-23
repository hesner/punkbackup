"""Optional second copy (mirror): PC-side, one-directional sync of a
profile's destination folder onto a second folder/drive.

Deliberately has NO dependency on FastAPI or anything the iPhone/Shortcut
talks to — this is triggered only by a button in the GUI, so a bug or a
failing second drive here can never affect the real backup path. See
PLAN.md section 13 for the full design and rationale.

The mirror destination gets its OWN real ManifestDB, with the exact same
schema as any primary destination (the index lives inside the folder,
travels with the drive, same principle manifest_db.py already documents
for a primary destination). This is why "promoting" a second copy to
become a profile's new primary destination needs no special code at all
— see server/app.py::_engine_for and forget_profile(): pointing
destination_dir at this folder just opens the real index that's already
there.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .manifest_db import ManifestDB
from .storage import CHUNK_SIZE


@dataclass
class MirrorSyncResult:
    pending_before: int = 0
    copied: int = 0
    verify_failed: int = 0
    insufficient_space_warning: bool = False  # up-front disk_usage() check said "not enough room"
    # A per-file write failed and the sync halted early — could be a
    # genuinely full disk, OR the drive being disconnected mid-copy
    # (unplugged instead of safely ejected). Can't always tell which from
    # the OSError alone, so this is reported as one honest "something went
    # wrong, here's why" outcome rather than guessing.
    stopped_with_error: Optional[str] = None
    fatal_error: Optional[str] = None  # something unexpected broke the whole sync outright
    cancelled: bool = False  # user asked to stop (e.g. to safely eject the drive) -- not an error


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def sync_mirror(
    primary_root: Path,
    primary_db: ManifestDB,
    mirror_root: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    profile_label: str = "-",
) -> MirrorSyncResult:
    """Copies whatever primary_root/primary_db has that mirror_root
    doesn't yet, newest-first, verifying each copy by hash before
    recording it in the mirror's own index. Blocking — call this from a
    background thread, never the GUI's event-loop thread (same contract
    as ServerController.start_with_retry in server/runner.py).

    `cancel_event`: checked once per file, only BETWEEN files (never mid-
    copy or mid-verify) — e.g. so the user can safely eject the drive
    right after stopping, without any file left half-written. Whatever
    was already copied+verified before the cancellation stays valid.

    `profile_label`: passed straight to the mirror's own ManifestDB so any
    log line it emits (in practice just its own dangling-run reap notice,
    essentially never for a mirror) is tagged with the right profile —
    same purpose as every other ManifestDB/BackupEngine's profile_label.

    `progress_callback(done, total)`: CUMULATIVE against the mirror's
    whole target, not just this run's pending list -- resuming a mirror
    that already has 128 files reports "129 of X", never "1 of Y". A
    fresh "1/N"-looking readout on a resume looked like data had been
    lost even though nothing had (confirmed confusing on a real device,
    2026-09-21).

    Safe to interrupt at any point (drive unplugged, app closed, power
    loss): a file is only ever recorded in the mirror's index AFTER it's
    been copied AND verified, so the next call simply picks up whatever
    is still missing — no in-progress state is ever persisted or trusted.

    Never raises — every failure mode (drive full, drive yanked instead of
    safely ejected mid-copy, anything else unexpected) comes back as a
    field on the returned result instead. This matters specifically
    because the caller runs this in a background thread (see
    gui/main_window.py::_sync_profile_mirror): an exception escaping here
    would skip the self.after(...) callback that re-enables the "Sync
    now" button, leaving the GUI stuck showing "Syncing..." forever with
    no visible error — the same silent-failure shape already fixed
    elsewhere in this project (PLAN.md section 5.13, AGENTS.md lesson 11).
    """
    result = MirrorSyncResult()
    try:
        mirror_root.mkdir(parents=True, exist_ok=True)
        mirror_db = ManifestDB(mirror_root, profile_label=profile_label)
    except OSError as exc:
        result.fatal_error = str(exc)
        return result

    try:
        already_have = mirror_db.all_sha256s()
        baseline = len(already_have)  # already copied+verified, from this or an earlier run
        pending = [
            row for row in primary_db.iter_files_by_recency()
            if row["sha256"] not in already_have
        ]
        result.pending_before = len(pending)
        grand_total = baseline + len(pending)  # what progress_callback reports against
        if not pending:
            return result

        try:
            total_needed = sum(row["size_bytes"] for row in pending)
            free_bytes = shutil.disk_usage(mirror_root).free
            if total_needed > free_bytes:
                result.insufficient_space_warning = True
        except OSError:
            pass  # can't tell free space right now -- the copy loop below will surface any real problem

        for i, row in enumerate(pending, start=1):
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break

            rel = Path(row["dest_path"]).relative_to(primary_root)
            dest = mirror_root / rel
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(row["dest_path"], dest)
            except OSError as exc:
                # Drive full OR drive disconnected mid-copy (unplugged
                # instead of safely ejected) -- can't always tell which
                # from the OSError alone, so this is reported as one
                # honest "sync stopped, here's why" rather than a
                # guessed cause. Discard whatever partial bytes got
                # written; whatever's already recorded in the mirror's
                # own index stays valid regardless.
                try:
                    dest.unlink(missing_ok=True)
                except OSError:
                    pass  # the drive itself may be the thing that's gone -- nothing more to do
                result.stopped_with_error = str(exc)
                break

            try:
                verified = _hash_file(dest) == row["sha256"]
            except OSError as exc:
                # dest became unreadable right after being written (e.g.
                # the drive was pulled between the copy and the verify) --
                # same outcome as a failed copy above.
                result.stopped_with_error = str(exc)
                break

            if verified:
                mirror_db.record_file(
                    row["filename"], row["sha256"], row["taken_at"], str(dest), row["size_bytes"]
                )
                result.copied += 1
            else:
                # Corrupted copy (bad USB write, etc.) — never record it;
                # left for a retry on the next sync rather than aborting
                # the whole run over one bad file.
                try:
                    dest.unlink(missing_ok=True)
                except OSError:
                    pass
                result.verify_failed += 1

            if progress_callback is not None:
                # Cumulative, not "1 of {len(pending)}" -- resuming a mirror
                # that already has files must never look like it's starting
                # over from zero (confirmed confusing on a real device,
                # 2026-09-21: 128 already-verified files, next run's
                # progress showed "1/6885" with no visible sign of the 128
                # that were already safely there).
                progress_callback(baseline + i, grand_total)
    except Exception as exc:  # genuinely unexpected -- still report, never disappear silently
        result.fatal_error = str(exc)
    finally:
        try:
            mirror_db.close()
        except Exception:
            pass
    return result


def get_mirror_status(mirror_dir: str) -> Optional[dict]:
    """Cheap, side-effect-free status check for the GUI's periodic refresh
    (runs every ~1.5s per profile, see gui/main_window.py's
    _refresh_status_loop) — safe to call constantly. Deliberately never
    constructs ManifestDB() directly: that would re-run its reap logic
    and schema script on every tick for no reason (see AGENTS.md section
    6 on why ad-hoc status checks must use a read-only connection
    instead). Returns None if the folder isn't currently reachable (USB
    not connected) — that's the normal, expected state for this feature,
    not an error."""
    root = Path(mirror_dir)
    if not root.is_dir():
        return None
    try:
        usage = shutil.disk_usage(root)
        space = {"free_bytes": usage.free, "total_bytes": usage.total}
    except OSError:
        space = {"free_bytes": None, "total_bytes": None}

    db_path = root / ".iphone_backup_index" / "index.sqlite"
    if not db_path.exists():
        return {"total_files": 0, **space}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            total = conn.execute("SELECT COUNT(*) FROM backed_up_files").fetchone()[0]
        finally:
            conn.close()
        return {"total_files": total, **space}
    except sqlite3.OperationalError:
        return None
