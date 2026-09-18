"""Windows "launch at login" toggle for PunkBackup.

Uses the per-user registry Run key (HKCU, not HKLM) so toggling it never
needs admin/UAC — consistent with this project's rule that only the
one-time installer run ever needs elevation (see installer/PunkBackup.iss).
"""
from __future__ import annotations

import sys
import winreg

from server.paths import app_root, is_frozen

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PunkBackup"


def _launch_command() -> str:
    if is_frozen():
        return f'"{sys.executable}"'
    # Dev mode: sys.executable is the Python interpreter, not the app.
    main_py = app_root() / "main.py"
    return f'"{sys.executable}" "{main_py}"'


def set_start_with_windows(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
