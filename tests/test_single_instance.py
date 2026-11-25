"""v1.8.10: only one PunkBackup open at a time (gui/single_instance.py). A second copy
brings the first to the front and quits, unless the first closes within a few
seconds (Avast's sandbox copy on the first launch after an install).

Each test uses its own mutex name, so a real PunkBackup open on this PC never
interferes. The holder is a separate process, like a real second launch.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui import single_instance

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows mutex")

HOLDER = """
import sys
sys.path.insert(0, {root!r})
from gui.single_instance import acquire
lock = acquire({name!r}, wait_ms=0)
print("held" if lock else "busy", flush=True)
sys.stdin.readline()
"""


def _name():
    return f"PunkBackup.Test.{uuid.uuid4().hex}"


def _start_holder(name):
    proc = subprocess.Popen([sys.executable, "-c", HOLDER.format(root=str(ROOT), name=name)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def _stop(proc):
    proc.stdin.close()
    proc.wait(10)


def test_the_first_copy_opens():
    lock = single_instance.acquire(_name(), wait_ms=0)
    assert lock is not None and lock.handle
    lock.release()


def test_a_second_copy_shows_the_first_and_quits():
    name = _name()
    holder = _start_holder(name)
    try:
        calls = []
        started = time.monotonic()
        assert single_instance.acquire(name, on_busy=lambda: calls.append(1), wait_ms=300) is None
        assert calls == [1]  # the open window is brought forward right away, not after the wait
        assert time.monotonic() - started < 3
    finally:
        _stop(holder)


def test_a_second_copy_opens_if_the_first_closes_meanwhile():
    """Avast's sandbox copy closes a moment later: the real one must still open."""
    name = _name()
    holder = _start_holder(name)
    closer = threading.Timer(0.5, _stop, [holder])
    closer.start()
    calls = []
    lock = single_instance.acquire(name, on_busy=lambda: calls.append(1), wait_ms=5000)
    closer.join()
    assert calls == [1]  # it was busy at first
    assert lock is not None and lock.handle
    lock.release()


def test_a_crashed_first_copy_never_blocks_the_next():
    name = _name()
    holder = _start_holder(name)
    holder.kill()
    holder.wait(10)
    lock = single_instance.acquire(name, wait_ms=0)
    assert lock is not None and lock.handle  # Windows hands over an abandoned mutex
    lock.release()


def test_once_released_the_next_copy_opens():
    name = _name()
    first = single_instance.acquire(name, wait_ms=0)
    first.release()
    holder = _start_holder(name)  # would print "busy" and fail if still held
    _stop(holder)


def test_no_window_found_is_not_an_error():
    assert single_instance.show_existing_window(f"no window is called {uuid.uuid4().hex}") is False


def test_names_match_the_window_title_and_the_installer():
    window = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")
    assert 'APP_TITLE = "PunkBackup"' in window
    assert 'self.title(f"{APP_TITLE} — v{APP_VERSION}")' in window
    assert single_instance.WINDOW_TITLE_PREFIX == "PunkBackup — v"
    installer = (ROOT / "installer" / "PunkBackup.iss").read_text(encoding="utf-8")
    assert re.search(r"^AppMutex=(.+)$", installer, re.M).group(1).strip() == single_instance.MUTEX_NAME
