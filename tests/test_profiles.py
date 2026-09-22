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


def test_old_profiles_json_without_mirror_fields_still_loads(store, tmp_path):
    """profiles.json files saved before this feature existed have no
    mirror_dir/mirror_history keys at all -- Profile(**item) must still
    construct fine, falling back to the dataclass defaults (see PLAN.md
    section 13.2)."""
    import json

    old_style = {
        "profiles": [{
            "id": "abc123",
            "name": "iPhone de Laura",
            "slug": "iphone-de-laura",
            "token": "tok",
            "created_at": "2026-01-01T00:00:00+00:00",
            "enabled": True,
            "destination_dir": str(tmp_path / "usb1"),
            "destination_history": [],
            # no mirror_dir / mirror_history keys at all -- pre-feature file
        }]
    }
    profiles_module.PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    profiles_module.PROFILES_PATH.write_text(json.dumps(old_style), encoding="utf-8")

    reloaded = ProfileStore()
    again = reloaded.get("abc123")
    assert again is not None
    assert again.mirror_dir is None
    assert again.mirror_history == []


def test_set_mirror_destination_records_a_volume_snapshot_independent_of_primary(store, tmp_path):
    profile = store.add("iPhone de Laura")
    store.set_destination(profile.id, str(tmp_path / "usb1"))
    store.set_mirror_destination(profile.id, str(tmp_path / "usb2-mirror"))

    updated = store.get(profile.id)
    assert updated.destination_dir == str(tmp_path / "usb1")  # untouched
    assert updated.mirror_dir == str(tmp_path / "usb2-mirror")
    assert len(updated.destination_history) == 1
    assert len(updated.mirror_history) == 1
    assert updated.current_mirror_volume["path"] == str(tmp_path / "usb2-mirror")


def test_mirror_cannot_be_the_same_folder_as_the_primary_destination(store, tmp_path):
    profile = store.add("iPhone de Laura")
    dest = tmp_path / "usb1"
    store.set_destination(profile.id, str(dest))

    with pytest.raises(ValueError):
        store.set_mirror_destination(profile.id, str(dest))

    assert store.get(profile.id).mirror_dir is None  # rejected, nothing saved


def test_clear_mirror_destination_unlinks_without_deleting_history(store, tmp_path):
    profile = store.add("iPhone de Laura")
    store.set_mirror_destination(profile.id, str(tmp_path / "usb2-mirror"))

    store.clear_mirror_destination(profile.id)

    updated = store.get(profile.id)
    assert updated.mirror_dir is None
    assert len(updated.mirror_history) == 1  # history kept, only the active link is cleared
