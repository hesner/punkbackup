"""End-to-end tests against the actual FastAPI app, covering the contract
the iPhone Shortcut relies on: per-profile auth, per-profile DESTINATION
FOLDER, upload, run tracking, and status — and crucially, that different
profiles never mix files together even when they each point at their own
independent folder/drive.

/upload takes the file as the raw POST body and filename/taken_at/run_id as
URL query params (not multipart form-data) — see app.py's upload() docstring
for why: iOS Shortcuts can't reliably attach a Photos item as a real
multipart file part.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from server import app as app_module
import server.profiles as profiles_module
from server.profiles import ProfileStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", tmp_path / "profiles.json")
    return ProfileStore()


@pytest.fixture()
def client(store):
    app_module.configure(store)
    return TestClient(app_module.app)


def add_profile_with_dest(store, tmp_path, name: str):
    profile = store.add(name)
    dest = tmp_path / f"dest-{profile.slug}"
    store.set_destination(profile.id, str(dest))
    return store.get(profile.id)


def upload(client, headers, filename, content, taken_at="2026-06-01T12:00:00", run_id=None):
    params = {"filename": filename, "taken_at": taken_at}
    if run_id:
        params["run_id"] = run_id
    return client.post("/upload", headers=headers, params=params, content=content)


def test_health_reports_configured(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["configured"] is True


def test_upload_without_token_is_rejected(client):
    r = client.post("/upload", params={"filename": "a.jpg"}, content=b"data")
    assert r.status_code == 401


def test_upload_with_unknown_token_is_rejected(client, store):
    store.add("iPhone de Laura")
    r = client.post(
        "/upload",
        headers={"X-Backup-Token": "not-a-real-token"},
        params={"filename": "a.jpg"},
        content=b"data",
    )
    assert r.status_code == 401


def test_upload_without_destination_configured_is_rejected(client, store):
    profile = store.add("iPhone sin carpeta")  # no set_destination() called
    r = upload(client, {"X-Backup-Token": profile.token}, "a.jpg", b"data")
    assert r.status_code == 409


def test_two_profiles_use_independent_folders(client, store, tmp_path):
    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    hesner = add_profile_with_dest(store, tmp_path, "iPad de Hesner")
    assert laura.destination_dir != hesner.destination_dir  # different drives/folders

    r1 = upload(client, {"X-Backup-Token": laura.token}, "IMG_1.jpg", b"laura-photo")
    assert r1.json()["status"] == "new"
    assert str(Path(laura.destination_dir)) in r1.json()["dest_path"]

    # Same filename, different profile, different destination folder entirely
    # -> must not be treated as a conflict with Laura's file.
    r2 = upload(client, {"X-Backup-Token": hesner.token}, "IMG_1.jpg", b"hesner-photo")
    assert r2.json()["status"] == "new"
    assert str(Path(hesner.destination_dir)) in r2.json()["dest_path"]
    assert r2.json()["dest_path"] != r1.json()["dest_path"]

    status_laura = client.get("/status", headers={"X-Backup-Token": laura.token}).json()
    status_hesner = client.get("/status", headers={"X-Backup-Token": hesner.token}).json()
    assert status_laura["total_files_backed_up"] == 1
    assert status_hesner["total_files_backed_up"] == 1


def test_paused_profile_is_rejected_but_not_deleted(client, store, tmp_path):
    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    store.set_enabled(laura.id, False)
    r = client.get("/status", headers={"X-Backup-Token": laura.token})
    assert r.status_code == 403
    assert store.get(laura.id) is not None  # still exists, just paused

    store.set_enabled(laura.id, True)
    r2 = client.get("/status", headers={"X-Backup-Token": laura.token})
    assert r2.status_code == 200


def test_two_profiles_can_upload_concurrently(client, store, tmp_path):
    """The server has no notion of a single 'active' profile — any number
    of enabled profiles can upload at the same time, each isolated in its
    own folder."""
    import concurrent.futures

    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    hesner = add_profile_with_dest(store, tmp_path, "iPad de Hesner")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(upload, client, {"X-Backup-Token": laura.token}, "IMG_1.jpg", b"laura-photo")
        f2 = pool.submit(upload, client, {"X-Backup-Token": hesner.token}, "IMG_1.jpg", b"hesner-photo")
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200 and r1.json()["status"] == "new"
    assert r2.status_code == 200 and r2.json()["status"] == "new"


def test_deleted_profile_token_stops_working(client, store, tmp_path):
    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    store.remove(laura.id)
    r = client.get("/status", headers={"X-Backup-Token": laura.token})
    assert r.status_code == 401


def test_changing_destination_is_picked_up_after_forget_profile(client, store, tmp_path):
    profile = add_profile_with_dest(store, tmp_path, "iPhone de prueba")
    upload(client, {"X-Backup-Token": profile.token}, "A.jpg", b"1")

    # Point the profile at a brand new folder (e.g. user swapped USB drives)
    # and tell the app to drop its cached engine, as the GUI does.
    new_dest = tmp_path / "new-drive"
    store.set_destination(profile.id, str(new_dest))
    app_module.forget_profile(profile.id)

    r = upload(client, {"X-Backup-Token": profile.token}, "B.jpg", b"2")
    assert str(new_dest) in r.json()["dest_path"]


def test_unknown_token_request_logs_once_per_source(client, store, caplog):
    """A request whose token matches NO profile at all can only mean a
    stray/misconfigured device -- it won't start working by waiting, so
    unlike the unreachable-destination warning (AGENTS.md lesson 26) this
    is logged ONCE per source, not on a repeating cooldown. See lesson 27."""
    import logging

    caplog.set_level(logging.WARNING, logger="backup_engine")

    client.post("/upload", headers={"X-Backup-Token": "not-a-real-token"}, params={"filename": "a.jpg"}, content=b"x")
    assert len(caplog.records) == 1
    assert "no profile matches that token" in caplog.records[0].getMessage()

    caplog.clear()
    client.post("/upload", headers={"X-Backup-Token": "not-a-real-token"}, params={"filename": "b.jpg"}, content=b"x")
    assert len(caplog.records) == 0  # same source, second time -- stays quiet


def test_disabled_profile_request_logs_once(client, store, tmp_path, caplog):
    """A paused profile's token is real, but requests against it can never
    succeed until a human re-enables it on the PC -- same once-per-session
    treatment as an unknown token (AGENTS.md lesson 27)."""
    import logging

    profile = add_profile_with_dest(store, tmp_path, "iPhone de Hesner")
    store.set_enabled(profile.id, False)
    caplog.set_level(logging.WARNING, logger="backup_engine")

    r = client.get("/status", headers={"X-Backup-Token": profile.token})
    assert r.status_code == 403
    assert len(caplog.records) == 1
    assert "isn't ready to receive it" in caplog.records[0].getMessage()

    caplog.clear()
    client.get("/status", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 0


def test_profile_without_destination_request_logs_once(client, store, caplog):
    """Same once-per-session treatment for an enabled profile that simply
    has no destination folder configured yet (AGENTS.md lesson 27)."""
    import logging

    profile = store.add("iPhone sin carpeta")  # enabled by default, no destination
    caplog.set_level(logging.WARNING, logger="backup_engine")

    r = client.get("/status", headers={"X-Backup-Token": profile.token})
    assert r.status_code == 409
    assert len(caplog.records) == 1
    assert "isn't ready to receive it" in caplog.records[0].getMessage()

    caplog.clear()
    client.get("/status", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 0


def test_unreachable_destination_logs_once_via_the_backup_engine_logger(client, store, tmp_path, monkeypatch, caplog):
    """Before this, a request against an unreachable/unplugged destination
    raised straight to a 503 with ZERO logging anywhere -- a real Shortcut
    run against a disconnected USB left no trace at all in the app's
    activity log (only an occasional unrelated traceback from the idle
    checker, and only much later). Reuses the "backup_engine" logger so
    this shows up in the GUI's live activity panel for free. See AGENTS.md
    lesson 26."""
    import logging

    profile = add_profile_with_dest(store, tmp_path, "iPhone de Hesner")

    def failing_mkdir(self, *a, **k):
        raise OSError(3, "The system cannot find the path specified")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)
    caplog.set_level(logging.ERROR, logger="backup_engine")

    r = client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert r.status_code == 503
    assert any("not reachable" in rec.getMessage() for rec in caplog.records)


def test_unreachable_destination_warning_is_rate_limited_per_profile(client, store, tmp_path, monkeypatch, caplog):
    """A real Shortcut sweep retries /check and /upload for every item in
    the library against the SAME disconnected destination -- without a
    cooldown, that's hundreds of identical log lines for one underlying
    fact. See AGENTS.md lesson 26."""
    import logging

    import server.app as app_mod

    profile = add_profile_with_dest(store, tmp_path, "iPhone de Hesner")

    def failing_mkdir(self, *a, **k):
        raise OSError(3, "The system cannot find the path specified")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)
    fake_now = [1000.0]
    monkeypatch.setattr(app_mod.time, "monotonic", lambda: fake_now[0])
    caplog.set_level(logging.ERROR, logger="backup_engine")

    client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 1

    caplog.clear()
    fake_now[0] += 10  # well inside the cooldown
    client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 0

    caplog.clear()
    fake_now[0] += app_mod._UNREACHABLE_WARN_COOLDOWN + 1  # past the cooldown
    client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 1


def test_unreachable_destination_warns_again_right_after_a_real_reconnect(client, store, tmp_path, monkeypatch, caplog):
    """A successful request (drive genuinely reconnected) must clear the
    rate-limit state -- otherwise a disconnect -> reconnect -> disconnect
    cycle inside one cooldown window would wrongly stay silent on the
    second disconnect, even though it's a fresh, newly-true fact."""
    import logging

    import server.app as app_mod

    profile = add_profile_with_dest(store, tmp_path, "iPhone de Hesner")
    real_mkdir = Path.mkdir
    fail = {"on": True}

    def maybe_failing_mkdir(self, *a, **k):
        if fail["on"]:
            raise OSError(3, "The system cannot find the path specified")
        return real_mkdir(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", maybe_failing_mkdir)
    fake_now = [1000.0]
    monkeypatch.setattr(app_mod.time, "monotonic", lambda: fake_now[0])
    caplog.set_level(logging.ERROR, logger="backup_engine")

    client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 1

    fail["on"] = False
    fake_now[0] += 1  # still well inside the cooldown, but the drive is back
    r = client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert r.status_code == 200

    caplog.clear()
    fail["on"] = True
    app_module.forget_profile(profile.id)
    fake_now[0] += 1
    client.post("/run/start", headers={"X-Backup-Token": profile.token})
    assert len(caplog.records) == 1  # not suppressed by the earlier cooldown


def test_check_endpoint_matches_actual_destination(client, store, tmp_path):
    profile = add_profile_with_dest(store, tmp_path, "iPhone de prueba")
    headers = {"X-Backup-Token": profile.token}

    r0 = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.jpg", "taken_at": "2026-06-01T12:00:00"},
    )
    assert r0.json() == {"missing": True}  # not backed up yet -> key present

    upload(client, headers, "IMG_1.jpg", b"content-one")

    r1 = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.jpg", "taken_at": "2026-06-01T12:00:00"},
    )
    assert r1.json() == {}  # already backed up -> key absent


def test_check_is_scoped_to_the_profiles_current_destination(client, store, tmp_path):
    """The whole point: switching a profile to a fresh destination (e.g. a
    different USB) must NOT remember what was sent to the old one."""
    profile = add_profile_with_dest(store, tmp_path, "iPhone de prueba")
    headers = {"X-Backup-Token": profile.token}
    upload(client, headers, "IMG_1.jpg", b"content-one")

    # Point this profile at a brand new, empty destination.
    store.set_destination(profile.id, str(tmp_path / "fresh-usb"))
    app_module.forget_profile(profile.id)

    r = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.jpg", "taken_at": "2026-06-01T12:00:00"},
    )
    assert r.json() == {"missing": True}  # correctly "missing" on the new destination


def test_full_run_flow(client, store, tmp_path):
    profile = add_profile_with_dest(store, tmp_path, "Perfil de prueba")
    headers = {"X-Backup-Token": profile.token}

    run_id = client.post("/run/start", headers=headers).json()["run_id"]

    r1 = upload(client, headers, "IMG_1.jpg", b"content-one", run_id=run_id)
    assert r1.status_code == 200
    assert r1.json()["status"] == "new"

    # Re-upload the same file -> should be a no-op, not a duplicate.
    r2 = upload(client, headers, "IMG_1.jpg", b"content-one", run_id=run_id)
    assert r2.json()["status"] == "skipped_duplicate"

    summary = client.post("/run/finish", headers=headers, data={"run_id": run_id}).json()
    assert summary["files_new"] == 1
    assert summary["files_skipped"] == 1

    status = client.get("/status", headers=headers).json()
    assert status["state"] == "idle"
    assert status["total_files_backed_up"] == 1
    assert status["last_backup_at"] is not None


def test_log_records_are_tagged_with_the_correct_profile(client, store, tmp_path, caplog):
    """The whole point of this feature: with two profiles active, every
    log line must be attributable to the right one, never mixed up or
    left unlabeled — this is what lets a shared activity log distinguish
    "iPhone de Hesner" from "iPad" activity at a glance."""
    profile_a = add_profile_with_dest(store, tmp_path, "iPhone de Hesner")
    profile_b = add_profile_with_dest(store, tmp_path, "iPad")

    with caplog.at_level("INFO", logger="backup_engine"):
        run_id_a = client.post("/run/start", headers={"X-Backup-Token": profile_a.token}).json()["run_id"]
        upload(client, {"X-Backup-Token": profile_a.token}, "IMG_A.jpg", b"a", run_id=run_id_a)

        run_id_b = client.post("/run/start", headers={"X-Backup-Token": profile_b.token}).json()["run_id"]
        upload(client, {"X-Backup-Token": profile_b.token}, "IMG_B.jpg", b"b", run_id=run_id_b)

    started_a = [r for r in caplog.records if run_id_a in r.getMessage() and "started" in r.getMessage()]
    started_b = [r for r in caplog.records if run_id_b in r.getMessage() and "started" in r.getMessage()]
    uploaded_a = [r for r in caplog.records if "IMG_A.jpg" in r.getMessage()]
    uploaded_b = [r for r in caplog.records if "IMG_B.jpg" in r.getMessage()]
    assert started_a and started_b and uploaded_a and uploaded_b

    assert all(r.profile == "iPhone de Hesner" for r in started_a + uploaded_a)
    assert all(r.profile == "iPad" for r in started_b + uploaded_b)


def test_empty_upload_is_rejected_and_not_recorded(client, store, tmp_path):
    """A 0-byte body (seen in practice when Shortcuts runs in the
    background and can't fetch a large video's full bytes from iCloud in
    time) must never be recorded as a successful backup — otherwise /check
    would wrongly report it as already backed up forever, and the real
    file would never get a chance to upload on a later, successful run.

    Deliberately a 200 with `detail` in the body, not a 4xx status:
    confirmed on a real device that a non-2xx response makes Shortcuts
    silently abort the rest of that loop iteration, which would break the
    client-side Encode-Media-and-retry logic built to run right after this
    call (see PLAN.md §5.1) — same always-200 idiom as /check's `missing`."""
    profile = add_profile_with_dest(store, tmp_path, "Perfil de prueba")
    headers = {"X-Backup-Token": profile.token}

    r = upload(client, headers, "IMG_1.mov", b"")
    assert r.status_code == 200
    assert r.json().get("detail")

    status = client.get("/status", headers=headers).json()
    assert status["total_files_backed_up"] == 0

    check = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.mov", "taken_at": "2026-06-01T12:00:00"},
    )
    assert check.json() == {"missing": True}  # still reported missing, so a retry can succeed


def test_disk_full_during_upload_returns_graceful_error(client, store, tmp_path, monkeypatch):
    """Found via design review while planning the second-USB mirror feature
    (2026-09-21): the destination drive filling up mid-write (ENOSPC) used
    to propagate as an unhandled exception -> a bare 500 -> confirmed on a
    real device elsewhere in this project that a non-2xx response makes
    Shortcuts silently abort the rest of that loop iteration. Same
    always-200-with-detail idiom as the 0-byte-upload case above."""
    profile = add_profile_with_dest(store, tmp_path, "Perfil de prueba")
    headers = {"X-Backup-Token": profile.token}

    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        if str(path).endswith(".part"):
            f = real_open(path, mode, *args, **kwargs)

            def failing_write(data, _real_write=f.write):
                raise OSError(28, "No space left on device")

            f.write = failing_write
            return f
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(app_module, "open", failing_open, raising=False)

    r = upload(client, headers, "IMG_1.mov", b"some real bytes")
    assert r.status_code == 200
    assert r.json().get("detail")

    status = client.get("/status", headers=headers).json()
    assert status["total_files_backed_up"] == 0

    check = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.mov", "taken_at": "2026-06-01T12:00:00"},
    )
    assert check.json() == {"missing": True}  # still reported missing, so a retry can succeed


def test_error_count_self_heals_when_retry_succeeds(client, store, tmp_path):
    """The Shortcut's own retry (see PLAN.md §5.1: 0-byte upload -> Encode
    Media -> re-upload the same filename) shouldn't leave files_error
    permanently inflated once that retry succeeds — a transient failure
    that immediately fixed itself isn't a real, lasting problem, and the
    live counter shouldn't keep claiming it is."""
    profile = add_profile_with_dest(store, tmp_path, "Perfil de prueba")
    headers = {"X-Backup-Token": profile.token}
    run_id = client.post("/run/start", headers=headers).json()["run_id"]

    # First attempt: 0 bytes (as if the raw Photos item failed to
    # materialize) -> rejected, counted as an error.
    r1 = upload(client, headers, "IMG_1.mov", b"", run_id=run_id)
    assert r1.json().get("detail")

    # Retry with the SAME filename (as if Encode Media fixed it) -> succeeds.
    r2 = upload(client, headers, "IMG_1.mov", b"real video bytes", run_id=run_id)
    assert r2.json()["status"] == "new"

    summary = client.post("/run/finish", headers=headers, data={"run_id": run_id}).json()
    assert summary["files_new"] == 1
    assert summary["files_error"] == 0  # the resolved retry un-counted the earlier error


def test_aggregate_status_sums_all_profiles(client, store, tmp_path):
    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    hesner = add_profile_with_dest(store, tmp_path, "iPad de Hesner")
    upload(client, {"X-Backup-Token": laura.token}, "A.jpg", b"1")
    upload(client, {"X-Backup-Token": hesner.token}, "B.jpg", b"2")
    agg = app_module.get_aggregate_status()
    assert agg["total_files_backed_up"] == 2
