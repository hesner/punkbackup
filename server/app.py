"""FastAPI application exposed to iPhone/iPad Shortcuts on the local network.

Multi-profile, each with its OWN destination folder: the ``X-Backup-Token``
header identifies WHICH profile (person/device) is talking, and that
profile's own ``destination_dir`` (its own folder — possibly on its own USB
drive) decides where its files land. There is no shared destination root
anymore; one profile's disk being unplugged doesn't affect any other
profile — see profiles.py for why.

Endpoints:
    GET  /health        -- liveness + whether any profiles are registered
    POST /run/start      -- begin a backup run for the caller's profile
    POST /check           -- cheap pre-check (filename+date, no bytes): already backed up?
    POST /upload          -- upload one photo/video; filename/taken_at/run_id as URL query
                              params, the file itself as the raw POST body (see upload())
    POST /run/finish     -- close out a run, returns its summary
    GET  /status         -- last backup time, file counts, current state (for the caller's profile)

Profile management (create/rename/delete/regenerate token/set destination)
is done locally by the GUI via profiles.ProfileStore directly — intentionally
NOT exposed over HTTP, so a device on the network can never mint itself a
new identity or redirect where files get written.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from .manifest_db import ManifestDB
from .profiles import Profile, ProfileStore
from .storage import BackupEngine

# Reuses "backup_engine" (not a new logger name) so this shows up in the
# GUI's live activity log for free — main_window.py only wires its
# QueueHandler onto that one logger.
logger = logging.getLogger("backup_engine")

app = FastAPI(title="PunkBackup")

WRITE_BLOCK = 1024 * 1024  # /upload hands the drive 1 MB at a time from a worker thread

_state: dict = {
    "profile_store": None, "engines": {}, "unreachable_warned": set(), "not_ready_warned": set(), "activity": {},
    "bad_tokens": {},
}

# A device that keeps sending a wrong token gets a short pause (PLAN.md W12). Tokens
# are 192 random bits, so this isn't what stops guessing; it keeps a misconfigured or
# stray device from hammering the server and the log. The phone with the right token
# never counts, and a fixed token works again within the minute.
BAD_TOKEN_LIMIT = 20
BAD_TOKEN_WINDOW = 60.0  # seconds


def configure(profile_store: ProfileStore) -> None:
    """Called by the GUI right before the server starts listening."""
    _state["profile_store"] = profile_store
    _state["engines"] = {}
    _state["unreachable_warned"] = set()
    _state["not_ready_warned"] = set()
    _state["activity"] = {}
    _state["bad_tokens"] = {}


def _activity(profile_id: str) -> dict:
    """When this profile's device last talked to us, and how many items it has
    asked about since its run started. A sweep where everything is already backed
    up writes no file and no log line for many minutes, so the GUI's "stalled"
    notice and its progress line need this instead (PLAN.md W9). Memory only:
    after a restart the open run is closed anyway."""
    return _state["activity"].setdefault(profile_id, {"last_request_at": None, "checked": 0})


def is_configured() -> bool:
    return _state["profile_store"] is not None


def _warn_destination_unreachable(profile: Profile, dest_path: Path, exc: OSError) -> None:
    """Logs one clear, human-readable line via the SAME "backup_engine"
    logger the GUI's live activity panel already listens to — before this,
    a request against an unreachable/unplugged destination raised straight
    to an HTTPException with no logging at all, so a real Shortcut run
    against a disconnected USB produced zero visible trace in the app: not
    in the log, not on the profile card (see AGENTS.md lesson 26).

    Logs ONCE per disconnect episode, not on a repeating timer — a first
    version repeated this every 60s for as long as the drive stayed
    unplugged, which looked noisy/repetitive in practice on a real,
    long-running disconnect (confirmed via a real screenshot, 2026-09-24)
    — four near-identical lines in a few minutes for one unchanging fact.
    Silenced here the moment it's logged once; _engine_for's success path
    clears the flag the instant the destination is reachable again, so a
    genuinely NEW disconnect (reconnect, then unplug again) still warns
    right away rather than staying quiet forever."""
    warned = _state["unreachable_warned"]
    if profile.id in warned:
        return
    warned.add(profile.id)
    adapter = logging.LoggerAdapter(logger, {"profile": profile.name})
    adapter.error("Destination folder not reachable — is the USB drive connected? (%s: %s)", dest_path, exc)


def _warn_unknown_request(source: str) -> None:
    """Logs ONCE per source (not rate-limited on a timer like
    _warn_destination_unreachable — a request with a token that matches NO
    profile at all can only mean a misconfigured/stray device, which won't
    fix itself by waiting, so repeating it hundreds of times adds nothing).
    Stays quiet for the rest of this server-listening session (cleared by
    configure(), i.e. the next time the server is started) — see AGENTS.md
    lesson 27."""
    warned = _state["not_ready_warned"]
    key = f"unknown:{source}"
    if key in warned:
        return
    warned.add(key)
    logging.LoggerAdapter(logger, {"profile": "-"}).warning(
        "Backup request received from %s but no profile matches that token.", source
    )


def _warn_profile_not_ready(profile: Profile) -> None:
    """Counterpart to _warn_unknown_request for a KNOWN profile that isn't
    ready to receive a backup right now (paused, or no destination folder
    configured) — same once-per-session behavior, keyed by profile.id so a
    profile that's disabled AND has no destination still only logs once,
    not twice. See AGENTS.md lesson 27."""
    warned = _state["not_ready_warned"]
    if profile.id in warned:
        return
    warned.add(profile.id)
    logging.LoggerAdapter(logger, {"profile": profile.name}).warning(
        "Backup request received from %s but this profile isn't ready to receive it "
        "(paused, or no destination folder set).", profile.name
    )


def _engine_for(profile: Profile) -> BackupEngine:
    engines = _state["engines"]
    if profile.id not in engines:
        if not profile.destination_dir:
            _warn_profile_not_ready(profile)
            raise HTTPException(409, f'Profile "{profile.name}" has no destination folder configured yet.')
        dest_path = Path(profile.destination_dir)
        try:
            dest_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _warn_destination_unreachable(profile, dest_path, exc)
            raise HTTPException(503, f"Destination folder is not reachable (is the drive connected?): {exc}")
        _state["unreachable_warned"].discard(profile.id)
        engines[profile.id] = BackupEngine(dest_path, ManifestDB(dest_path, profile_label=profile.name))
        engines[profile.id].clear_staging()
    return engines[profile.id]


def forget_profile(profile_id: str) -> None:
    """Drops any cached engine for a profile — call this whenever a
    profile's destination_dir changes, or it was just deleted, so a stale
    reference to the old folder isn't kept around. Files on disk untouched."""
    _state["engines"].pop(profile_id, None)


def close_open_runs() -> None:
    """See ManifestDB.finish_open_runs. Best-effort per profile: one
    unreachable drive must not stop the others from closing."""
    for engine in list(_state["engines"].values()):
        try:
            engine.db.finish_open_runs()
        except Exception as exc:
            engine.logger.warning("Could not close the open run: %s", exc)


def get_status_for_profile(profile: Profile) -> dict:
    """Used directly by the GUI (same process, no HTTP round-trip needed)."""
    status = _engine_for(profile).db.get_status()
    activity = _activity(profile.id)
    status["last_request_at"] = activity["last_request_at"]
    status["checked_this_run"] = activity["checked"]
    return status


def get_aggregate_status() -> dict:
    if not is_configured():
        return {"total_files_backed_up": 0, "last_backup_at": None}
    store: ProfileStore = _state["profile_store"]
    total = 0
    last: Optional[str] = None
    for p in store.list():
        if not p.destination_dir:
            continue
        try:
            st = get_status_for_profile(p)
        except HTTPException:
            continue
        total += st["total_files_backed_up"]
        if st["last_backup_at"] and (last is None or st["last_backup_at"] > last):
            last = st["last_backup_at"]
    return {"total_files_backed_up": total, "last_backup_at": last}


def _blocked_for_bad_tokens(source: str) -> bool:
    entry = _state["bad_tokens"].get(source)
    if entry is None or entry["blocked_until"] is None:
        return False
    if time.monotonic() < entry["blocked_until"]:
        return True
    _state["bad_tokens"].pop(source, None)  # the pause is over: start counting again
    return False


def _count_bad_token(source: str) -> None:
    now = time.monotonic()
    entry = _state["bad_tokens"].setdefault(source, {"times": [], "blocked_until": None})
    entry["times"] = [t for t in entry["times"] if now - t < BAD_TOKEN_WINDOW] + [now]
    if len(entry["times"]) >= BAD_TOKEN_LIMIT:
        entry["blocked_until"] = now + BAD_TOKEN_WINDOW
        logging.LoggerAdapter(logger, {"profile": "-"}).warning(
            "%s sent %s wrong tokens in a minute; ignoring it for a minute.", source, BAD_TOKEN_LIMIT
        )


async def verify_token(request: Request, x_backup_token: Optional[str] = Header(None)) -> Profile:
    if not is_configured():
        raise HTTPException(503, "Server has no profiles configured yet.")
    store: ProfileStore = _state["profile_store"]
    source = request.client.host if request.client else "?"
    if _blocked_for_bad_tokens(source):
        raise HTTPException(429, "Too many requests with a wrong token; wait a minute.")
    profile = store.find_by_token(x_backup_token) if x_backup_token else None
    if profile is None:
        _warn_unknown_request(source)
        _count_bad_token(source)
        raise HTTPException(401, "Missing or invalid X-Backup-Token header.")
    if not profile.enabled:
        _warn_profile_not_ready(profile)
        raise HTTPException(403, "This profile is paused on the PC.")
    _activity(profile.id)["last_request_at"] = datetime.now(timezone.utc).isoformat()
    return profile


@app.get("/health")
async def health():
    profile_count = len(_state["profile_store"].list()) if is_configured() else 0
    return {"status": "ok", "configured": is_configured(), "profiles": profile_count}


@app.post("/run/start")
async def run_start(profile: Profile = Depends(verify_token)):
    engine = _engine_for(profile)
    # A commit is a real wait on the drive; never on the thread serving every request.
    run_id = await run_in_threadpool(engine.db.start_run)
    _activity(profile.id)["checked"] = 0
    engine.logger.info("=== Backup run started — run_id %s ===", run_id)
    return {"run_id": run_id, "profile": profile.name}


@app.post("/run/finish")
async def run_finish(run_id: str = Form(...), profile: Profile = Depends(verify_token)):
    engine = _engine_for(profile)
    result = await run_in_threadpool(engine.db.finish_run, run_id)
    failed = result.pop("error_files", [])
    engine.logger.info(
        "=== Backup run finished — run_id %s — %s new, %s already had, %s conflicts,"
        " %s errors%s ===",
        run_id,
        result.get("files_new", 0),
        result.get("files_skipped", 0),
        result.get("files_conflict", 0),
        result.get("files_error", 0),
        # Which ones, so nobody has to dig back through the run's lines (PLAN.md W11).
        f" ({', '.join(failed)}; they'll be asked for again next run)" if failed else "",
    )
    return result


@app.post("/check")
async def check(
    filename: str = Form(...),
    taken_at: Optional[str] = Form(None),
    profile: Profile = Depends(verify_token),
):
    """Cheap pre-flight check — no file bytes — so the Shortcut only spends
    bandwidth uploading what this profile's CURRENT destination is actually
    missing right now. See storage.BackupEngine.check_exists.

    Response shape is deliberately presence/absence of a key, not a JSON
    boolean: iOS Shortcuts' "Get Dictionary Value" + "If" combo only offers
    "has any value" / "does not have any value" as comparison operators for
    this kind of result (no reliable "is true/false" equality in practice),
    so the API meets the client where it is instead of fighting it."""
    engine = _engine_for(profile)
    already = await run_in_threadpool(engine.check_exists, filename, taken_at)
    _activity(profile.id)["checked"] += 1
    return {} if already else {"missing": True}


@app.post("/upload")
async def upload(
    request: Request,
    filename: str = Query(...),
    taken_at: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    profile: Profile = Depends(verify_token),
):
    """The photo/video is the RAW POST body (not a multipart form field).

    iOS Shortcuts has no reliable way to attach a Photos item as a genuine
    multipart file part — inserting "Repeat Item" into a Form field always
    resolves to a specific text attribute (its Name, by default) rather
    than the binary content, which this API would reject as a plain
    string. Sending the file as the whole body and the metadata as URL
    query parameters sidesteps that entirely; it's also the pattern
    Shortcuts' own documentation and most third-party tutorials use for
    uploading a Photos item to an HTTP API."""
    engine = _engine_for(profile)
    staging_path = engine.staging_dir / f"{uuid.uuid4().hex}.part"
    hasher = hashlib.sha256()
    size = 0
    try:
        with open(staging_path, "wb") as out:
            # Written in blocks from a worker thread: a write to a USB drive can
            # stall, and on this thread it stalled every other request with it,
            # up to half a second during a 200 MB video (PLAN.md W9).
            pending = bytearray()
            async for chunk in request.stream():
                hasher.update(chunk)
                pending += chunk
                size += len(chunk)
                if len(pending) >= WRITE_BLOCK:
                    await run_in_threadpool(out.write, bytes(pending))
                    pending.clear()
            if pending:
                await run_in_threadpool(out.write, bytes(pending))
            # Onto the drive before the file can get a row: otherwise a power cut or a
            # yanked USB could leave "backed up" over data still in Windows' cache
            # (PLAN.md W5). Measured on the real USB: 9-62 ms per file.
            await run_in_threadpool(out.flush)
            await run_in_threadpool(os.fsync, out.fileno())
    except OSError as exc:
        # Most common real cause: the destination drive filled up mid-write
        # (ENOSPC). Same reasoning as the 0-byte-upload case below: a non-2xx
        # here would silently abort the rest of the Shortcut's loop (see
        # PLAN.md §5.1 / AGENTS.md lesson 11) instead of surfacing anything —
        # this used to propagate as an unhandled exception (a bare 500),
        # exactly the failure mode that pattern exists to avoid. Not recorded
        # as backed up, so /check still reports it missing and a later run
        # (once space is freed) retries it automatically.
        staging_path.unlink(missing_ok=True)
        await run_in_threadpool(engine.db.mark_error, run_id, Path(filename).name)
        engine.logger.error("x %s: could not write to disk (%s), requesting the file again", filename, exc)
        return {"detail": f'"{filename}" could not be saved (disk write failed: {exc}) — will retry on the next run.'}
    except asyncio.CancelledError:
        # The server is being force-stopped mid-upload (switching to cable
        # mode). CancelledError isn't an Exception, so without this the
        # partial file would stay in the staging folder forever.
        staging_path.unlink(missing_ok=True)
        raise
    except Exception:
        staging_path.unlink(missing_ok=True)
        await run_in_threadpool(engine.db.mark_error, run_id, Path(filename).name)
        raise

    if size == 0:
        # Header-level detail for the 0-byte video bug (see PLAN.md §5.1 —
        # root cause found and fixed client-side via an Encode Media retry,
        # so this is now an expected, self-healing event, not a mystery).
        # Kept at debug (not shown in the GUI's normal activity panel,
        # which only surfaces info+) in case it's ever needed again; the
        # user-visible pairing is storage.py's "x ... / + ..." log lines.
        engine.logger.debug(
            "0-byte upload: filename=%r declared_content_length=%r "
            "content_type=%r user_agent=%r transfer_encoding=%r",
            filename,
            request.headers.get("content-length"),
            request.headers.get("content-type"),
            request.headers.get("user-agent"),
            request.headers.get("transfer-encoding"),
        )

    try:
        result = await run_in_threadpool(
            engine.finalize_upload, filename, staging_path, hasher.hexdigest(), size, taken_at, run_id
        )
    except ValueError as exc:
        # Currently just an empty (0-byte) body — see finalize_upload's
        # docstring. Not recorded as backed up, so /check still reports it
        # missing and a later run retries it automatically.
        #
        # Deliberately a 200 with the error in the body (`detail`, same
        # shape FastAPI's HTTPException would have used) instead of a 4xx
        # status: confirmed on a real device that when this action itself
        # errors, Shortcuts silently aborts the REST of that loop
        # iteration — including the Encode-Media-and-retry steps built to
        # follow it (see PLAN.md §5.1). A 200 keeps the action "successful"
        # so the Shortcut's own `detail`-has-any-value check downstream
        # still runs, exactly like `/check`'s always-200 `missing` pattern.
        return {"detail": str(exc)}
    return result


@app.get("/status")
async def status_endpoint(profile: Profile = Depends(verify_token)):
    return await run_in_threadpool(_engine_for(profile).db.get_status)
