"""Tests for ProfileStore — identity, destination history/volume tracking."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import server.profiles as profiles_module
from server.profiles import ProfileStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", tmp_path / "profiles.json")
    return ProfileStore()


def test_set_destination_records_a_volume_snapshot(store, tmp_path):
    profile = store.add("iPhone de Laura")
    dest = tmp_path / "usb1"
    store.set_destination(profile.id, str(dest))

    updated = store.get(profile.id)
    assert updated.destination_dir == str(dest)
    assert len(updated.destination_history) == 1
    snap = updated.current_volume
    assert snap["path"] == str(dest)
    assert "recorded_at" in snap
    # volume_label/serial can be None depending on the filesystem, but the
    # keys must always be present so the GUI can render them safely.
    assert "volume_label" in snap and "volume_serial" in snap
    assert "total_bytes" in snap and "free_bytes" in snap


def test_destination_history_accumulates_across_changes(store, tmp_path):
    profile = store.add("iPhone de Laura")
    store.set_destination(profile.id, str(tmp_path / "usb1"))
    store.set_destination(profile.id, str(tmp_path / "usb2"))

    updated = store.get(profile.id)
    assert len(updated.destination_history) == 2
    assert updated.destination_dir == str(tmp_path / "usb2")
    assert updated.current_volume["path"] == str(tmp_path / "usb2")
    # Older entry is still there for the user to recognize past drives.
    assert updated.destination_history[0]["path"] == str(tmp_path / "usb1")


def test_history_survives_reload_from_disk(store, tmp_path):
    profile = store.add("iPhone de Laura")
    store.set_destination(profile.id, str(tmp_path / "usb1"))

    reloaded = ProfileStore()  # re-reads PROFILES_PATH (monkeypatched to the same file)
    again = reloaded.get(profile.id)
    assert again is not None
    assert len(again.destination_history) == 1
