"""Where things live — different depending on whether the app is running
from source (dev) or as a packaged/installed PyInstaller build.

- `app_root()`: read-only bundled assets (e.g. assets/punkbackup.ico).
  Dev mode: the project folder. Frozen: PyInstaller's `sys._MEIPASS`.
- `user_data_dir()`: writable per-user data — config.json, profiles.json
  (which holds secrets). Dev mode: `config/` next to the project, so the
  repo-local workflow used throughout development keeps working unchanged.
  Frozen: `%APPDATA%\\PunkBackup`, since an installed app's own folder
  (typically under Program Files) usually isn't writable by a normal user,
  and mixing user data into the program's install directory is bad
  practice regardless.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    if is_frozen():
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        return base / "PunkBackup"
    return Path(__file__).resolve().parent.parent / "config"
