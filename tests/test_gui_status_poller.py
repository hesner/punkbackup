"""Tests for gui/main_window.py's _compute_status_snapshot — the ONE
function that does all the disk/SQLite work the GUI's periodic refresh
needs, deliberately kept as a plain module-level function with no Tkinter
dependency so it can run on a background thread (see AGENTS.md lesson 22
and PLAN.md's write-up on the ~10s window-switch freeze this fixed).

Nothing else in gui/main_window.py is unit tested (this project's
established convention — the Tkinter layer itself is smoke-tested by
hand, not pytest) but this function is pure business logic wearing a GUI
module's address, so it gets the same direct-unit-test treatment
BackupEngine/ManifestDB already get.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from server import app as app_module
import server.profiles as profiles_module
from server.manifest_db import ManifestDB
from server.profiles import ProfileStore
from server.storage import BackupEngine
from gui.main_window import _compute_status_snapshot, _destination_is_valid, _profile_stats_text


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", tmp_path / "profiles.json")
    s = ProfileStore()
    app_module.configure(s)
    return s


def test_snapshot_has_independent_entries_per_profile(store, tmp_path):
    p1 = store.add("iPhone de Hesner")
    dest1 = tmp_path / "dest1"
    store.set_destination(p1.id, str(dest1))
    p2 = store.add("iPad")
    store.set_destination(p2.id, str(tmp_path / "dest2"))

    # Give profile 1 one real backed-up file so its status is distinguishable
    # -- written directly via BackupEngine/ManifestDB (same pattern as
    # test_backup_engine.py's make_engine), not through app_module's
    # internal engine cache, to keep this test focused on the snapshot
    # function rather than app.py's caching internals.
    dest1.mkdir()
    engine = BackupEngine(dest1, ManifestDB(dest1, profile_label=p1.name))
    engine.process_upload("IMG_1.jpg", io.BytesIO(b"hello"), "2026-01-01T00:00:00", None)

    snapshot = _compute_status_snapshot(store.list())
    per_profile = snapshot["per_profile"]

    assert per_profile[p1.id]["status"]["total_files_backed_up"] == 1
    assert per_profile[p2.id]["status"]["total_files_backed_up"] == 0
    assert per_profile[p1.id]["mirror_status"] is None  # no mirror configured
    assert snapshot["aggregate"]["total_files_backed_up"] == 1


def test_snapshot_skips_status_fetch_for_disabled_or_unconfigured_profiles(store, tmp_path):
    """Same rule _check_idle_backups already enforced (AGENTS.md point 17)
    — must not even attempt a status fetch for these, not just swallow the
    resulting error."""
    disabled = store.add("Perfil pausado")
    store.set_destination(disabled.id, str(tmp_path / "dest"))
    store.set_enabled(disabled.id, False)

    unconfigured = store.add("Perfil sin carpeta")

    snapshot = _compute_status_snapshot(store.list())
    per_profile = snapshot["per_profile"]

    assert per_profile[disabled.id]["status"] is None
    assert per_profile[disabled.id]["status_error"] is None
    assert per_profile[unconfigured.id]["status"] is None
    assert per_profile[unconfigured.id]["status_error"] is None


def test_snapshot_includes_mirror_status_when_mirror_configured(store, tmp_path):
    p = store.add("iPhone de Hesner")
    dest = tmp_path / "dest"
    mirror = tmp_path / "mirror"
    store.set_destination(p.id, str(dest))
    store.set_mirror_destination(p.id, str(mirror))

    snapshot = _compute_status_snapshot(store.list())
    entry = snapshot["per_profile"][p.id]

    # Mirror folder doesn't exist on disk yet -- get_mirror_status()
    # correctly reports "not connected" (None), not an error.
    assert entry["mirror_status"] is None

    mirror.mkdir()
    snapshot2 = _compute_status_snapshot(store.list())
    assert snapshot2["per_profile"][p.id]["mirror_status"] is not None
    assert snapshot2["per_profile"][p.id]["mirror_status"]["total_files"] == 0


def test_snapshot_flags_destination_unreachable_distinctly(store, tmp_path, monkeypatch):
    """An unplugged USB must be reported distinctly from BOTH a brand-new
    not-yet-existing folder (which mkdir() legitimately auto-creates, see
    test_snapshot_has_independent_entries_per_profile's dest2, unaffected
    by this test) and a genuinely unexpected error (which still gets the
    full "status_error" traceback, unchanged) -- see AGENTS.md lesson 26.
    Before this fix, both cases looked identical to the profile card: a
    silent "never backed up, 0 files" with no indication anything was
    wrong."""
    p = store.add("iPhone de Hesner")
    store.set_destination(p.id, str(tmp_path / "dest"))

    def failing_mkdir(self, *a, **k):
        raise OSError(3, "The system cannot find the path specified")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)

    snapshot = _compute_status_snapshot(store.list())
    entry = snapshot["per_profile"][p.id]

    assert entry["destination_unreachable"] is True
    assert entry["status"] is None
    assert entry["status_error"] is None


def test_stats_text_shows_not_connected_instead_of_stale_empty_stats(store, tmp_path):
    p = store.add("iPhone de Hesner")
    dest = tmp_path / "dest"
    store.set_destination(p.id, str(dest))

    text = _profile_stats_text(p, "es", status=None, destination_unreachable=True)
    assert str(dest) in text
    assert "conectad" in text.lower()  # "no conectada" -- distinct from the normal stats layout
    assert "0 archivos" not in text  # must not look like a real, empty-but-reachable destination


def test_destination_is_valid_for_a_real_writable_folder_even_if_not_created_yet(tmp_path):
    """A brand-new profile's first-ever destination doesn't exist on disk
    yet, but is perfectly valid -- mkdir() creates it. Deliberately NOT
    about whether it's a USB: an internal-drive folder is just as valid
    (see AGENTS.md lesson 27's addendum)."""
    dest = tmp_path / "not-created-yet"
    assert not dest.exists()
    assert _destination_is_valid(str(dest)) is True
    assert dest.is_dir()  # side effect is the same mkdir _engine_for relies on


def test_destination_is_valid_returns_false_for_an_unreachable_root(monkeypatch):
    """A drive root that doesn't exist at all (unplugged USB, or any other
    reason mkdir() can't create the path) must report False, not raise."""

    def failing_mkdir(self, *a, **k):
        raise OSError(3, "The system cannot find the path specified")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)
    assert _destination_is_valid("E:/does-not-exist") is False


def test_snapshot_never_raises_when_nothing_is_configured(store):
    """A brand-new profile store with zero profiles must produce a valid,
    empty-but-well-formed snapshot -- this runs on a background thread, so
    an uncaught exception here would be silently lost rather than shown
    anywhere."""
    snapshot = _compute_status_snapshot(store.list())
    assert snapshot == {"per_profile": {}, "aggregate": snapshot["aggregate"]}
    assert snapshot["aggregate"]["total_files_backed_up"] == 0
