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


def test_empty_upload_is_rejected_and_not_recorded(client, store, tmp_path):
    """A 0-byte body (seen in practice when Shortcuts runs in the
    background and can't fetch a large video's full bytes from iCloud in
    time) must never be recorded as a successful backup — otherwise /check
    would wrongly report it as already backed up forever, and the real
    file would never get a chance to upload on a later, successful run."""
    profile = add_profile_with_dest(store, tmp_path, "Perfil de prueba")
    headers = {"X-Backup-Token": profile.token}

    r = upload(client, headers, "IMG_1.mov", b"")
    assert r.status_code == 422

    status = client.get("/status", headers=headers).json()
    assert status["total_files_backed_up"] == 0

    check = client.post(
        "/check", headers=headers,
        data={"filename": "IMG_1.mov", "taken_at": "2026-06-01T12:00:00"},
    )
    assert check.json() == {"missing": True}  # still reported missing, so a retry can succeed


def test_aggregate_status_sums_all_profiles(client, store, tmp_path):
    laura = add_profile_with_dest(store, tmp_path, "iPhone de Laura")
    hesner = add_profile_with_dest(store, tmp_path, "iPad de Hesner")
    upload(client, {"X-Backup-Token": laura.token}, "A.jpg", b"1")
    upload(client, {"X-Backup-Token": hesner.token}, "B.jpg", b"2")
    agg = app_module.get_aggregate_status()
    assert agg["total_files_backed_up"] == 2
