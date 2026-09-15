"""Dashboard GUI — PunkBackup dark/industrial theme, live ES/EN switching.

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

Two screens, switched by a custom nav bar (not CTkTabview — we need to
rename the tab labels live when the language changes, and CTkTabview ties
a tab's internal identity to its display text):
  - "Principal": server switch, connection info, live profile status (with
    the enable/pause switch), aggregate stats, collapsible log.
  - "⚙ Configuración" (Settings): language toggle (ES/EN, applied
    instantly, no restart) + full profile management (create/rename/
    regenerate/delete).
"""
from __future__ import annotations

import logging
import logging.handlers
import queue
import socket
from datetime import datetime, timezone
from tkinter import filedialog, messagebox

import customtkinter as ctk

from server import app as app_module
from server.config import AppConfig
from server.diskinfo import format_bytes
from server.paths import app_root
from server.profiles import Profile, ProfileStore
from server.runner import ServerController

from .dialogs import ask_input, ask_yes_no, show_error, show_info, show_warning
from .i18n import LANGUAGES, LANGUAGE_NAMES, t as _t

# PunkBackup: dark, industrial, deliberately rebellious. "Tus recuerdos. Tu
# USB. Cero dependencia de la nube." No cloud, no subscription, no light
# corporate dashboard vibes.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "PunkBackup"  # brand name — stays the same in every language

BG = "#0c0c0e"            # near-black window background
CARD_BG = "#19191d"        # card/panel background
CARD_BG_ALT = "#221418"    # subtle warm-dark variant for the log panel
BORDER = "#2c2c32"
TEXT_MAIN = "#f2f2f5"
TEXT_MUTED = "#9a9aa3"
ACCENT = "#ff2d55"         # punk pink/red — headers, selected nav, highlights
ACCENT_HOVER = "#c81d4a"
ACCENT_INK = "#1a0308"      # text color used ON TOP of the accent color
GREEN = "#2ecc71"
GREEN_HOVER = "#1e9e58"
RED = "#ff3b30"
RED_HOVER = "#c62828"
TERMINAL_GREEN = "#39d353"  # log text — CRT/hacker-terminal touch

ICON_PATH = app_root() / "assets" / "punkbackup.ico"


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


def _format_local(iso_utc: str | None) -> str | None:
    """Every timestamp the server hands the GUI (last_backup_at, a
    destination-history snapshot's recorded_at, ...) is stored in UTC —
    see manifest_db.py's _now(). The GUI is the only layer that should
    ever convert it: show the user their own device's local time, never
    change what's actually stored. Returns None (so callers can fall back
    to their own "never"/empty text) if there's nothing to format."""
    if not iso_utc:
        return None
    try:
        dt = datetime.fromisoformat(iso_utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_utc  # unexpected format — show it raw rather than crash


def _volume_text(profile: Profile, lang: str) -> str:
    vol = profile.current_volume
    if not vol:
        return ""
    label = vol.get("volume_label") or _t("no_label", lang)
    free = format_bytes(vol.get("free_bytes"))
    total = format_bytes(vol.get("total_bytes"))
    return _t("free_of_total", lang, label=label, free=free, total=total)


def _profile_stats_text(profile: Profile, lang: str) -> str:
    if not profile.destination_dir:
        return _t("stats_no_dest", lang)

    lines = [_t("stats_folder", lang, path=profile.destination_dir)]
    volume = _volume_text(profile, lang)
    if volume:
        lines.append(_t("stats_usb", lang, info=volume))

    stats_line = _t("stats_line", lang, last=_t("never", lang), count=0)
    if app_module.is_configured():
        try:
            st = app_module.get_status_for_profile(profile)
            last = _format_local(st["last_backup_at"]) or _t("never", lang)
            stats_line = _t("stats_line", lang, last=last, count=st["total_files_backed_up"])
        except Exception:
            pass
    return "\n".join([stats_line] + lines)


class ProfileStatusRow(ctk.CTkFrame):
    """Used on the "Principal" screen: name, stats, and the enable/pause switch."""

    def __init__(self, master, profile: Profile, lang: str, on_toggle):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.profile = profile
        self.lang = lang
        self._on_toggle = on_toggle

        self.name_label = ctk.CTkLabel(self, text=profile.name, font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN)
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.stats_label = ctk.CTkLabel(
            self, text=_profile_stats_text(profile, lang), text_color=TEXT_MUTED, justify="left"
        )
        self.stats_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        switch_frame = ctk.CTkFrame(self, fg_color="transparent")
        switch_frame.grid(row=0, column=1, rowspan=2, padx=12, pady=8, sticky="e")
        self.state_label = ctk.CTkLabel(
            switch_frame, text=self._state_text(), text_color=TEXT_MUTED, width=80
        )
        self.state_label.pack(side="left", padx=(0, 6))
        self.switch_var = ctk.BooleanVar(value=profile.enabled)
        self.switch = ctk.CTkSwitch(
            switch_frame, text="", variable=self.switch_var, progress_color=ACCENT,
            command=lambda: self._on_toggle(self.profile, self.switch_var.get()),
        )
        self.switch.pack(side="left")

    def _state_text(self) -> str:
        return _t("profile_active", self.lang) if self.profile.enabled else _t("profile_paused", self.lang)

    def update_data(self, profile: Profile, lang: str) -> None:
        """Refresh in place instead of destroying/recreating — avoids the
        visible flicker a full rebuild causes on every periodic status poll."""
        self.profile = profile
        self.lang = lang
        self.name_label.configure(text=profile.name)
        self.stats_label.configure(text=_profile_stats_text(profile, lang))
        self.state_label.configure(text=self._state_text())
        if self.switch_var.get() != profile.enabled:
            self.switch_var.set(profile.enabled)


class ProfileManageRow(ctk.CTkFrame):
    """Used on the "⚙ Configuración" screen: full CRUD controls."""

    def __init__(self, master, profile: Profile, lang: str, callbacks: dict):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.profile = profile
        self.lang = lang

        self.name_label = ctk.CTkLabel(self, text=profile.name, font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN)
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.status_label = ctk.CTkLabel(self, text=self._status_text(), text_color=TEXT_MUTED, justify="left")
        self.status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, padx=8, pady=6, sticky="e")
        self.btn_choose_dest = ctk.CTkButton(
            btns, width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: callbacks["choose_dest"](self.profile),
        )
        self.btn_choose_dest.pack(side="left", padx=2)
        self.btn_history = ctk.CTkButton(
            btns, width=100, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["history"](self.profile),
        )
        self.btn_history.pack(side="left", padx=2)
        self.btn_copy = ctk.CTkButton(
            btns, width=104, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["copy"](self.profile),
        )
        self.btn_copy.pack(side="left", padx=2)
        self.btn_rename = ctk.CTkButton(
            btns, width=90, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["rename"](self.profile),
        )
        self.btn_rename.pack(side="left", padx=2)
        self.btn_regenerate = ctk.CTkButton(
            btns, width=110, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["regenerate"](self.profile),
        )
        self.btn_regenerate.pack(side="left", padx=2)
        self.btn_delete = ctk.CTkButton(
            btns, width=80, fg_color=RED, hover_color=RED_HOVER,
            command=lambda: callbacks["delete"](self.profile),
        )
        self.btn_delete.pack(side="left", padx=2)

        self._apply_button_text()

    def _status_text(self) -> str:
        status = _t("profile_active", self.lang) if self.profile.enabled else _t("profile_paused", self.lang)
        return f"{status}\n{_profile_stats_text(self.profile, self.lang)}"

    def _apply_button_text(self) -> None:
        self.btn_choose_dest.configure(text=_t("btn_choose_folder", self.lang))
        self.btn_history.configure(text=_t("btn_usb_history", self.lang))
        self.btn_copy.configure(text=_t("btn_copy_token", self.lang))
        self.btn_rename.configure(text=_t("btn_rename", self.lang))
        self.btn_regenerate.configure(text=_t("btn_regenerate_token", self.lang))
        self.btn_delete.configure(text=_t("btn_delete", self.lang))

    def update_data(self, profile: Profile, lang: str) -> None:
        lang_changed = lang != self.lang
        self.profile = profile
        self.lang = lang
        self.name_label.configure(text=profile.name)
        self.status_label.configure(text=self._status_text())
        if lang_changed:
            self._apply_button_text()


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = AppConfig.load()
        self.lang = self.cfg.language if self.cfg.language in LANGUAGES else "es"

        self.configure(fg_color=BG)
        self.title(APP_TITLE)
        if ICON_PATH.exists():
            try:
                self.iconbitmap(str(ICON_PATH))
            except Exception:
                pass  # icon is cosmetic — never let a bad .ico stop the app from opening
        self.geometry("860x720")
        self.minsize(760, 540)

        self.profile_store = ProfileStore()
        self.controller: ServerController | None = None
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.log_visible = False
        self._extra_log_widgets: list[ctk.CTkTextbox] = []  # expanded-log popups also live-fed
        self._log_popup: ctk.CTkToplevel | None = None  # only one expanded window at a time
        self.current_screen = "main"
        self._principal_rows: dict[str, ProfileStatusRow] = {}
        self._principal_empty_label: ctk.CTkLabel | None = None
        self._settings_rows: dict[str, ProfileManageRow] = {}
        self._settings_empty_label: ctk.CTkLabel | None = None

        self._build_header()
        self._build_nav()

        self.content_area = ctk.CTkFrame(self, fg_color=BG)
        self.content_area.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tab_principal = ctk.CTkFrame(self.content_area, fg_color=BG)
        self.tab_settings = ctk.CTkFrame(self.content_area, fg_color=BG)

        self._build_principal_tab()
        self._build_settings_tab()
        self._show_screen("main")

        self._setup_log_handler()
        self._update_connection_info()
        self._refresh_principal_profiles()
        self._refresh_settings_profiles()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(300, self._drain_log_queue)
        self.after(1500, self._refresh_status_loop)

    def t(self, key: str, **kwargs) -> str:
        return _t(key, self.lang, **kwargs)

    # ------------------------------------------------------------------
    # Header / nav
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            header, text="PUNKBACKUP", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT,
        ).pack(anchor="w")
        self.tagline_label = ctk.CTkLabel(
            header, text=self.t("tagline"), font=ctk.CTkFont(size=11, slant="italic"), text_color=TEXT_MUTED,
        )
        self.tagline_label.pack(anchor="w", pady=(0, 4))

    def _build_nav(self) -> None:
        nav = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10)
        nav.pack(padx=16, pady=(8, 4), anchor="w")
        self.nav_main_btn = ctk.CTkButton(
            nav, text=self.t("nav_main"), corner_radius=8, command=lambda: self._show_screen("main"),
        )
        self.nav_main_btn.pack(side="left", padx=4, pady=4)
        self.nav_settings_btn = ctk.CTkButton(
            nav, text=self.t("nav_settings"), corner_radius=8, command=lambda: self._show_screen("settings"),
        )
        self.nav_settings_btn.pack(side="left", padx=4, pady=4)

    def _show_screen(self, screen: str) -> None:
        self.current_screen = screen
        self.tab_principal.pack_forget()
        self.tab_settings.pack_forget()
        if screen == "main":
            self.tab_principal.pack(fill="both", expand=True)
            self.nav_main_btn.configure(fg_color=ACCENT, text_color=ACCENT_INK, hover_color=ACCENT_HOVER)
            self.nav_settings_btn.configure(fg_color="transparent", text_color=TEXT_MAIN, hover_color=CARD_BG_ALT)
        else:
            self.tab_settings.pack(fill="both", expand=True)
            self.nav_settings_btn.configure(fg_color=ACCENT, text_color=ACCENT_INK, hover_color=ACCENT_HOVER)
            self.nav_main_btn.configure(fg_color="transparent", text_color=TEXT_MAIN, hover_color=CARD_BG_ALT)

    # ------------------------------------------------------------------
    # "Principal" screen
    # ------------------------------------------------------------------
    def _build_principal_tab(self) -> None:
        pad = {"padx": 12, "pady": 8}
        parent = self.tab_principal

        ctrl_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        ctrl_frame.pack(fill="x", **pad)
        self.start_btn = ctk.CTkButton(
            ctrl_frame, text=self.t("btn_start"), command=self._toggle_server, fg_color=GREEN,
            hover_color=GREEN_HOVER, text_color="#08120b", font=ctk.CTkFont(weight="bold"),
        )
        self.start_btn.pack(side="left", padx=10, pady=10)
        self.status_label = ctk.CTkLabel(ctrl_frame, text=self.t("status_stopped"), text_color=TEXT_MUTED)
        self.status_label.pack(side="left", padx=12)

        info_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        info_frame.pack(fill="x", **pad)
        self.server_address_title_label = ctk.CTkLabel(
            info_frame, text=self.t("server_address_title"), font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
        )
        self.server_address_title_label.pack(anchor="w", padx=10, pady=(8, 0))
        self.address_label = ctk.CTkLabel(info_frame, text=self.t("address_placeholder"), text_color=TEXT_MUTED)
        self.address_label.pack(anchor="w", padx=10, pady=2)
        self.ip_label = ctk.CTkLabel(info_frame, text=self.t("ip_placeholder"), text_color=TEXT_MUTED)
        self.ip_label.pack(anchor="w", padx=10, pady=(2, 10))

        profiles_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        profiles_frame.pack(fill="both", expand=True, **pad)
        self.profiles_connected_title_label = ctk.CTkLabel(
            profiles_frame, text=self.t("profiles_connected_title"),
            font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
        )
        self.profiles_connected_title_label.pack(anchor="w", padx=10, pady=(8, 4))
        self.principal_profiles_container = ctk.CTkScrollableFrame(profiles_frame, fg_color=BG)
        self.principal_profiles_container.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.principal_profiles_container.grid_columnconfigure(0, weight=1)

        stats_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        stats_frame.pack(fill="x", **pad)
        self.stats_label = ctk.CTkLabel(
            stats_frame, text=self.t("aggregate_stats", last=self.t("never"), total=0), text_color=TEXT_MAIN
        )
        self.stats_label.pack(anchor="w", padx=10, pady=8)

        log_btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        log_btn_row.pack(fill="x", padx=12, pady=(0, 4))
        log_btn_row.grid_columnconfigure(0, weight=1)

        self.log_toggle_btn = ctk.CTkButton(
            log_btn_row, text=self.t("show_activity"), command=self._toggle_log, anchor="w",
            fg_color=CARD_BG, hover_color=CARD_BG_ALT, border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        )
        self.log_toggle_btn.grid(row=0, column=0, sticky="ew")

        self.log_expand_btn = ctk.CTkButton(
            log_btn_row, text=self.t("expand_activity"), command=self._open_log_popup, width=110,
            fg_color=CARD_BG, hover_color=CARD_BG_ALT, border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        )
        self.log_expand_btn.grid(row=0, column=1, padx=(8, 0))

        self.log_frame = ctk.CTkFrame(parent, fg_color=CARD_BG_ALT, border_width=1, border_color=BORDER)
        # not packed yet — starts hidden
        self.log_box = ctk.CTkTextbox(
            self.log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#050505", text_color=TERMINAL_GREEN,
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # "⚙ Configuración" (Settings) screen — language + profile management
    # ------------------------------------------------------------------
    def _build_settings_tab(self) -> None:
        parent = self.tab_settings

        lang_frame = ctk.CTkFrame(parent, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        lang_frame.pack(fill="x", padx=12, pady=(12, 8))
        self.language_title_label = ctk.CTkLabel(
            lang_frame, text=self.t("language_title"), font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
        )
        self.language_title_label.pack(anchor="w", padx=10, pady=(10, 4))
        lang_btns = ctk.CTkFrame(lang_frame, fg_color="transparent")
        lang_btns.pack(anchor="w", padx=10, pady=(0, 10))
        self.lang_buttons: dict[str, ctk.CTkButton] = {}
        for code in LANGUAGES:
            btn = ctk.CTkButton(
                lang_btns, text=LANGUAGE_NAMES[code], width=110, command=lambda c=code: self._set_language(c)
            )
            btn.pack(side="left", padx=(0, 8))
            self.lang_buttons[code] = btn
        self._refresh_language_buttons()

        header_row = ctk.CTkFrame(parent, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))
        self.profiles_title_label = ctk.CTkLabel(
            header_row, text=self.t("profiles_title"), font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_MAIN,
        )
        self.profiles_title_label.pack(side="left")
        self.add_profile_btn = ctk.CTkButton(
            header_row, text=self.t("add_profile"), width=140, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._add_profile,
        )
        self.add_profile_btn.pack(side="right")

        self.profiles_hint_label = ctk.CTkLabel(
            parent, text=self.t("profiles_hint"), text_color=TEXT_MUTED, wraplength=760, justify="left",
        )
        self.profiles_hint_label.pack(fill="x", padx=12, pady=(0, 8))

        self.perfiles_container = ctk.CTkScrollableFrame(parent, fg_color=BG)
        self.perfiles_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.perfiles_container.grid_columnconfigure(0, weight=1)

    def _refresh_language_buttons(self) -> None:
        for code, btn in self.lang_buttons.items():
            if code == self.lang:
                btn.configure(fg_color=ACCENT, text_color=ACCENT_INK, hover_color=ACCENT_HOVER, border_width=0)
            else:
                btn.configure(
                    fg_color="transparent", text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
                    border_width=1, border_color=BORDER,
                )

    def _set_language(self, code: str) -> None:
        if code == self.lang or code not in LANGUAGES:
            return
        self.lang = code
        self.cfg.language = code
        self.cfg.save()
        self._apply_language()

    def _apply_language(self) -> None:
        """Re-applies every translatable widget's text in place — no restart."""
        self.tagline_label.configure(text=self.t("tagline"))
        self.nav_main_btn.configure(text=self.t("nav_main"))
        self.nav_settings_btn.configure(text=self.t("nav_settings"))

        running = bool(self.controller and self.controller.running)
        self.start_btn.configure(text=self.t("btn_stop") if running else self.t("btn_start"))
        self.status_label.configure(
            text=self.t("status_listening", port=self.cfg.port) if running else self.t("status_stopped")
        )

        self.server_address_title_label.configure(text=self.t("server_address_title"))
        self._update_connection_info()
        self.profiles_connected_title_label.configure(text=self.t("profiles_connected_title"))

        self.log_toggle_btn.configure(text=self.t("hide_activity") if self.log_visible else self.t("show_activity"))
        self.log_expand_btn.configure(text=self.t("expand_activity"))

        self.language_title_label.configure(text=self.t("language_title"))
        self._refresh_language_buttons()
        self.profiles_title_label.configure(text=self.t("profiles_title"))
        self.add_profile_btn.configure(text=self.t("add_profile"))
        self.profiles_hint_label.configure(text=self.t("profiles_hint"))

        self._refresh_aggregate_stats()
        self._refresh_principal_profiles()
        self._refresh_settings_profiles()
        self._show_screen(self.current_screen)  # re-apply selected/unselected nav styling

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
        self.address_label.configure(
            text=self.t("address_value", url=f"http://{hostname}.local:{self.cfg.port}")
        )
        self.ip_label.configure(
            text=self.t("ip_value", url=f"http://{get_local_ip()}:{self.cfg.port}")
        )

    def _toggle_server(self) -> None:
        try:
            if self.controller and self.controller.running:
                self._stop_server()
            else:
                self._start_server()
        except Exception:
            import traceback

            details = traceback.format_exc()
            self._log_local(f"ERROR:\n{details}")
            show_error(self, self.lang, self.t("dlg_title_error"), self.t("err_toggle_server", details=details))

    def _start_server(self) -> None:
        profiles = self.profile_store.list()
        if not profiles:
            show_warning(self, self.lang, self.t("dlg_title_warning"), self.t("warn_no_profiles"))
            return
        if not any(p.destination_dir for p in profiles):
            show_warning(self, self.lang, self.t("dlg_title_warning"), self.t("warn_no_destination"))
            return

        app_module.configure(self.profile_store)
        self.controller = ServerController(app_module.app, host="0.0.0.0", port=self.cfg.port)
        self.controller.start()

        self.start_btn.configure(text=self.t("btn_stop"), fg_color=RED, hover_color=RED_HOVER, text_color=TEXT_MAIN)
        self.status_label.configure(text=self.t("status_listening", port=self.cfg.port), text_color=GREEN)
        self._log_local(self.t("log_server_started"))

    def _stop_server(self) -> None:
        if self.controller:
            self.controller.stop()
        self.start_btn.configure(
            text=self.t("btn_start"), fg_color=GREEN, hover_color=GREEN_HOVER, text_color="#08120b"
        )
        self.status_label.configure(text=self.t("status_stopped"), text_color=TEXT_MUTED)
        self._log_local(self.t("log_server_stopped"))

    # ------------------------------------------------------------------
    # Profiles — "Principal" screen (status + enable/pause only)
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
                    self.principal_profiles_container, text=self.t("empty_profiles_main"), text_color=TEXT_MUTED,
                )
                self._principal_empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            else:
                self._principal_empty_label.configure(text=self.t("empty_profiles_main"))
            return

        if self._principal_empty_label is not None and self._principal_empty_label.winfo_exists():
            self._principal_empty_label.destroy()
            self._principal_empty_label = None

        for i, profile in enumerate(profiles):
            row = self._principal_rows.get(profile.id)
            if row is None:
                row = ProfileStatusRow(self.principal_profiles_container, profile, self.lang, self._on_toggle_profile)
                self._principal_rows[profile.id] = row
            else:
                row.update_data(profile, self.lang)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=4)

    def _on_toggle_profile(self, profile: Profile, enabled: bool) -> None:
        self.profile_store.set_enabled(profile.id, enabled)
        key = "log_profile_activated" if enabled else "log_profile_paused"
        self._log_local(self.t(key, name=profile.name))
        self._refresh_principal_profiles()
        self._refresh_settings_profiles()

    # ------------------------------------------------------------------
    # Profiles — "⚙ Configuración" screen (full management)
    # ------------------------------------------------------------------
    def _refresh_settings_profiles(self) -> None:
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

        for pid in list(self._settings_rows.keys()):
            if pid not in current_ids:
                self._settings_rows.pop(pid).destroy()

        if not profiles:
            for row in self._settings_rows.values():
                row.destroy()
            self._settings_rows.clear()
            if self._settings_empty_label is None or not self._settings_empty_label.winfo_exists():
                self._settings_empty_label = ctk.CTkLabel(
                    self.perfiles_container, text=self.t("empty_profiles_settings"), text_color=TEXT_MUTED,
                )
                self._settings_empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            else:
                self._settings_empty_label.configure(text=self.t("empty_profiles_settings"))
            return

        if self._settings_empty_label is not None and self._settings_empty_label.winfo_exists():
            self._settings_empty_label.destroy()
            self._settings_empty_label = None

        for i, profile in enumerate(profiles):
            row = self._settings_rows.get(profile.id)
            if row is None:
                row = ProfileManageRow(self.perfiles_container, profile, self.lang, callbacks)
                self._settings_rows[profile.id] = row
            else:
                row.update_data(profile, self.lang)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=4)

    def _add_profile(self) -> None:
        name = ask_input(self, self.lang, self.t("dlg_add_profile_title"), self.t("dlg_add_profile_text"))
        if not name:
            return
        try:
            profile = self.profile_store.add(name)
        except ValueError as exc:
            show_error(self, self.lang, self.t("dlg_title_error"), str(exc))
            return
        self.clipboard_clear()
        self.clipboard_append(profile.token)
        show_info(
            self, self.lang, self.t("dlg_title_profile_created"),
            self.t("msg_profile_created", name=profile.name, token=profile.token), copy_value=profile.token,
        )
        self._choose_profile_destination(profile)
        self._refresh_settings_profiles()
        self._refresh_principal_profiles()

    def _choose_profile_destination(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        chosen = filedialog.askdirectory(
            title=self.t("dlg_choose_dest_title", name=current.name),
            initialdir=current.destination_dir or self.cfg.last_destination_dir or None,
        )
        if not chosen:
            return
        self.profile_store.set_destination(profile.id, chosen)
        app_module.forget_profile(profile.id)  # drop any cached engine pointing at the old folder
        self.cfg.last_destination_dir = chosen  # convenience default for the next profile's picker
        self.cfg.save()
        self._refresh_settings_profiles()
        self._refresh_principal_profiles()

    def _show_destination_history(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        history = list(reversed(current.destination_history))  # most recent first
        if not history:
            show_info(self, self.lang, self.t("dlg_title_history"), self.t("msg_no_history", name=current.name))
            return
        lines = []
        for snap in history:
            label = snap.get("volume_label") or self.t("no_label")
            free = format_bytes(snap.get("free_bytes"))
            total = format_bytes(snap.get("total_bytes"))
            serial = snap.get("volume_serial") or "?"
            when = _format_local(snap.get("recorded_at")) or ""
            marker = self.t("history_current") if snap.get("path") == current.destination_dir else ""
            lines.append(
                f'{when}{marker}\n  "{label}"  ·  {self.t("history_serial", serial=serial)}  ·  '
                f'{free} / {total}\n  {snap.get("path")}'
            )
        show_info(
            self, self.lang, self.t("dlg_title_history"),
            self.t("history_title", name=current.name, lines="\n\n".join(lines)),
        )

    def _copy_profile_token(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        self.clipboard_clear()
        self.clipboard_append(current.token)
        show_info(
            self, self.lang, self.t("dlg_title_token_copied"),
            self.t("msg_token_copied", name=current.name), copy_value=current.token,
        )

    def _rename_profile(self, profile: Profile) -> None:
        new_name = ask_input(
            self, self.lang, self.t("dlg_rename_title"), self.t("dlg_rename_text", name=profile.name)
        )
        if not new_name:
            return
        try:
            self.profile_store.rename(profile.id, new_name)
        except ValueError as exc:
            show_error(self, self.lang, self.t("dlg_title_error"), str(exc))
            return
        self._refresh_settings_profiles()
        self._refresh_principal_profiles()

    def _regenerate_profile_token(self, profile: Profile) -> None:
        if not ask_yes_no(self, self.lang, self.t("dlg_title_confirm"), self.t("confirm_regenerate", name=profile.name)):
            return
        new_token = self.profile_store.regenerate_token(profile.id)
        self.clipboard_clear()
        self.clipboard_append(new_token)
        show_info(
            self, self.lang, self.t("dlg_title_new_token"), self.t("msg_new_token", token=new_token),
            copy_value=new_token,
        )
        self._refresh_settings_profiles()

    def _delete_profile(self, profile: Profile) -> None:
        if not ask_yes_no(
            self, self.lang, self.t("dlg_title_confirm"), self.t("confirm_delete", name=profile.name), danger=True
        ):
            return
        self.profile_store.remove(profile.id)
        app_module.forget_profile(profile.id)
        self._refresh_settings_profiles()
        self._refresh_principal_profiles()

    # ------------------------------------------------------------------
    # Collapsible log
    # ------------------------------------------------------------------
    def _toggle_log(self) -> None:
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            self.log_toggle_btn.configure(text=self.t("hide_activity"))
        else:
            self.log_frame.pack_forget()
            self.log_toggle_btn.configure(text=self.t("show_activity"))

    def _open_log_popup(self) -> None:
        """A separate, resizable/maximizable window mirroring the same
        live log — for when the small embedded panel isn't enough to read
        a long run's activity. Fed by the same _drain_log_queue loop as
        the main log box, so both stay in sync while both are open."""
        if self._log_popup is not None and self._log_popup.winfo_exists():
            self._log_popup.lift()
            self._log_popup.attributes("-topmost", True)
            self._log_popup.focus_force()
            self._log_popup.after(150, lambda: self._log_popup.attributes("-topmost", False))
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"{APP_TITLE} — {self.t('expand_activity')}")
        popup.geometry("900x600")
        popup.configure(fg_color=BG)
        try:
            popup.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

        # New Toplevels can otherwise open BEHIND the main window on
        # Windows — force it to the front once it's actually mapped, then
        # drop the "always on top" flag so it behaves like a normal window
        # afterward (just raised once, not pinned above everything).
        def _bring_to_front() -> None:
            popup.lift()
            popup.attributes("-topmost", True)
            popup.focus_force()
            popup.after(150, lambda: popup.attributes("-topmost", False))

        popup.after(50, _bring_to_front)

        box = ctk.CTkTextbox(
            popup, wrap="word", font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#050505", text_color=TERMINAL_GREEN,
        )
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.configure(state="normal")
        box.insert("end", self.log_box.get("1.0", "end-1c"))  # seed with what's already there
        box.see("end")
        box.configure(state="disabled")

        self._extra_log_widgets.append(box)

        def _on_close() -> None:
            if box in self._extra_log_widgets:
                self._extra_log_widgets.remove(box)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _on_close)
        self._log_popup = popup

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
            for widget in list(self._extra_log_widgets):
                if not widget.winfo_exists():
                    self._extra_log_widgets.remove(widget)
                    continue
                widget.configure(state="normal")
                widget.insert("end", "> " + text + "\n")
                widget.see("end")
                widget.configure(state="disabled")
        self.after(300, self._drain_log_queue)

    def _refresh_aggregate_stats(self) -> None:
        if app_module.is_configured():
            try:
                agg = app_module.get_aggregate_status()
                last = _format_local(agg["last_backup_at"]) or self.t("never")
                self.stats_label.configure(text=self.t("aggregate_stats", last=last, total=agg["total_files_backed_up"]))
            except Exception:
                pass
        else:
            self.stats_label.configure(text=self.t("aggregate_stats", last=self.t("never"), total=0))

    def _refresh_status_loop(self) -> None:
        if app_module.is_configured():
            try:
                self._refresh_aggregate_stats()
                self._refresh_principal_profiles()
                self._refresh_settings_profiles()
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
        self._log_local(f"ERROR:\n{details}")
        message = self.t("err_unexpected", val=val)
        try:
            show_error(self, self.lang, self.t("dlg_title_error"), message)
        except Exception:
            # Last-resort fallback: if the custom dialog itself errors while
            # we're already handling an uncaught exception, fall back to the
            # plain native messagebox rather than risk masking the error.
            messagebox.showerror(APP_TITLE, message)

    def _on_close(self) -> None:
        if self.controller and self.controller.running:
            self.controller.stop()
        self.destroy()


def main() -> None:
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
