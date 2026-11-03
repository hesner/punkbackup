"""A sweep where everything is already backed up saves nothing for many minutes
while it works. The app must still see it moving: no false "stalled" notice, and
a count of items checked on the profile's card. See PLAN.md W9.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from server import app as app_module
import server.profiles as profiles_module
from server.profiles import ProfileStore
from gui.main_window import _idle_tick, _profile_stats_text

TAKEN_AT = "2026-06-01T12:00:00"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", tmp_path / "profiles.json")
    s = ProfileStore()
    app_module.configure(s)
    return s


def _profile(store, tmp_path, name):
    p = store.add(name)
    store.set_destination(p.id, str(tmp_path / f"dest-{p.slug}"))
    return store.get(p.id)


def _check(client, profile, name):
    r = client.post("/check", headers={"X-Backup-Token": profile.token}, data={"filename": name, "taken_at": TAKEN_AT})
    assert r.status_code == 200


def test_checks_are_counted_per_run_and_per_profile(store, tmp_path):
    a, b = _profile(store, tmp_path, "A"), _profile(store, tmp_path, "B")
    client = TestClient(app_module.app)
    client.post("/run/start", headers={"X-Backup-Token": a.token})
    for i in range(3):
        _check(client, a, f"IMG_{i}.JPG")
    _check(client, b, "IMG_9.JPG")
    status = app_module.get_status_for_profile(a)
    assert status["state"] == "running"
    assert status["checked_this_run"] == 3
    assert status["last_request_at"] is not None
    assert app_module.get_status_for_profile(b)["checked_this_run"] == 1

    client.post("/run/start", headers={"X-Backup-Token": a.token})  # a new run starts from zero
    assert app_module.get_status_for_profile(a)["checked_this_run"] == 0


def test_a_rejected_token_is_not_activity(store, tmp_path):
    a = _profile(store, tmp_path, "A")
    client = TestClient(app_module.app)
    client.post("/check", headers={"X-Backup-Token": "wrong"}, data={"filename": "x.jpg"})
    assert app_module.get_status_for_profile(a)["last_request_at"] is None


def _running(last_backup_at, last_request_at):
    return {"state": "running", "last_backup_at": last_backup_at, "last_request_at": last_request_at}


def test_no_stalled_notice_while_the_phone_keeps_checking(store):
    """The real case of 2026-11-03: no file saved for 17 minutes, checks all along."""
    start = datetime(2026, 11, 3, 14, 38, tzinfo=timezone.utc)
    tracking = {"last_backup_at": None, "seen_at": start, "notified": False}
    notices = []
    for minute in range(40):
        now = start + timedelta(minutes=minute)
        notices.append(_idle_tick(tracking, _running("14:38", now.isoformat()), now, 20 * 60))
    assert not any(notices)


def test_stalled_notice_once_when_the_phone_really_goes_quiet(store):
    start = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
    tracking = {"last_backup_at": None, "seen_at": start, "notified": False}
    quiet = _running("15:00", "15:00")
    notices = [_idle_tick(tracking, quiet, start + timedelta(minutes=m), 20 * 60) for m in range(45)]
    assert notices.count(True) == 1
    assert notices.index(True) == 20


def test_card_shows_items_checked_while_the_run_is_open(store, tmp_path):
    a = _profile(store, tmp_path, "A")
    client = TestClient(app_module.app)
    client.post("/run/start", headers={"X-Backup-Token": a.token})
    for i in range(5):
        _check(client, a, f"IMG_{i}.JPG")
    text = _profile_stats_text(a, "es", app_module.get_status_for_profile(a))
    assert "5 revisados" in text
    assert "5 checked" in _profile_stats_text(a, "en", app_module.get_status_for_profile(a))
