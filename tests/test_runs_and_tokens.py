"""v1.8.8: an abandoned run closes when the next one starts (W10), the run summary
names the files that failed (W11), wrong tokens are compared in constant time and a
device that keeps sending them gets a short pause (W12), and the profile card shows
how much the backup takes up (roadmap 11).

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from server import app as app_module
import server.profiles as profiles_module
from server.manifest_db import ManifestDB
from server.profiles import ProfileStore
from gui.main_window import _profile_stats_text, _size_text

TAKEN_AT = "2026-06-01T12:00:00"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", tmp_path / "profiles.json")
    s = ProfileStore()
    app_module.configure(s)
    return s


def _profile(store, tmp_path, name="A"):
    p = store.add(name)
    store.set_destination(p.id, str(tmp_path / f"dest-{p.slug}"))
    return store.get(p.id)


def _headers(profile):
    return {"X-Backup-Token": profile.token}


# -- W10 ---------------------------------------------------------------------


def test_a_run_left_open_is_closed_when_the_next_one_starts(tmp_path, caplog):
    db = ManifestDB(tmp_path)
    abandoned = db.start_run()
    with caplog.at_level(logging.WARNING, logger="backup_engine"):
        current = db.start_run()
    rows = {r["id"]: r for r in db._conn.execute("SELECT id, finished_at FROM runs").fetchall()}
    assert rows[abandoned]["finished_at"] is not None
    assert rows[current]["finished_at"] is None
    status = db.get_status()
    assert status["state"] == "running" and status["last_run"]["id"] == current
    assert abandoned in caplog.text and "new run started" in caplog.text


def test_a_finished_run_is_left_alone(tmp_path, caplog):
    db = ManifestDB(tmp_path)
    first = db.start_run()
    finished_at = db.finish_run(first)["finished_at"]
    with caplog.at_level(logging.WARNING, logger="backup_engine"):
        db.start_run()
    assert db._conn.execute("SELECT finished_at FROM runs WHERE id = ?", (first,)).fetchone()[0] == finished_at
    assert "new run started" not in caplog.text


# -- W11 ---------------------------------------------------------------------


def test_the_run_summary_names_the_files_that_failed(store, tmp_path, caplog):
    a = _profile(store, tmp_path)
    client = TestClient(app_module.app)
    run_id = client.post("/run/start", headers=_headers(a)).json()["run_id"]
    for name in ("IMG_1.MOV", "IMG_2.MOV"):
        client.post("/upload", headers=_headers(a), params={"filename": name, "taken_at": TAKEN_AT, "run_id": run_id}, content=b"")
    # IMG_2 arrives on a retry within the same run, so it's no longer an error.
    client.post("/upload", headers=_headers(a), params={"filename": "IMG_2.MOV", "taken_at": TAKEN_AT, "run_id": run_id}, content=b"video")
    with caplog.at_level(logging.INFO, logger="backup_engine"):
        result = client.post("/run/finish", headers=_headers(a), data={"run_id": run_id}).json()
    assert result["files_error"] == 1 and result["files_new"] == 1
    assert "error_files" not in result  # the Shortcut's response keeps its shape
    finish_line = next(r.getMessage() for r in caplog.records if "run finished" in r.getMessage())
    assert "IMG_1.MOV" in finish_line and "IMG_2.MOV" not in finish_line


def test_no_diagnostic_lines_left(store, tmp_path, caplog):
    a = _profile(store, tmp_path)
    client = TestClient(app_module.app)
    run_id = client.post("/run/start", headers=_headers(a)).json()["run_id"]
    with caplog.at_level(logging.INFO, logger="backup_engine"):
        for _ in range(2):  # the second is a duplicate skip, where DIAG lines used to be
            client.post("/upload", headers=_headers(a), params={"filename": "IMG_3.JPG", "taken_at": TAKEN_AT, "run_id": run_id}, content=b"photo")
    assert "DIAG" not in caplog.text


# -- W12 ---------------------------------------------------------------------


def test_tokens_still_match_exactly(store, tmp_path):
    a, b = _profile(store, tmp_path, "A"), _profile(store, tmp_path, "B")
    assert store.find_by_token(a.token).id == a.id
    assert store.find_by_token(b.token).id == b.id
    assert store.find_by_token(a.token[:-1]) is None
    assert store.find_by_token("") is None
    assert store.find_by_token("ñ-not-ascii") is None


def test_a_device_sending_wrong_tokens_gets_a_short_pause(store, tmp_path, monkeypatch, caplog):
    a = _profile(store, tmp_path)
    clock = [1000.0]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: clock[0])
    client = TestClient(app_module.app)
    with caplog.at_level(logging.WARNING, logger="backup_engine"):
        codes = [client.post("/check", headers={"X-Backup-Token": "wrong"}, data={"filename": "x.jpg"}).status_code
                 for _ in range(app_module.BAD_TOKEN_LIMIT)]
    assert codes == [401] * app_module.BAD_TOKEN_LIMIT
    assert caplog.text.count("wrong tokens in a minute") == 1
    # Paused: even a request with the right token from that device waits.
    assert client.post("/check", headers=_headers(a), data={"filename": "x.jpg"}).status_code == 429
    clock[0] += app_module.BAD_TOKEN_WINDOW + 1
    assert client.post("/check", headers=_headers(a), data={"filename": "x.jpg"}).status_code == 200


def test_the_right_token_never_counts_towards_the_pause(store, tmp_path):
    a = _profile(store, tmp_path)
    client = TestClient(app_module.app)
    for _ in range(app_module.BAD_TOKEN_LIMIT * 2):
        assert client.post("/check", headers=_headers(a), data={"filename": "x.jpg"}).status_code == 200


def test_a_few_wrong_tokens_spread_out_never_pause(store, tmp_path, monkeypatch):
    a = _profile(store, tmp_path)
    clock = [1000.0]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: clock[0])
    client = TestClient(app_module.app)
    for _ in range(app_module.BAD_TOKEN_LIMIT * 2):
        client.post("/check", headers={"X-Backup-Token": "wrong"}, data={"filename": "x.jpg"})
        clock[0] += 10  # one every 10 s: 6 a minute, under the limit
    assert client.post("/check", headers=_headers(a), data={"filename": "x.jpg"}).status_code == 200


# -- Roadmap 11 ----------------------------------------------------------------


def test_status_and_card_show_how_much_the_backup_takes(store, tmp_path):
    a = _profile(store, tmp_path)
    client = TestClient(app_module.app)
    for i, size in enumerate((1_500_000, 2_500_000)):
        client.post("/upload", headers=_headers(a), params={"filename": f"IMG_{i}.JPG", "taken_at": TAKEN_AT},
                    content=bytes([i]) * size)
    status = app_module.get_status_for_profile(a)
    assert status["total_bytes"] == 4_000_000
    assert "2 archivos, 4 MB" in _profile_stats_text(a, "es", status)


def test_size_text():
    assert _size_text(188_855_939_374, "es") == "188,9 GB"
    assert _size_text(188_855_939_374, "en") == "188.9 GB"
    assert _size_text(4_000_000, "en") == "4 MB"
    assert _size_text(0, "es") == "0 MB"
