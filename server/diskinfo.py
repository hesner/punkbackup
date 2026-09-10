"""Windows volume information — lets the app recognize/label WHICH physical
drive a profile's destination folder is on (label, serial number, capacity),
even though the drive letter can change every time a USB stick is plugged
back in. Pure ctypes/stdlib, no extra dependency.
"""
from __future__ import annotations

import ctypes
import shutil
from pathlib import Path
from typing import Optional, TypedDict


class VolumeInfo(TypedDict):
    drive_root: str
    volume_label: Optional[str]
    volume_serial: Optional[str]  # 8-hex-digit Windows volume serial number
    total_bytes: Optional[int]
    free_bytes: Optional[int]


def get_volume_info(path) -> VolumeInfo:
    resolved = Path(path).resolve()
    drive_root = f"{resolved.drive}\\" if resolved.drive else resolved.anchor or str(resolved)

    total_bytes: Optional[int] = None
    free_bytes: Optional[int] = None
    try:
        total_bytes, _used, free_bytes = shutil.disk_usage(drive_root)
    except OSError:
        pass

    volume_label: Optional[str] = None
    volume_serial: Optional[str] = None
    try:
        name_buf = ctypes.create_unicode_buffer(1024)
        fs_name_buf = ctypes.create_unicode_buffer(1024)
        serial = ctypes.c_uint(0)
        max_component_len = ctypes.c_uint(0)
        fs_flags = ctypes.c_uint(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(drive_root),
            name_buf, ctypes.sizeof(name_buf),
            ctypes.byref(serial),
            ctypes.byref(max_component_len),
            ctypes.byref(fs_flags),
            fs_name_buf, ctypes.sizeof(fs_name_buf),
        )
        if ok:
            volume_label = name_buf.value or None
            volume_serial = f"{serial.value:08X}"
    except (OSError, AttributeError, ValueError):
        pass  # non-Windows, or the call failed — degrade gracefully

    return {
        "drive_root": drive_root,
        "volume_label": volume_label,
        "volume_serial": volume_serial,
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
    }


def format_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
