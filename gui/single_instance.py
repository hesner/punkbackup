"""Only one PunkBackup open at a time (v1.8.10).

Two copies would fight over the port and both poll the same index. A second launch
brings the open window to the front instead. It also covers the first launch after an
install, when Avast runs a copy in its sandbox and closes it before opening the real
one: a second copy waits a few seconds for the first to close and, if it does, opens
normally instead of quitting.

Plain ctypes on Windows, no import of the GUI, so main.py can check before loading
customtkinter. Anywhere else (or if Windows refuses the mutex) nothing is blocked.
"""
import sys

MUTEX_NAME = "PunkBackup.SingleInstance"  # also AppMutex in installer/PunkBackup.iss
WINDOW_TITLE_PREFIX = "PunkBackup — v"  # gui/main_window.py: f"{APP_TITLE} — v{APP_VERSION}"
WAIT_FOR_FIRST_MS = 8000

_WAIT_OBJECT_0 = 0x0
_WAIT_ABANDONED = 0x80
_SW_RESTORE = 9


class _Lock:
    """Holds the mutex for the life of the process; Windows frees it on exit."""

    def __init__(self, handle):
        self.handle = handle

    def release(self) -> None:
        if self.handle and sys.platform == "win32":
            k32 = _kernel32()
            k32.ReleaseMutex(self.handle)
            k32.CloseHandle(self.handle)
        self.handle = None


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    return k32


def acquire(name: str = MUTEX_NAME, on_busy=None, wait_ms: int = WAIT_FOR_FIRST_MS):
    """The lock if this is the only copy (or the other one closed within `wait_ms`),
    None if another copy stays open. `on_busy()` runs once, right when another copy
    is found, before waiting."""
    if sys.platform != "win32":
        return _Lock(None)
    k32 = _kernel32()
    handle = k32.CreateMutexW(None, False, name)
    if not handle:
        return _Lock(None)  # can't tell: never stop the app from opening
    if k32.WaitForSingleObject(handle, 0) in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
        return _Lock(handle)
    if on_busy is not None:
        try:
            on_busy()
        except Exception:
            pass
    if k32.WaitForSingleObject(handle, wait_ms) in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
        return _Lock(handle)
    k32.CloseHandle(handle)
    return None


def show_existing_window(prefix: str = WINDOW_TITLE_PREFIX) -> bool:
    """Restore and focus the open PunkBackup window. True if one was found."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith(prefix):
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return False
    hwnd = found[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, _SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True
