"""App-level configuration (NOT profiles, NOT the per-destination backup
index). Stored at config/config.json (gitignored). Just the port and the
last destination folder used, so the GUI can pre-fill it.

Per-device/person identity and secrets live in profiles.py instead — see
that module for why authentication moved from one global token to one
token per profile.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import user_data_dir

CONFIG_DIR = user_data_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_PORT = 8787


DEFAULT_IDLE_TIMEOUT_MINUTES = 5


@dataclass
class AppConfig:
    port: int = DEFAULT_PORT
    last_destination_dir: str | None = None
    language: str = "es"  # "es" or "en" — GUI display language, switchable live
    start_with_windows: bool = False  # launch PunkBackup.exe at Windows login
    auto_start_backup: bool = False  # call "Start backup" automatically right after opening
    idle_timeout_minutes: int = DEFAULT_IDLE_TIMEOUT_MINUTES  # see MainWindow._check_idle_backups

    @staticmethod
    def load() -> "AppConfig":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return AppConfig(**{**asdict(AppConfig()), **data})
        return AppConfig()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )
