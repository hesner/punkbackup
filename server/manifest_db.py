"""The per-destination backup index.

Lives INSIDE the destination folder (``<dest>/.iphone_backup_index/index.sqlite``)
so it travels with that drive. Plugging in a different USB drive gives you a
completely independent backup history — nothing is shared between destinations.

Schema:
    backed_up_files  -- one row per file actually written to disk
    runs             -- one row per backup session, for the /status endpoint
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Same logger the GUI's queue handler already listens to (see storage.py) —
# reusing it means a reaped run shows up in the activity log for free,
# right alongside real upload/run-finish lines, instead of being invisible.
logger = logging.getLogger("backup_engine")

SCHEMA = """
CREATE TABLE IF NOT EXISTS backed_up_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    taken_at TEXT,
    received_at TEXT NOT NULL,
    dest_path TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    original_filename TEXT
);
CREATE INDEX IF NOT EXISTS idx_backed_up_files_dest_path ON backed_up_files(dest_path);
CREATE INDEX IF NOT EXISTS idx_backed_up_files_sha256 ON backed_up_files(sha256);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    files_new INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    files_conflict INTEGER NOT NULL DEFAULT 0,
    files_error INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManifestDB:
    """Thread-safe wrapper around the per-destination SQLite index.

    A single lock serializes access. This is a personal, single-user, local
    tool — write volume is one file at a time from one iPhone — so this is
    not a bottleneck; it trades a bit of theoretical throughput for
    correctness simplicity.
    """

    def __init__(self, dest_root: Path, reap_dangling_runs: bool = True, profile_label: str = "-"):
        self.dest_root = Path(dest_root)
        self.index_dir = self.dest_root / ".iphone_backup_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "index.sqlite"
        self.profile_label = profile_label
        # Every log line this DB (or anything built on top of it) emits
        # carries this profile's name as a separate field — see
        # gui/main_window.py's Formatter and PLAN.md's log-format section —
        # so activity from multiple devices/profiles in the same log can be
        # told apart at a glance instead of only by the message text.
        self.logger = logging.LoggerAdapter(logger, {"profile": profile_label})
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            # Migration for DBs created before original_filename existed
            # (see find_by_original_filename()'s docstring) — CREATE TABLE IF
            # NOT EXISTS above never adds columns to an already-existing
            # table, so older index.sqlite files need this ALTER TABLE once.
            existing_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(backed_up_files)")}
            if "original_filename" not in existing_cols:
                self._conn.execute("ALTER TABLE backed_up_files ADD COLUMN original_filename TEXT")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_backed_up_files_original_filename "
                "ON backed_up_files(original_filename)"
            )
            self._conn.commit()
            # A run's finished_at can only ever be set by /run/finish, called
            # from the SAME app process that handed out its run_id via
            # /run/start (RunID is a Shortcut-local variable, never persisted
            # across a Shortcut run) — so a run still open from a PREVIOUS
            # process lifetime (app closed/crashed mid-run) can never be
            # finished for real. Reap it here, once, the first time this
            # profile's DB is opened in this process: otherwise get_status()
            # reports "running" indefinitely for a run nobody is actually
            # running, which then falsely trips the GUI's idle-backup notice
            # a few minutes after simply opening the app.
            #
            # reap_dangling_runs=False exists specifically for a SECOND
            # ManifestDB opened on the SAME dest_root within the SAME still-
            # running process (e.g. server/mirror.py reading the primary
            # destination's index to build its copy list) -- the "previous
            # process lifetime" assumption above is only true for the FIRST
            # ManifestDB opened on a given dest_root per process. A second
            # one opened while a real /run/start from the phone is still
            # genuinely in progress would otherwise reap that live run out
            # from under it (confirmed live, 2026-09-22: the GUI's mirror-
            # sync button did exactly this to a real, currently uploading
            # backup, making it look stalled even though files kept
            # landing). See AGENTS.md's "ad-hoc read-only status checks"
            # lesson -- this is the same category of bug, now also possible
            # from application code, not just a one-off script.
            dangling = self._conn.execute(
                "SELECT id FROM runs WHERE finished_at IS NULL"
            ).fetchall() if reap_dangling_runs else []
            if dangling:
                self._conn.execute(
                    "UPDATE runs SET finished_at = ? WHERE finished_at IS NULL", (_now(),)
                )
                self._conn.commit()
                for row in dangling:
                    self.logger.warning(
                        "!! Run %s was left \"running\" by a previous session (app closed/crashed "
                        "mid-run) — auto-closed on reopen. This is NOT a real /run/finish from the "
                        "Shortcut; its final tally may be incomplete.",
                        row["id"],
                    )
        # In-memory only (reset on restart) — which filenames currently have
        # an unresolved mark_error() in a given run, so a same-run retry that
        # later succeeds for that exact filename can un-count it. See
        # mark_error()/resolve_error().
        self._pending_errors: dict[str, set[str]] = {}

    # -- file records ---------------------------------------------------

    def find_by_dest_path(self, dest_path: str) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM backed_up_files WHERE dest_path = ?", (dest_path,)
            )
            return cur.fetchone()

    def find_by_original_filename(self, original_filename: str) -> Optional[sqlite3.Row]:
        """Lookup used by BackupEngine.check_exists() for items whose name,
        as the Shortcut actually sends it, has no extension — see
        PLAN.md section 5.4.2. The plain path-existence check in
        check_exists() can never match these after their first successful
        upload, because the extension only gets appended server-side
        (during finalize_upload's content-sniffing), never reflected back
        to what the Shortcut sends on a later /check call for the same
        item. This is an EXACT match against a name that was actually,
        really sent and processed before — not a guess — so it stays safe
        even for items with no other distinguishing metadata (no
        taken_at)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM backed_up_files WHERE original_filename = ? LIMIT 1", (original_filename,)
            )
            return cur.fetchone()

    def backfill_original_filename(self, dest_path: str, original_filename: str) -> None:
        """Opportunistically fills in original_filename on a row that
        predates this column, or that was first recorded before the
        Shortcut's as-sent name was tracked — called from finalize_upload's
        skip paths (duplicate / re-encoded-duplicate) so a file that keeps
        getting re-uploaded because /check couldn't recognize its bare name
        self-heals the very next time it's encountered, without needing a
        one-off migration script."""
        with self._lock:
            self._conn.execute(
                "UPDATE backed_up_files SET original_filename = ? "
                "WHERE dest_path = ? AND (original_filename IS NULL OR original_filename != ?)",
                (original_filename, dest_path, original_filename),
            )
            self._conn.commit()

    def record_file(
        self,
        filename: str,
        sha256: str,
        taken_at: Optional[str],
        dest_path: str,
        size_bytes: int,
        original_filename: Optional[str] = None,
        commit: bool = True,
    ) -> None:
        """`commit=False` lets a caller batch many inserts into one physical
        disk confirmation via a later explicit commit() call — see
        commit()'s docstring for why this matters and when it's safe.
        Defaults to True (commit every call, today's behavior, unchanged)
        so every existing caller — the real iPhone-facing upload path
        included — keeps its current per-file durability with no code
        change needed."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO backed_up_files
                   (filename, sha256, taken_at, received_at, dest_path, size_bytes, original_filename)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (filename, sha256, taken_at, _now(), dest_path, size_bytes, original_filename or filename),
            )
            if commit:
                self._conn.commit()

    def commit(self) -> None:
        """Explicit commit, paired with record_file(..., commit=False) to
        batch several inserts into one physical disk confirmation instead
        of one per file. Measured (2026-09-23, real USB media, mirror
        sync): the per-file commit's fsync was ~81% of total sync time —
        far more than the actual file copy or hash verification, which
        this change never touches. Safe to skip/delay: a row that isn't
        committed yet (app closed, power loss) simply isn't in the index
        next time it's opened, so the next sync just re-copies and
        re-verifies that one file — the same self-healing behavior this
        project already relies on elsewhere (see AGENTS.md lessons 12/20),
        never a risk of silently recording something that wasn't really
        there."""
        with self._lock:
            self._conn.commit()

    def update_sha256(self, dest_path: str, new_sha256: str, commit: bool = True) -> None:
        """Corrects an already-recorded row's hash to match what's
        actually on disk now — used by the one-off retroactive fix for
        the video creation_time stale-hash bug (PLAN.md §17.5): a row
        recorded before that fix has a `sha256` that no longer matches
        its file's real bytes (the creation_time patch changed them after
        the hash was recorded), and there's no other way to correct it
        after the fact than to re-hash the real file and update the row.
        `commit=False` mirrors record_file()'s batching — a maintenance
        script touching hundreds of rows should batch this the same way."""
        with self._lock:
            self._conn.execute(
                "UPDATE backed_up_files SET sha256 = ? WHERE dest_path = ?",
                (new_sha256, dest_path),
            )
            if commit:
                self._conn.commit()

    def all_sha256s(self) -> set[str]:
        """Every content hash this destination already has. Used by
        server/mirror.py to cheaply tell, in one query, which rows of the
        PRIMARY destination still need to be copied to a second-copy
        destination — reuses idx_backed_up_files_sha256."""
        with self._lock:
            cur = self._conn.execute("SELECT sha256 FROM backed_up_files")
            return {row[0] for row in cur.fetchall()}

    def iter_files_by_recency(self) -> list[sqlite3.Row]:
        """All rows, newest photo first (falling back to received_at for
        the few rows with no known taken_at) — same ordering the iPhone's
        own block-sweep already uses in practice (see PLAN.md section 5.1),
        applied here to server/mirror.py's copy order so an interrupted or
        space-constrained sync protects the most recent files first."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM backed_up_files ORDER BY COALESCE(taken_at, received_at) DESC"
            )
            return cur.fetchall()

    # -- runs -------------------------------------------------------------

    def start_run(self) -> str:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs (id, started_at) VALUES (?, ?)", (run_id, _now())
            )
            self._conn.commit()
        return run_id

    def bump_run(self, run_id: Optional[str], field: str) -> None:
        """Increment a counter column on a run. No-op if run_id is None
        (the Shortcut is allowed to call /upload without bracketing a run)."""
        if not run_id:
            return
        assert field in ("files_new", "files_skipped", "files_conflict", "files_error")
        with self._lock:
            self._conn.execute(
                f"UPDATE runs SET {field} = {field} + 1 WHERE id = ?", (run_id,)
            )
            self._conn.commit()

    def mark_error(self, run_id: Optional[str], filename: str) -> None:
        """Like bump_run(run_id, "files_error"), but remembers the filename
        so a same-run retry that later succeeds for this exact file can
        un-count it via resolve_error() — a 0-byte upload that the
        Shortcut's own Encode-Media retry fixes a moment later (see
        PLAN.md §5.1) isn't a real, lasting error, and the live counter
        shouldn't keep saying it is."""
        if not run_id:
            return
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET files_error = files_error + 1 WHERE id = ?", (run_id,)
            )
            self._conn.commit()
            self._pending_errors.setdefault(run_id, set()).add(filename)

    def resolve_error(self, run_id: Optional[str], filename: str) -> None:
        """Undo a previous mark_error() for this exact filename in this
        run, if there was one — call right after a file finishes
        successfully (new / skipped / conflict), before/after the matching
        bump_run() for that outcome."""
        if not run_id:
            return
        with self._lock:
            pending = self._pending_errors.get(run_id)
            if pending and filename in pending:
                pending.discard(filename)
                self._conn.execute(
                    "UPDATE runs SET files_error = files_error - 1 WHERE id = ?", (run_id,)
                )
                self._conn.commit()

    def finish_run(self, run_id: str) -> dict:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET finished_at = ? WHERE id = ?", (_now(), run_id)
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else {}

    # -- status -------------------------------------------------------------

    def get_status(self) -> dict:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS c, MAX(received_at) AS last FROM backed_up_files"
            ).fetchone()
            last_run = self._conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

        state = "idle"
        if last_run and last_run["finished_at"] is None:
            state = "running"

        return {
            "state": state,
            "total_files_backed_up": total["c"] or 0,
            "last_backup_at": total["last"],
            "last_run": dict(last_run) if last_run else None,
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
