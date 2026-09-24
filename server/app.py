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

import hashlib
import logging
import time
import uuid
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

_state: dict = {"profile_store": None, "engines": {}, "unreachable_warned": {}, "not_ready_warned": set()}

# How long to stay quiet about the SAME profile's destination being
# unreachable before logging it again — a real device sweeping hundreds of
# items against a disconnected USB hits _engine_for on every single
# /check and /upload, and without this a whole sweep would flood the
# activity log with hundreds of copies of the same fact. A long-running
# sweep still gets periodic reminders, just not one per request. See
# AGENTS.md lesson 26.
_UNREACHABLE_WARN_COOLDOWN = 60.0  # seconds


def configure(profile_store: ProfileStore) -> None:
    """Called by the GUI right before the server starts listening."""
    _state["profile_store"] = profile_store
    _state["engines"] = {}
    _state["unreachable_warned"] = {}
    _state["not_ready_warned"] = set()


def is_configured() -> bool:
    return _state["profile_store"] is not None


def _warn_destination_unreachable(profile: Profile, dest_path: Path, exc: OSError) -> None:
    """Logs one clear, human-readable line via the SAME "backup_engine"
    logger the GUI's live activity panel already listens to — before this,
    a request against an unreachable/unplugged destination raised straight
    to an HTTPException with no logging at all, so a real Shortcut run
    against a disconnected USB produced zero visible trace in the app: not
    in the log, not on the profile card (see AGENTS.md lesson 26). Rate
    limited per profile via _UNREACHABLE_WARN_COOLDOWN so a whole failing
    sweep doesn't flood the log with the same fact on every request."""
    warned = _state["unreachable_warned"]
    now = time.monotonic()
    last = warned.get(profile.id)
    if last is not None and (now - last) < _UNREACHABLE_WARN_COOLDOWN:
        return
    warned[profile.id] = now
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
        _state["unreachable_warned"].pop(profile.id, None)
        engines[profile.id] = BackupEngine(dest_path, ManifestDB(dest_path, profile_label=profile.name))
    return engines[profile.id]


def forget_profile(profile_id: str) -> None:
    """Drops any cached engine for a profile — call this whenever a
    profile's destination_dir changes, or it was just deleted, so a stale
    reference to the old folder isn't kept around. Files on disk untouched."""
    _state["engines"].pop(profile_id, None)


def get_status_for_profile(profile: Profile) -> dict:
    """Used directly by the GUI (same process, no HTTP round-trip needed)."""
    return _engine_for(profile).db.get_status()


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


async def verify_token(request: Request, x_backup_token: Optional[str] = Header(None)) -> Profile:
    if not is_configured():
        raise HTTPException(503, "Server has no profiles configured yet.")
    store: ProfileStore = _state["profile_store"]
    profile = store.find_by_token(x_backup_token) if x_backup_token else None
    if profile is None:
        _warn_unknown_request(request.client.host if request.client else "?")
        raise HTTPException(401, "Missing or invalid X-Backup-Token header.")
    if not profile.enabled:
        _warn_profile_not_ready(profile)
        raise HTTPException(403, "This profile is paused on the PC.")
    return profile


@app.get("/health")
async def health():
    profile_count = len(_state["profile_store"].list()) if is_configured() else 0
    return {"status": "ok", "configured": is_configured(), "profiles": profile_count}


@app.post("/run/start")
async def run_start(profile: Profile = Depends(verify_token)):
    engine = _engine_for(profile)
    run_id = engine.db.start_run()
    engine.logger.info("=== Backup run started — run_id %s ===", run_id)
    return {"run_id": run_id, "profile": profile.name}


@app.post("/run/finish")
async def run_finish(run_id: str = Form(...), profile: Profile = Depends(verify_token)):
    engine = _engine_for(profile)
    result = engine.db.finish_run(run_id)
    engine.logger.info(
        "=== Backup run finished — run_id %s — %s new, %s already had, %s conflicts,"
        " %s errors ===",
        run_id,
        result.get("files_new", 0),
        result.get("files_skipped", 0),
        result.get("files_conflict", 0),
        result.get("files_error", 0),
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
            async for chunk in request.stream():
                hasher.update(chunk)
                out.write(chunk)
                size += len(chunk)
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
        engine.db.bump_run(run_id, "files_error")
        engine.logger.error("x %s: could not write to disk (%s), requesting the file again", filename, exc)
        return {"detail": f'"{filename}" could not be saved (disk write failed: {exc}) — will retry on the next run.'}
    except Exception:
        staging_path.unlink(missing_ok=True)
        engine.db.bump_run(run_id, "files_error")
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
    return _engine_for(profile).db.get_status()
