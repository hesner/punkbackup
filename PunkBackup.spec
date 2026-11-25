# -*- mode: python ; coding: utf-8 -*-
import re

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

# Antivirus false positives (PLAN.md, v1.8.10): the bootloader in .venv is compiled
# from PyInstaller's source on this PC instead of the stock one shared with a lot of
# malware (see docs/BUILD_BOOTLOADER.md), the exe carries a real version resource
# (an exe without one looks suspicious to heuristics), and UPX stays off: packed
# executables are a classic trigger.
import hashlib
from pathlib import Path

import PyInstaller

# Refuse to build with the stock bootloader (a fresh .venv brings it back).
_STOCK_RUNW = {"87b0c589906a5d690c26c602bf2ee7e43b3eab55574bf72887a8ca07fbb2dba0"}  # PyInstaller 6.22.2 wheel
_runw = Path(PyInstaller.__file__).parent / "bootloader" / "Windows-64bit-intel" / "runw.exe"
if hashlib.sha256(_runw.read_bytes()).hexdigest() in _STOCK_RUNW:
    raise SystemExit("Stock PyInstaller bootloader in .venv: rebuild it first (docs/BUILD_BOOTLOADER.md).")

VERSION = re.search(r'APP_VERSION = "([^"]+)"', open("server/version.py", encoding="utf-8").read()).group(1)
_nums = tuple(int(n) for n in VERSION.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_nums, prodvers=_nums),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "PunkBackup"),
            StringStruct("FileDescription", "PunkBackup - iPhone photo and video backup to this PC"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "PunkBackup"),
            StringStruct("OriginalFilename", "PunkBackup.exe"),
            StringStruct("ProductName", "PunkBackup"),
            StringStruct("ProductVersion", VERSION),
            StringStruct("LegalCopyright", "PunkBackup"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [('assets', 'assets')]
datas += collect_data_files('customtkinter')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules('comtypes'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PunkBackup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/punkbackup.ico'],
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PunkBackup',
)
