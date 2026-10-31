"""Backup by USB cable: PC-side and independent of FastAPI, same as
server/mirror.py — it works with the server off and no network at all, and
nothing here can affect the iPhone-facing path. See PLAN.md section 26.

Every file lands through BackupEngine.finalize_upload, the same as WiFi, so
both paths recognize each other's files however they're named (DFTN0869.JPG by
cable, ced9b322….jpeg by Shortcut, identical bytes) and nothing is overwritten.

Both entry points are blocking and never raise: failures come back as fields
on the result, for the same reason sync_mirror doesn't (a background-thread
exception would leave the GUI stuck with no visible error).
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .device_source import DeviceItem, DeviceReadError, DeviceSource
from .manifest_db import ManifestDB, path_key
from .storage import BackupEngine, existing_path

# Edit recipes: not images, no viewer shows them, and WiFi doesn't back them
# up either. The edited picture itself (IMG_E*) is a normal file and is kept.
SKIPPED_EXTENSIONS = {".aae"}

COMMIT_BATCH_SIZE = 25  # same reasoning and value as server/mirror.py
READ_ATTEMPTS = 3
# This many files failing in a row means the phone is gone or locked, not that
# those files are bad — stop and say so instead of grinding through thousands.
MAX_CONSECUTIVE_FAILURES = 5

logger = logging.getLogger("backup_engine")


@dataclass
class CablePlan:
    pending: list[DeviceItem] = field(default_factory=list)
    already: int = 0  # recognized without reading a single byte
    total_on_device: int = 0
    pending_bytes: int = 0
    free_bytes: Optional[int] = None
    fatal_error: Optional[str] = None
    cancelled: bool = False
    unreadable: int = 0  # objects the phone wouldn't describe: unknown, so never counted as safe

    @property
    def insufficient_space(self) -> bool:
        return self.free_bytes is not None and self.pending_bytes > self.free_bytes


@dataclass
class CableImportResult:
    copied: int = 0
    conflicts: int = 0  # same name, different content: both kept
    already_had: int = 0  # read in full and found to be already backed up
    failed: int = 0
    failed_names: list[str] = field(default_factory=list)
    cancelled: bool = False
    # "device": the phone stopped answering. "verification": the drive keeps failing
    # the read-back. Anything else: the OS error from a full or unplugged drive.
    stopped_with_error: Optional[str] = None
    fatal_error: Optional[str] = None


def _open_engine(dest_root: Path, profile_label: str) -> BackupEngine:
    # reap_dangling_runs=False: a second ManifestDB on this destination in the
    # same process, see AGENTS.md lesson 16.
    engine = BackupEngine(dest_root, ManifestDB(dest_root, reap_dangling_runs=False, profile_label=profile_label))
    engine.clear_staging(older_than_seconds=0)  # the server is off in cable mode, so nothing here is in use
    return engine


def _is_recognized(engine: BackupEngine, aliases: dict, indexed: set[str], item: DeviceItem) -> bool:
    alias = aliases.get((item.name.lower(), item.size))
    if alias and existing_path(engine.dest_root, alias):
        return True
    if not item.taken_at:
        return False  # the folder would be a guess
    candidate = engine._year_month_dir(item.taken_at) / Path(item.name).name
    try:
        if candidate.stat().st_size != item.size:
            return False
    except OSError:
        return False
    # On disk but not in the index: a crash between the file landing and its
    # row being saved. Reading it once proves the content and writes the row;
    # otherwise the mirror would never copy it.
    return path_key(candidate) in indexed


def analyze_device(
    source: DeviceSource,
    dest_root: Path,
    profile_label: str = "-",
    progress_callback: Optional[Callable[[int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> CablePlan:
    """Lists the phone and works out what can be recognized without reading
    any file. Copies nothing. Scan order is the phone's; the plan is sorted
    newest-first so an interrupted copy protects the most recent files, same
    as the mirror."""
    plan = CablePlan()
    try:
        engine = _open_engine(dest_root, profile_label)
    except OSError as exc:
        plan.fatal_error = str(exc)
        return plan
    try:
        items = source.list_items(progress_callback, cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            plan.cancelled = True
            return plan
        if not items:
            # A phone with no files at all isn't credible. Reporting this as
            # "everything is backed up" would be the worst possible failure.
            plan.fatal_error = "the phone listed no files"
            return plan
        plan.unreadable = getattr(source, "unreadable", 0)
        aliases = engine.db.cable_aliases()
        indexed = engine.db.indexed_paths()
        for item in items:
            if Path(item.name).suffix.lower() in SKIPPED_EXTENSIONS:
                continue
            plan.total_on_device += 1
            if _is_recognized(engine, aliases, indexed, item):
                plan.already += 1
            else:
                plan.pending.append(item)
                plan.pending_bytes += item.size
        plan.pending.sort(key=lambda item: item.taken_at or "", reverse=True)
        plan.free_bytes = shutil.disk_usage(dest_root).free
    except Exception as exc:
        plan.fatal_error = str(exc)
    finally:
        engine.db.close()
    return plan


def _stage(source: DeviceSource, engine: BackupEngine, item: DeviceItem) -> Optional[tuple[Path, str, int]]:
    """Reads one file off the phone into staging, or None if it never arrived
    intact. OSError from the destination propagates to the caller."""
    for attempt in range(1, READ_ATTEMPTS + 1):
        try:
            reader = source.open_reader(item)
            try:
                staged, sha256, size = engine.stage_bytes(reader)
            finally:
                reader.close()
            if size == item.size:
                return staged, sha256, size
            # WPD has really handed back another file's bytes (PLAN.md section
            # 26), so a wrong size is never accepted, only retried.
            staged.unlink(missing_ok=True)
            engine.logger.warning("%s: got %s bytes, expected %s, reading it again", item.name, size, item.size)
        except DeviceReadError as exc:
            engine.logger.warning("%s: read failed (%s), attempt %s of %s", item.name, exc, attempt, READ_ATTEMPTS)
        if attempt < READ_ATTEMPTS:
            time.sleep(attempt)
            try:
                source.reopen()
            except DeviceReadError:
                pass  # the next attempt reports it
    return None


def run_cable_import(
    source: DeviceSource,
    plan: CablePlan,
    dest_root: Path,
    profile_label: str = "-",
    progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> CableImportResult:
    """`progress_callback(done, total, failed, bytes_read)`: `done` counts files
    confirmed safe at the destination, never attempts, and starts from what was
    already there, so a resumed copy can't look like lost work (AGENTS.md
    lessons 15 and 23). `cancel_event` is only checked between files.

    Safe to interrupt anywhere: a file gets its row only after it has landed,
    and one that landed without a row (power cut before a commit) is recognized
    by name and hash next time, and its row is written then."""
    result = CableImportResult()
    try:
        engine = _open_engine(dest_root, profile_label)
    except OSError as exc:
        result.fatal_error = str(exc)
        return result

    db = engine.db
    run_id = None
    uncommitted = 0
    consecutive_failures = 0
    bytes_read = 0
    indexed: set[str] = set()
    grand_total = plan.already + len(plan.pending)

    def done() -> int:
        return plan.already + result.copied + result.conflicts + result.already_had

    def fail(name: str) -> None:
        result.failed += 1
        result.failed_names.append(name)
        db.bump_run(run_id, "files_error", commit=False)

    try:
        run_id = db.start_run(source="cable")
        indexed = db.indexed_paths()
        engine.logger.info("=== Cable backup started — %s files to review ===", len(plan.pending))
        for item in plan.pending:
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break
            try:
                staged_result = _stage(source, engine, item)
            except OSError as exc:
                result.stopped_with_error = str(exc)
                break
            if staged_result is None:
                fail(item.name)
                engine.logger.error("x %s: could not read it from the phone", item.name)
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    result.stopped_with_error = "device"
                    break
                if progress_callback is not None:
                    progress_callback(done(), grand_total, result.failed, bytes_read)
                continue
            staged, sha256, size = staged_result
            bytes_read += size

            try:
                # Forces the bytes onto the drive before the file can get a row.
                # Otherwise a power cut or a yanked USB could leave a row saying
                # "backed up" over data still sitting in Windows' write cache.
                with open(staged, "rb+") as staged_file:
                    os.fsync(staged_file.fileno())

                # Same read-back the mirror does. It may be served from Windows'
                # cache, so it catches a bad read path more than a bad disk.
                if engine._hash_existing(staged) != sha256:
                    staged.unlink(missing_ok=True)
                    fail(item.name)
                    engine.logger.error("x %s: failed verification on the destination drive", item.name)
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        result.stopped_with_error = "verification"
                        break
                    if progress_callback is not None:
                        progress_callback(done(), grand_total, result.failed, bytes_read)
                    continue
                consecutive_failures = 0

                outcome = engine.finalize_upload(item.name, staged, sha256, size, item.taken_at, run_id, commit=False)
                if outcome["status"] == "new":
                    result.copied += 1
                elif outcome["status"] == "conflict_kept_both":
                    result.conflicts += 1
                else:
                    result.already_had += 1
                    # Another name, or a video re-encoded by the Shortcut: the scan
                    # can't recognize either without reading it, so remember it.
                    db.record_cable_alias(item.name, item.size, outcome["dest_path"], commit=False)
                    if path_key(outcome["dest_path"]) not in indexed:
                        # The hash of what's on disk, not of what was just read: a
                        # video that landed before a crash already had its container
                        # patched, and the two differ (AGENTS.md lesson 24).
                        on_disk = engine._hash_existing(Path(outcome["dest_path"]))
                        db.record_file(item.name, on_disk, item.taken_at, outcome["dest_path"], size, commit=False)
                        indexed.add(path_key(outcome["dest_path"]))
            except ValueError:
                # An empty file, which the engine refuses and has already counted
                # and logged. One bad file must not end the whole copy.
                staged.unlink(missing_ok=True)
                result.failed += 1
                result.failed_names.append(item.name)
                if progress_callback is not None:
                    progress_callback(done(), grand_total, result.failed, bytes_read)
                continue
            except OSError as exc:
                staged.unlink(missing_ok=True)
                result.stopped_with_error = str(exc)
                break

            uncommitted += 1
            if uncommitted >= COMMIT_BATCH_SIZE:
                db.commit()
                uncommitted = 0
            if progress_callback is not None:
                progress_callback(done(), grand_total, result.failed, bytes_read)
    except Exception as exc:
        result.fatal_error = str(exc)
    finally:
        try:
            if run_id is not None:
                db.finish_run(run_id)  # also commits whatever is left in the batch
            db.commit()
            engine.logger.info(
                "=== Cable backup finished — %s new, %s already had, %s conflicts, %s errors ===",
                result.copied, result.already_had, result.conflicts, result.failed,
            )
        except Exception as exc:
            result.fatal_error = result.fatal_error or str(exc)
        try:
            db.close()
        except Exception:
            pass
    return result
