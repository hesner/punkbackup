"""Device/person profiles — e.g. "iPhone de Laura", "iPad de Hesner".

Each profile is an independent identity: its own secret token, its own
subfolder under the chosen destination root, and therefore its own
incremental backup progress. Multiple people/devices can share one PC and
one destination drive without ever mixing up files — any profile can back
up at any time, in any order, without the PC user having to "switch" an
active profile first. The server just looks at which token came in and
routes the request to that profile's subfolder.

Stored at config/profiles.json (gitignored — it holds per-profile secrets).
"""
from __future__ import annotations

import json
import re
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .diskinfo import get_volume_info
from .paths import user_data_dir

PROFILES_PATH = user_data_dir() / "profiles.json"

MAX_DESTINATION_HISTORY = 20  # per profile — oldest entries drop off


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "perfil"


@dataclass
class Profile:
    id: str
    name: str
    slug: str  # filesystem-safe folder name, derived from `name` (kept for display/backward-compat)
    token: str
    created_at: str
    enabled: bool = True  # paused profiles keep their history but can't upload until re-enabled
    destination_dir: Optional[str] = None  # each profile backs up to its OWN folder/drive
    destination_history: list = field(default_factory=list)  # snapshots — see set_destination()
    # Optional second copy (mirror), synced PC-side from destination_dir — never touched by
    # the iPhone/Shortcut path. See PLAN.md section 13. Both fields default so old
    # profiles.json files without them still load fine via Profile(**item).
    mirror_dir: Optional[str] = None
    mirror_history: list = field(default_factory=list)  # snapshots — see set_mirror_destination()

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def current_volume(self) -> Optional[dict]:
        """The most recent destination snapshot, i.e. info about the drive
        `destination_dir` currently points at (label, serial, free space)."""
        return self.destination_history[-1] if self.destination_history else None

    @property
    def current_mirror_volume(self) -> Optional[dict]:
        """Same as current_volume, but for the optional second-copy drive."""
        return self.mirror_history[-1] if self.mirror_history else None


class ProfileStore:
    def __init__(self):
        self._profiles: dict[str, Profile] = {}
        self.load()

    def load(self) -> None:
        self._profiles = {}
        if PROFILES_PATH.exists():
            data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
            for item in data.get("profiles", []):
                p = Profile(**item)
                self._profiles[p.id] = p

    def save(self) -> None:
        PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"profiles": [p.to_dict() for p in self._profiles.values()]}
        PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def list(self) -> list[Profile]:
        return sorted(self._profiles.values(), key=lambda p: p.created_at)

    def _unique_slug(self, base: str) -> str:
        existing = {p.slug for p in self._profiles.values()}
        slug = base
        n = 2
        while slug in existing:
            slug = f"{base}-{n}"
            n += 1
        return slug

    def add(self, name: str) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("El nombre del perfil no puede estar vacío.")
        profile = Profile(
            id=uuid.uuid4().hex,
            name=name,
            slug=self._unique_slug(_slugify(name)),
            token=secrets.token_urlsafe(24),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._profiles[profile.id] = profile
        self.save()
        return profile

    def rename(self, profile_id: str, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("El nombre del perfil no puede estar vacío.")
        self._profiles[profile_id].name = new_name
        self.save()

    def regenerate_token(self, profile_id: str) -> str:
        new_token = secrets.token_urlsafe(24)
        self._profiles[profile_id].token = new_token
        self.save()
        return new_token

    def set_destination(self, profile_id: str, destination_dir: str) -> None:
        """Points the profile at a (possibly new) folder/drive and records a
        snapshot of that volume — label, serial number, capacity, free
        space — so the user can later recognize *which physical USB* this
        was, even if it gets a different drive letter next time it's
        plugged in. History keeps the last MAX_DESTINATION_HISTORY entries."""
        profile = self._profiles[profile_id]
        profile.destination_dir = destination_dir
        info = get_volume_info(destination_dir)
        snapshot = {**info, "path": destination_dir, "recorded_at": datetime.now(timezone.utc).isoformat()}
        profile.destination_history.append(snapshot)
        profile.destination_history = profile.destination_history[-MAX_DESTINATION_HISTORY:]
        self.save()

    def set_mirror_destination(self, profile_id: str, mirror_dir: str) -> None:
        """Points the profile's optional second copy at a (possibly new)
        folder/drive — same bookkeeping as set_destination(), kept
        entirely separate from destination_history so switching one never
        affects the other."""
        profile = self._profiles[profile_id]
        if profile.destination_dir and Path(mirror_dir) == Path(profile.destination_dir):
            # Would otherwise try to "mirror a folder into itself" — see
            # PLAN.md section 13.6.
            raise ValueError(
                "La segunda copia no puede ser la misma carpeta que el destino principal."
            )
        profile.mirror_dir = mirror_dir
        info = get_volume_info(mirror_dir)
        snapshot = {**info, "path": mirror_dir, "recorded_at": datetime.now(timezone.utc).isoformat()}
        profile.mirror_history.append(snapshot)
        profile.mirror_history = profile.mirror_history[-MAX_DESTINATION_HISTORY:]
        self.save()

    def clear_mirror_destination(self, profile_id: str) -> None:
        """Unlinks the second copy without touching any file already
        written there, and without erasing mirror_history — the same
        folder can be re-selected later and its own on-disk index (see
        server/mirror.py) picks up exactly where it left off."""
        self._profiles[profile_id].mirror_dir = None
        self.save()

    def set_enabled(self, profile_id: str, enabled: bool) -> None:
        """Pausing a profile blocks its token from uploading (403) without
        deleting it or touching any file it already backed up — unlike
        remove(), which revokes it entirely."""
        self._profiles[profile_id].enabled = enabled
        self.save()

    def remove(self, profile_id: str) -> None:
        """Removes the profile's registration only. Files already backed up
        under its subfolder are NOT deleted — this only revokes its token."""
        self._profiles.pop(profile_id, None)
        self.save()

    def find_by_token(self, token: str) -> Optional[Profile]:
        for p in self._profiles.values():
            if p.token == token:
                return p
        return None

    def get(self, profile_id: str) -> Optional[Profile]:
        return self._profiles.get(profile_id)
