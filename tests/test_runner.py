"""Tests for ServerController — specifically that a bind failure is
actually detectable, instead of dying silently in a background thread.

Confirmed on a real device (2026-09-18): the GUI showed "Escuchando en
el puerto 8787" while nothing was really listening (a background-thread
bind failure that went nowhere, since pythonw.exe redirects stderr to a
throwaway buffer) — the iPhone got "Could not connect to the server"
with zero indication anything was wrong on the PC side.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from server.runner import ServerController


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_force_stop_cuts_an_upload_in_progress_and_records_nothing(tmp_path):
    from server import app as app_module
    from server.manifest_db import ManifestDB

    class Store:
        def __init__(self, profile):
            self.profile = profile

        def list(self):
            return [self.profile]

        def find_by_token(self, _token):
            return self.profile

    class P:
        id, name, enabled, destination_dir = "p1", "p", True, str(tmp_path)

    app_module.configure(Store(P))
    port = _free_port()
    controller = ServerController(app_module.app, host="127.0.0.1", port=port)
    controller.start()
    assert controller.wait_until_listening(timeout=5.0)

    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.sendall(
        b"POST /upload?filename=BIG.MOV&taken_at=2026-01-01T00:00:00 HTTP/1.1\r\nHost: x\r\n"
        b"X-Backup-Token: t\r\nContent-Length: 100000000\r\n\r\n" + b"x" * 200000
    )
    staging = tmp_path / ".iphone_backup_index" / "staging"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not (staging.exists() and list(staging.iterdir())):
        time.sleep(0.02)
    assert list(staging.iterdir()), "the upload never started"

    started = time.monotonic()
    controller.stop(timeout=8.0, force=True)
    client.close()
    assert not controller.running
    assert time.monotonic() - started < 8.0

    app_module.close_open_runs()
    app_module.forget_profile("p1")
    assert list(staging.iterdir()) == []
    db = ManifestDB(tmp_path, reap_dangling_runs=False)
    assert db.get_status()["total_files_backed_up"] == 0
    db.close()
    assert not (tmp_path / "2026").exists()


def test_successful_start_is_confirmed_listening():
    app = FastAPI()
    port = _free_port()
    controller = ServerController(app, host="127.0.0.1", port=port)
    try:
        controller.start()
        assert controller.wait_until_listening(timeout=5.0) is True
        assert controller.actually_listening is True
        assert controller.start_error is None

        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            pass  # a real connection succeeding is the actual proof
    finally:
        controller.stop()


def test_port_conflict_is_detected_not_silent():
    app = FastAPI()
    port = _free_port()
    holder = ServerController(app, host="127.0.0.1", port=port)
    blocker = ServerController(FastAPI(), host="127.0.0.1", port=port)
    try:
        holder.start()
        assert holder.wait_until_listening(timeout=5.0) is True

        blocker.start()
        assert blocker.wait_until_listening(timeout=5.0) is False
        assert blocker.actually_listening is False
        assert blocker.start_error  # some non-empty reason was captured
    finally:
        holder.stop()
        blocker.stop()


def test_start_with_retry_succeeds_once_the_transient_conflict_clears():
    """Covers the confirmed Avast scenario: the port is briefly held by
    something that releases it a moment later — start_with_retry() should
    paper over that instead of failing on the very first attempt."""
    app = FastAPI()
    port = _free_port()

    blocking_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocking_socket.bind(("127.0.0.1", port))
    blocking_socket.listen(1)

    def release_after_a_moment() -> None:
        time.sleep(0.3)
        blocking_socket.close()

    threading.Thread(target=release_after_a_moment, daemon=True).start()

    controller = ServerController(app, host="127.0.0.1", port=port)
    try:
        assert controller.start_with_retry(attempts=4, retry_delay=0.3) is True
        assert controller.actually_listening is True
    finally:
        controller.stop()
        try:
            blocking_socket.close()
        except OSError:
            pass


def test_start_with_retry_gives_up_after_all_attempts_fail():
    app = FastAPI()
    port = _free_port()
    permanent_blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    permanent_blocker.bind(("127.0.0.1", port))
    permanent_blocker.listen(1)

    controller = ServerController(app, host="127.0.0.1", port=port)
    try:
        assert controller.start_with_retry(attempts=2, retry_delay=0.1) is False
        assert controller.actually_listening is False
        assert controller.start_error
    finally:
        controller.stop()
        permanent_blocker.close()
