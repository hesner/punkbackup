"""The per-destination backup index.

Lives INSIDE the destination folder (``<dest>/.iphone_backup_index/index.sqlite``)
so it travels with that drive. Plugging in a different USB drive gives you a
completely independent backup history — nothing is shared between destinations.

Schema:
    backed_up_files  -- one row per file actually written to disk
    runs             -- one row per backup session, for the /status endpoint
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS backed_up_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    taken_at TEXT,
    received_at TEXT NOT NULL,
    dest_path TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL
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

    def __init__(self, dest_root: Path):
        self.dest_root = Path(dest_root)
        self.index_dir = self.dest_root / ".iphone_backup_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "index.sqlite"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
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

    def record_file(
        self,
        filename: str,
        sha256: str,
        taken_at: Optional[str],
        dest_path: str,
        size_bytes: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO backed_up_files
                   (filename, sha256, taken_at, received_at, dest_path, size_bytes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (filename, sha256, taken_at, _now(), dest_path, size_bytes),
            )
            self._conn.commit()

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
