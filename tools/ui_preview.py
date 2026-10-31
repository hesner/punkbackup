"""Test application: opens the REAL interface with a simulated iPhone and
throwaway data, so every state of cable mode can be tried without a phone and
without touching real profiles, the real USB or the Windows startup setting.

    .venv\\Scripts\\python.exe tools\\ui_preview.py

A small "Simulador" window controls the phone. Not part of the installer.
With --shots <folder> it walks through the states by itself and saves a
screenshot of each, for checking the design without clicking.
"""
from __future__ import annotations

import hashlib
import io
import random
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TEMP = Path(tempfile.mkdtemp(prefix="punkbackup-preview-"))

# Must happen before anything imports server.config/server.profiles, which
# resolve their paths at import time.
import server.paths  # noqa: E402

server.paths.user_data_dir = lambda: _TEMP / "config"

import customtkinter as ctk  # noqa: E402

from gui import main_window  # noqa: E402
from server.config import AppConfig  # noqa: E402
from server.device_source import DeviceInfo, DeviceItem, DeviceReadError  # noqa: E402
from server.manifest_db import ManifestDB  # noqa: E402
from server.profiles import ProfileStore  # noqa: E402
from server.storage import BackupEngine  # noqa: E402

main_window.set_start_with_windows = lambda _enabled: None  # never touch the real registry key


def _fake_jpeg(seed: int) -> bytes:
    rng = random.Random(seed)
    return b"\xff\xd8\xff" + rng.randbytes(rng.randint(200_000, 900_000))


class SimulatedPhone:
    def __init__(self, count: int = 120):
        self.connected = True
        self.unlocked = True
        self.fail_after: float | None = None
        self.delay = 0.04
        self.files: dict[str, tuple[bytes, str]] = {}
        for i in range(count):
            month = 1 + i % 10
            self.files[f"IMG_{1000 + i}.JPG"] = (_fake_jpeg(i), f"2026-{month:02d}-15T10:00:{i % 60:02d}")

    def info(self) -> list[DeviceInfo]:
        if not self.connected:
            return []
        return [DeviceInfo("sim", "Apple iPhone", "SIM-SERIAL-1", self.unlocked)]


class _Source:
    def __init__(self, phone: SimulatedPhone):
        self.phone = phone

    def list_items(self, on_progress=None, cancel=None):
        items = []
        for i, (name, (data, date)) in enumerate(self.phone.files.items(), start=1):
            if cancel is not None and cancel.is_set():
                return items
            time.sleep(0.005)
            items.append(DeviceItem(name, name, len(data), date))
            if on_progress:
                on_progress(i)
        return items

    def open_reader(self, item):
        time.sleep(self.phone.delay)
        if not self.phone.connected or not self.phone.unlocked:
            raise DeviceReadError("the phone stopped responding")
        return io.BytesIO(self.phone.files[item.name][0])

    def reopen(self):
        pass

    def close(self):
        pass


class SimulatedBackend:
    def __init__(self, phone: SimulatedPhone):
        self.phone = phone

    @contextmanager
    def com_thread(self):
        yield

    def find_devices(self):
        return self.phone.info()

    def open_source(self, _device):
        return _Source(self.phone)


def _seed(phone: SimulatedPhone) -> None:
    (_TEMP / "config").mkdir(parents=True, exist_ok=True)
    cfg = AppConfig()
    cfg.port = 8799  # never collides with the real app, which may be running
    if "--lang" in sys.argv:
        cfg.language = sys.argv[sys.argv.index("--lang") + 1]
    cfg.save()
    store = ProfileStore()
    first = store.add("iphone de Hes")
    store.set_destination(first.id, str(_TEMP / "USB_A"))
    second = store.add("ipad")
    store.set_destination(second.id, str(_TEMP / "USB_B"))
    store.set_enabled(second.id, False)
    store.add("sin carpeta")

    # A third of the phone is already there, as if WiFi had saved it.
    dest = _TEMP / "USB_A"
    dest.mkdir(parents=True, exist_ok=True)
    db = ManifestDB(dest, profile_label=first.name)
    engine = BackupEngine(dest, db)
    for i, (name, (data, date)) in enumerate(phone.files.items()):
        if i % 3 == 0:
            engine.process_upload(name, io.BytesIO(data), date, None)
        elif i % 3 == 1 and i < 30:  # same bytes under the name the Shortcut would use
            engine.process_upload(f"{hashlib.md5(name.encode()).hexdigest()}.jpeg", io.BytesIO(data), date, None)
    db.close()


def _build_simulator(window, phone: SimulatedPhone) -> None:
    sim = ctk.CTkToplevel(window)
    sim.title("Simulador de iPhone")
    sim.geometry("280x210")
    sim.attributes("-topmost", True)

    def toggle(attr: str, button: ctk.CTkButton, on: str, off: str) -> None:
        setattr(phone, attr, not getattr(phone, attr))
        button.configure(text=off if getattr(phone, attr) else on)

    plug = ctk.CTkButton(sim, text="Desconectar iPhone")
    plug.configure(command=lambda: toggle("connected", plug, "Conectar iPhone", "Desconectar iPhone"))
    plug.pack(fill="x", padx=12, pady=(12, 6))
    lock = ctk.CTkButton(sim, text="Bloquear iPhone")
    lock.configure(command=lambda: toggle("unlocked", lock, "Desbloquear iPhone", "Bloquear iPhone"))
    lock.pack(fill="x", padx=12, pady=6)
    speed = ctk.CTkButton(sim, text="Copia lenta")

    def toggle_speed() -> None:
        phone.delay = 0.5 if phone.delay < 0.5 else 0.04
        speed.configure(text="Copia rápida" if phone.delay >= 0.5 else "Copia lenta")

    speed.configure(command=toggle_speed)
    speed.pack(fill="x", padx=12, pady=6)
    ctk.CTkLabel(sim, text=f"Datos temporales en:\n{_TEMP}", wraplength=260, font=ctk.CTkFont(size=10)).pack(padx=12)


def _auto_tour(window, phone: SimulatedPhone, out: Path) -> None:
    """Drives the interface step by step on its own. Step functions run on the
    Tk thread; waiting happens between them, never inside."""
    from PIL import ImageGrab

    out.mkdir(parents=True, exist_ok=True)
    main_window.ask_yes_no = lambda *a, **k: True

    def shot(name: str):
        def take():
            window.update_idletasks()
            x, y = window.winfo_rootx(), window.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height())).save(out / f"{name}.png")
        return take

    def row():
        return next(r for r in window._principal_rows.values() if r.profile.name == "iphone de Hes")

    steps = [
        (1500, shot("1_wifi")),
        (200, window._on_mode_button),
        (5000, shot("2_cable_listo")),
        (200, lambda: setattr(phone, "connected", False)),
        (3800, shot("3_cable_sin_iphone")),
        (200, lambda: setattr(phone, "connected", True)),
        (3800, lambda: window._on_cable_action(row().profile, "start")),
        (300, shot("4_analizando")),
        (3000, shot("5_resumen")),
        (200, lambda: setattr(phone, "delay", 0.25)),
        (200, lambda: window._on_cable_action(row().profile, "copy")),
        (6000, shot("6_copiando")),
        (200, lambda: window._on_cable_action(row().profile, "cancel")),
        (1500, shot("7_detenido")),
        (200, lambda: setattr(phone, "delay", 0.0)),
        (200, lambda: window._on_cable_action(row().profile, "start")),
        (3000, lambda: window._on_cable_action(row().profile, "copy")),
        (8000, shot("8_listo")),
        (200, lambda: window._set_language("es" if window.lang == "en" else "en")),
        (500, shot("8b_idioma_cambiado_en_vivo")),
        (200, lambda: window._set_language("es" if window.lang == "en" else "en")),
        (200, lambda: window._show_screen("settings")),
        (800, shot("9_configuracion_cable")),
        (200, lambda: window._show_screen("main")),
        (200, window._on_mode_button),
        (2500, shot("10_wifi_de_vuelta")),
        (200, lambda: (print("tour ok", window.cable_mode, window.state()), window._on_close())),
    ]

    def run(i: int = 0) -> None:
        if i >= len(steps):
            return
        delay, action = steps[i]

        def fire() -> None:
            action()
            run(i + 1)

        window.after(delay, fire)

    window.after(1500, run)


def main() -> None:
    phone = SimulatedPhone()
    _seed(phone)
    window = main_window.MainWindow(cable_backend=SimulatedBackend(phone))
    window.title(window.title() + " — APLICACIÓN DE PRUEBA")
    if "--shots" in sys.argv:
        _auto_tour(window, phone, Path(sys.argv[sys.argv.index("--shots") + 1]))
    else:
        _build_simulator(window, phone)
    try:
        window.mainloop()
    finally:
        import logging

        for handler in list(window._file_logger.handlers):
            handler.close()
        shutil.rmtree(_TEMP, ignore_errors=True)


if __name__ == "__main__":
    main()
