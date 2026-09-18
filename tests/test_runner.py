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
