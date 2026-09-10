"""Dashboard GUI — PunkBackup dark/industrial theme, two screens.

Opens fully idle: the destination folder is whatever was last used (editable),
and the backup server is OFF until the user clicks "Iniciar backup" — the app
never listens on the network on its own (see PLAN.md section 7).

Multi-profile, concurrent by design: any number of people/devices (e.g.
"iPhone de Laura", "iPad de Hesner") can be registered, each with its own
token and its own subfolder under the destination. There is no single
"active" profile — the server already isolates every profile by its token,
so several devices can upload at the same time. Two controls layer on top
of that instead:
  - one server-wide ON/OFF switch ("Iniciar backup" / "Detener backup"),
  - one Activo/Pausado switch PER profile, to temporarily block a
    specific device without deleting its history.

Two tabs:
  - "Principal": destination, server switch, connection info, live profile
    status (with the enable/pause switch), aggregate stats, collapsible log.
  - "Perfiles": full profile management (create/rename/regenerate/delete).
"""
from __future__ import annotations

import logging
import logging.handlers
import queue
import socket
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from server import app as app_module
from server.config import AppConfig
from server.diskinfo import format_bytes
from server.profiles import Profile, ProfileStore
from server.runner import ServerController

# PunkBackup: dark, industrial, deliberately rebellious. "Tus recuerdos. Tu
# USB. Cero dependencia de la nube." No cloud, no subscription, no light
# corporate dashboard vibes.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "PunkBackup"
TAGLINE = "🤘 Tus recuerdos. Tu USB. Cero dependencia de la nube."

BG = "#0c0c0e"            # near-black window background
CARD_BG = "#19191d"        # card/panel background
CARD_BG_ALT = "#221418"    # subtle warm-dark variant for the log panel
BORDER = "#2c2c32"
TEXT_MAIN = "#f2f2f5"
TEXT_MUTED = "#9a9aa3"
ACCENT = "#ff2d55"         # punk pink/red — headers, selected tab, highlights
ACCENT_HOVER = "#c81d4a"
GREEN = "#2ecc71"
GREEN_HOVER = "#1e9e58"
RED = "#ff3b30"
RED_HOVER = "#c62828"
TERMINAL_GREEN = "#39d353"  # log text — CRT/hacker-terminal touch

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "punkbackup.ico"


def get_local_ip() -> str:
    """Best-effort LAN IP, as a fallback in case <hostname>.local doesn't
    resolve on the iPhone's network. Opens no real connection (UDP, DNS-less)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _volume_text(profile: Profile) -> str:
    vol = profile.current_volume
    if not vol:
        return ""
    label = vol.get("volume_label") or "Sin etiqueta"
    free = format_bytes(vol.get("free_bytes"))
    total = format_bytes(vol.get("total_bytes"))
    return f'"{label}"  ({free} libres de {total})'


def _profile_stats_text(profile: Profile) -> str:
    if not profile.destination_dir:
        return "Sin carpeta destino configurada"

    lines = [f"Carpeta: {profile.destination_dir}"]
    volume = _volume_text(profile)
    if volume:
        lines.append(f"USB: {volume}")

    stats_line = "Última copia: nunca   |   Archivos: 0"
    if app_module.is_configured():
        try:
            st = app_module.get_status_for_profile(profile)
            last = st["last_backup_at"] or "nunca"
            stats_line = f"Última copia: {last}   |   Archivos: {st['total_files_backed_up']}"
        except Exception:
            pass
    return "\n".join([stats_line] + lines)


class ProfileStatusRow(ctk.CTkFrame):
    """Used on the "Principal" screen: name, stats, and the enable/pause switch."""

    def __init__(self, master, profile: Profile, on_toggle):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.profile = profile
        self._on_toggle = on_toggle

        self.name_label = ctk.CTkLabel(self, text=profile.name, font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN)
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.stats_label = ctk.CTkLabel(self, text=_profile_stats_text(profile), text_color=TEXT_MUTED, justify="left")
        self.stats_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        switch_frame = ctk.CTkFrame(self, fg_color="transparent")
        switch_frame.grid(row=0, column=1, rowspan=2, padx=12, pady=8, sticky="e")
        state_text = "Activo" if profile.enabled else "Pausado"
        self.state_label = ctk.CTkLabel(switch_frame, text=state_text, text_color=TEXT_MUTED, width=80)
        self.state_label.pack(side="left", padx=(0, 6))
        self.switch_var = ctk.BooleanVar(value=profile.enabled)
        self.switch = ctk.CTkSwitch(
            switch_frame, text="", variable=self.switch_var, progress_color=ACCENT,
            command=lambda: self._on_toggle(self.profile, self.switch_var.get()),
        )
        self.switch.pack(side="left")

    def update_data(self, profile: Profile) -> None:
        """Refresh in place instead of destroying/recreating — avoids the
        visible flicker a full rebuild causes on every periodic status poll."""
        self.profile = profile
        self.name_label.configure(text=profile.name)
        self.stats_label.configure(text=_profile_stats_text(profile))
        self.state_label.configure(text="Activo" if profile.enabled else "Pausado")
        if self.switch_var.get() != profile.enabled:
            self.switch_var.set(profile.enabled)


class ProfileManageRow(ctk.CTkFrame):
    """Used on the "Perfiles" screen: full CRUD controls."""

    def __init__(self, master, profile: Profile, callbacks: dict):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.profile = profile

        self.name_label = ctk.CTkLabel(self, text=profile.name, font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN)
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        status = "Activo" if profile.enabled else "Pausado"
        self.status_label = ctk.CTkLabel(
            self, text=f"{status}\n{_profile_stats_text(profile)}", text_color=TEXT_MUTED, justify="left"
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, padx=8, pady=6, sticky="e")
        ctk.CTkButton(
            btns, text="Elegir carpeta...", width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: callbacks["choose_dest"](self.profile),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btns, text="Historial USB", width=100, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["history"](self.profile),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btns, text="Copiar token", width=104, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["copy"](self.profile),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btns, text="Renombrar", width=90, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["rename"](self.profile),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btns, text="Renovar token", width=110, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["regenerate"](self.profile),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btns,
            text="Eliminar",
            width=80,
            fg_color=RED,
            hover_color=RED_HOVER,
            command=lambda: callbacks["delete"](self.profile),
        ).pack(side="left", padx=2)

    def update_data(self, profile: Profile) -> None:
        self.profile = profile
        self.name_label.configure(text=profile.name)
        status = "Activo" if profile.enabled else "Pausado"
        self.status_label.configure(text=f"{status}\n{_profile_stats_text(profile)}")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=BG)
        self.title(APP_TITLE)
        if ICON_PATH.exists():
            try:
                self.iconbitmap(str(ICON_PATH))
            except Exception:
                pass  # icon is cosmetic — never let a bad .ico stop the app from opening
        self.geometry("860x700")
        self.minsize(760, 540)

        self.cfg = AppConfig.load()
        self.profile_store = ProfileStore()
        self.controller: ServerController | None = None
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.log_visible = False
        self._principal_rows: dict[str, ProfileStatusRow] = {}
        self._principal_empty_label: ctk.CTkLabel | None = None
        self._perfiles_rows: dict[str, ProfileManageRow] = {}
        self._perfiles_empty_label: ctk.CTkLabel | None = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            header, text="PUNKBACKUP", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header, text=TAGLINE, font=ctk.CTkFont(size=11, slant="italic"), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 4))

        self.tabs = ctk.CTkTabview(
            self, fg_color=BG, segmented_button_fg_color=CARD_BG,
            segmented_button_selected_color=ACCENT, segmented_button_selected_hover_color=ACCENT_HOVER,
            text_color=TEXT_MAIN,
        )
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_principal = self.tabs.add("Principal")
        self.tab_perfiles = self.tabs.add("Perfiles")
        self.tab_principal.configure(fg_color=BG)
        self.tab_perfiles.configure(fg_color=BG)

        self._build_principal_tab()
        self._build_perfiles_tab()
        self._setup_log_handler()
        self._update_connection_info()
        self._refresh_principal_profiles()
        self._refresh_perfiles_tab()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(300, self._drain_log_queue)
        self.after(1500, self._refresh_status_loop)

    # ------------------------------------------------------------------
    # "Principal" tab
    # ------------------------------------------------------------------
    def _build_principal_tab(self) -> None:
        pad = {"padx": 12, "pady": 8}
        parent = self.tab_principal

        ctrl_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        ctrl_frame.pack(fill="x", **pad)
        self.start_btn = ctk.CTkButton(
            ctrl_frame, text="🤘 Iniciar backup", command=self._toggle_server, fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="#08120b", font=ctk.CTkFont(weight="bold"),
        )
        self.start_btn.pack(side="left", padx=10, pady=10)
        self.status_label = ctk.CTkLabel(ctrl_frame, text="Estado: Detenido", text_color=TEXT_MUTED)
        self.status_label.pack(side="left", padx=12)

        info_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        info_frame.pack(fill="x", **pad)
        ctk.CTkLabel(
            info_frame, text="Dirección del servidor (igual para todos los perfiles):",
            font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.address_label = ctk.CTkLabel(info_frame, text="Dirección: -", text_color=TEXT_MUTED)
        self.address_label.pack(anchor="w", padx=10, pady=2)
        self.ip_label = ctk.CTkLabel(info_frame, text="IP alternativa: -", text_color=TEXT_MUTED)
        self.ip_label.pack(anchor="w", padx=10, pady=(2, 10))

        profiles_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        profiles_frame.pack(fill="both", expand=True, **pad)
        ctk.CTkLabel(
            profiles_frame, text="Perfiles conectados a este backup:",
            font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w", padx=10, pady=(8, 4))
        self.principal_profiles_container = ctk.CTkScrollableFrame(profiles_frame, fg_color=BG)
        self.principal_profiles_container.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.principal_profiles_container.grid_columnconfigure(0, weight=1)

        stats_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        stats_frame.pack(fill="x", **pad)
        self.stats_label = ctk.CTkLabel(
            stats_frame, text="Última copia (todos los perfiles): nunca   |   Total archivos: 0", text_color=TEXT_MAIN
        )
        self.stats_label.pack(anchor="w", padx=10, pady=8)

        self.log_toggle_btn = ctk.CTkButton(
            parent, text="▼  Mostrar actividad", command=self._toggle_log, anchor="w",
            fg_color=CARD_BG, hover_color=CARD_BG_ALT, border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        )
        self.log_toggle_btn.pack(fill="x", padx=12, pady=(0, 4))

        self.log_frame = ctk.CTkFrame(parent, fg_color=CARD_BG_ALT, border_width=1, border_color=BORDER)
        # not packed yet — starts hidden
        self.log_box = ctk.CTkTextbox(
            self.log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#050505", text_color=TERMINAL_GREEN,
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # "Perfiles" tab
    # ------------------------------------------------------------------
    def _build_perfiles_tab(self) -> None:
        parent = self.tab_perfiles
        header_row = ctk.CTkFrame(parent, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            header_row, text="Perfiles (personas o dispositivos)", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_MAIN,
        ).pack(side="left")
        ctk.CTkButton(
            header_row, text="+ Agregar perfil", width=140, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._add_profile,
        ).pack(side="right")

        ctk.CTkLabel(
            parent,
            text="Crea un perfil por cada iPhone/iPad. Cada uno tiene su propio token y su propia carpeta —"
            " nunca se mezclan.",
            text_color=TEXT_MUTED, wraplength=760, justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))

        self.perfiles_container = ctk.CTkScrollableFrame(parent, fg_color=BG)
        self.perfiles_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.perfiles_container.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Log setup
    # ------------------------------------------------------------------
    def _setup_log_handler(self) -> None:
        handler = logging.handlers.QueueHandler(self.log_queue)
        handler.setLevel(logging.INFO)
        logging.getLogger("backup_engine").addHandler(handler)
        logging.getLogger("backup_engine").setLevel(logging.INFO)

    # ------------------------------------------------------------------
    # Destination / server control
    # ------------------------------------------------------------------
    def _update_connection_info(self) -> None:
        hostname = socket.gethostname()
        self.address_label.configure(text=f"Dirección: http://{hostname}.local:{self.cfg.port}")
        self.ip_label.configure(text=f"IP alternativa: http://{get_local_ip()}:{self.cfg.port}")

    def _toggle_server(self) -> None:
        try:
            if self.controller and self.controller.running:
                self._stop_server()
            else:
                self._start_server()
        except Exception:
            import traceback

            details = traceback.format_exc()
            self._log_local(f"ERROR al iniciar/detener el servidor:\n{details}")
            messagebox.showerror(
                APP_TITLE, f"Ocurrió un error al iniciar/detener el servidor:\n\n{details}"
            )

    def _start_server(self) -> None:
        profiles = self.profile_store.list()
        if not profiles:
            messagebox.showwarning(
                APP_TITLE, 'Agrega al menos un perfil (pestaña "Perfiles") antes de iniciar.'
            )
            return
        if not any(p.destination_dir for p in profiles):
            messagebox.showwarning(
                APP_TITLE,
                'Ningún perfil tiene carpeta destino configurada. Ve a "Perfiles" y usa '
                '"Elegir carpeta..." en al menos uno.',
            )
            return

        app_module.configure(self.profile_store)
        self.controller = ServerController(app_module.app, host="0.0.0.0", port=self.cfg.port)
        self.controller.start()

        self.start_btn.configure(text="Detener backup", fg_color=RED, hover_color=RED_HOVER, text_color=TEXT_MAIN)
        self.status_label.configure(text=f"Estado: Escuchando en el puerto {self.cfg.port} 🤘", text_color=GREEN)
        self._log_local("Servidor iniciado. A darle.")

    def _stop_server(self) -> None:
        if self.controller:
            self.controller.stop()
        self.start_btn.configure(
            text="🤘 Iniciar backup", fg_color=GREEN, hover_color=GREEN_HOVER, text_color="#08120b"
        )
        self.status_label.configure(text="Estado: Detenido", text_color=TEXT_MUTED)
        self._log_local("Servidor detenido.")

    # ------------------------------------------------------------------
    # Profiles — "Principal" tab (status + enable/pause only)
    # ------------------------------------------------------------------
    def _refresh_principal_profiles(self) -> None:
        profiles = self.profile_store.list()
        current_ids = {p.id for p in profiles}

        for pid in list(self._principal_rows.keys()):
            if pid not in current_ids:
                self._principal_rows.pop(pid).destroy()

        if not profiles:
            for row in self._principal_rows.values():
                row.destroy()
            self._principal_rows.clear()
            if self._principal_empty_label is None or not self._principal_empty_label.winfo_exists():
                self._principal_empty_label = ctk.CTkLabel(
                    self.principal_profiles_container,
                    text='Aún no hay perfiles. Ve a la pestaña "Perfiles" y arranca la banda.',
                    text_color=TEXT_MUTED,
                )
                self._principal_empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        if self._principal_empty_label is not None and self._principal_empty_label.winfo_exists():
            self._principal_empty_label.destroy()
            self._principal_empty_label = None

        for i, profile in enumerate(profiles):
            row = self._principal_rows.get(profile.id)
            if row is None:
                row = ProfileStatusRow(self.principal_profiles_container, profile, self._on_toggle_profile)
                self._principal_rows[profile.id] = row
            else:
                row.update_data(profile)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=4)

    def _on_toggle_profile(self, profile: Profile, enabled: bool) -> None:
        self.profile_store.set_enabled(profile.id, enabled)
        self._log_local(f"Perfil \"{profile.name}\" {'activado' if enabled else 'pausado'}.")
        self._refresh_principal_profiles()
        self._refresh_perfiles_tab()

    # ------------------------------------------------------------------
    # Profiles — "Perfiles" tab (full management)
    # ------------------------------------------------------------------
    def _refresh_perfiles_tab(self) -> None:
        callbacks = {
            "choose_dest": self._choose_profile_destination,
            "history": self._show_destination_history,
            "copy": self._copy_profile_token,
            "rename": self._rename_profile,
            "regenerate": self._regenerate_profile_token,
            "delete": self._delete_profile,
        }

        profiles = self.profile_store.list()
        current_ids = {p.id for p in profiles}

        for pid in list(self._perfiles_rows.keys()):
            if pid not in current_ids:
                self._perfiles_rows.pop(pid).destroy()

        if not profiles:
            for row in self._perfiles_rows.values():
                row.destroy()
            self._perfiles_rows.clear()
            if self._perfiles_empty_label is None or not self._perfiles_empty_label.winfo_exists():
                self._perfiles_empty_label = ctk.CTkLabel(
                    self.perfiles_container,
                    text='Aún no hay perfiles. Usa "+ Agregar perfil" para registrar un iPhone o iPad.',
                    text_color=TEXT_MUTED,
                )
                self._perfiles_empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        if self._perfiles_empty_label is not None and self._perfiles_empty_label.winfo_exists():
            self._perfiles_empty_label.destroy()
            self._perfiles_empty_label = None

        for i, profile in enumerate(profiles):
            row = self._perfiles_rows.get(profile.id)
            if row is None:
                row = ProfileManageRow(self.perfiles_container, profile, callbacks)
                self._perfiles_rows[profile.id] = row
            else:
                row.update_data(profile)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=4)

    def _add_profile(self) -> None:
        dialog = ctk.CTkInputDialog(text='Nombre del perfil (ej. "iPhone de Laura"):', title="Agregar perfil")
        name = dialog.get_input()
        if not name:
            return
        try:
            profile = self.profile_store.add(name)
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.clipboard_clear()
        self.clipboard_append(profile.token)
        messagebox.showinfo(
            APP_TITLE,
            f'Perfil "{profile.name}" creado.\n\nToken (ya copiado al portapapeles):\n{profile.token}\n\n'
            "Pégalo en el Atajo de ese dispositivo siguiendo el manual de configuración del iPhone.\n\n"
            "Ahora elige la carpeta destino de este perfil.",
        )
        self._choose_profile_destination(profile)
        self._refresh_perfiles_tab()
        self._refresh_principal_profiles()

    def _choose_profile_destination(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        chosen = filedialog.askdirectory(
            title=f'Carpeta destino para "{current.name}"',
            initialdir=current.destination_dir or self.cfg.last_destination_dir or None,
        )
        if not chosen:
            return
        self.profile_store.set_destination(profile.id, chosen)
        app_module.forget_profile(profile.id)  # drop any cached engine pointing at the old folder
        self.cfg.last_destination_dir = chosen  # convenience default for the next profile's picker
        self.cfg.save()
        self._refresh_perfiles_tab()
        self._refresh_principal_profiles()

    def _show_destination_history(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        history = list(reversed(current.destination_history))  # most recent first
        if not history:
            messagebox.showinfo(APP_TITLE, f'"{current.name}" todavía no tiene historial de carpetas/USB.')
            return
        lines = []
        for snap in history:
            label = snap.get("volume_label") or "Sin etiqueta"
            free = format_bytes(snap.get("free_bytes"))
            total = format_bytes(snap.get("total_bytes"))
            serial = snap.get("volume_serial") or "?"
            when = snap.get("recorded_at", "")[:19].replace("T", " ")
            marker = " (actual)" if snap.get("path") == current.destination_dir else ""
            lines.append(
                f'{when}{marker}\n  "{label}"  ·  serie {serial}  ·  {free} libres de {total}\n  {snap.get("path")}'
            )
        messagebox.showinfo(APP_TITLE, f'Historial de carpetas/USB para "{current.name}":\n\n' + "\n\n".join(lines))

    def _copy_profile_token(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        self.clipboard_clear()
        self.clipboard_append(current.token)
        messagebox.showinfo(APP_TITLE, f'Token de "{current.name}" copiado al portapapeles.')

    def _rename_profile(self, profile: Profile) -> None:
        dialog = ctk.CTkInputDialog(text=f'Nuevo nombre para "{profile.name}":', title="Renombrar perfil")
        new_name = dialog.get_input()
        if not new_name:
            return
        try:
            self.profile_store.rename(profile.id, new_name)
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self._refresh_perfiles_tab()
        self._refresh_principal_profiles()

    def _regenerate_profile_token(self, profile: Profile) -> None:
        if not messagebox.askyesno(
            APP_TITLE,
            f'¿Renovar el token de "{profile.name}"?\n\nEl Atajo de ese dispositivo dejará de funcionar hasta '
            "que pegues el nuevo token ahí.",
        ):
            return
        new_token = self.profile_store.regenerate_token(profile.id)
        self.clipboard_clear()
        self.clipboard_append(new_token)
        messagebox.showinfo(APP_TITLE, f"Nuevo token (copiado al portapapeles):\n{new_token}")
        self._refresh_perfiles_tab()

    def _delete_profile(self, profile: Profile) -> None:
        if not messagebox.askyesno(
            APP_TITLE,
            f'¿Eliminar el perfil "{profile.name}"?\n\nSus archivos YA respaldados no se borran — solo se '
            "revoca su acceso (su token dejará de funcionar).",
        ):
            return
        self.profile_store.remove(profile.id)
        app_module.forget_profile(profile.id)
        self._refresh_perfiles_tab()
        self._refresh_principal_profiles()

    # ------------------------------------------------------------------
    # Collapsible log
    # ------------------------------------------------------------------
    def _toggle_log(self) -> None:
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            self.log_toggle_btn.configure(text="▲  Ocultar actividad")
        else:
            self.log_frame.pack_forget()
            self.log_toggle_btn.configure(text="▼  Mostrar actividad")

    # ------------------------------------------------------------------
    # Live updates
    # ------------------------------------------------------------------
    def _log_local(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                record = self.log_queue.get_nowait()
            except queue.Empty:
                break
            text = record.getMessage() if isinstance(record, logging.LogRecord) else str(record)
            self.log_box.configure(state="normal")
            self.log_box.insert("end", "> " + text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(300, self._drain_log_queue)

    def _refresh_status_loop(self) -> None:
        if app_module.is_configured():
            try:
                agg = app_module.get_aggregate_status()
                last = agg["last_backup_at"] or "nunca"
                self.stats_label.configure(
                    text=f"Última copia (todos los perfiles): {last}   |   Total archivos: {agg['total_files_backed_up']}"
                )
                self._refresh_principal_profiles()
                self._refresh_perfiles_tab()
            except Exception:
                pass
        self.after(1500, self._refresh_status_loop)

    def report_callback_exception(self, exc, val, tb) -> None:
        """Tkinter calls this for any uncaught exception raised inside a
        widget callback. Overridden so errors are never silently swallowed
        — the app normally runs via pythonw.exe with no console, so without
        this a broken button would just do nothing with zero visible clue."""
        import traceback

        details = "".join(traceback.format_exception(exc, val, tb))
        self._log_local(f"ERROR inesperado:\n{details}")
        messagebox.showerror(APP_TITLE, f"Ocurrió un error inesperado:\n\n{val}")

    def _on_close(self) -> None:
        if self.controller and self.controller.running:
            self.controller.stop()
        self.destroy()


def main() -> None:
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
