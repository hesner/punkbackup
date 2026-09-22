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
import shutil
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from server import app as app_module
from server.config import AppConfig
from server.diskinfo import format_bytes
from server.manifest_db import ManifestDB
from server.mirror import MirrorSyncResult, get_mirror_status, sync_mirror
from server.paths import app_root, user_data_dir
from server.profiles import Profile, ProfileStore
from server.runner import ServerController

from .autostart import set_start_with_windows
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
    last_run_line = None
    if app_module.is_configured():
        try:
            st = app_module.get_status_for_profile(profile)
            last = _format_local(st["last_backup_at"]) or _t("never", lang)
            stats_line = _t("stats_line", lang, last=last, count=st["total_files_backed_up"])
            last_run = st.get("last_run")
            if last_run:
                running = _t("stats_last_run_in_progress", lang) if last_run.get("finished_at") is None else ""
                last_run_line = _t(
                    "stats_last_run",
                    lang,
                    new=last_run.get("files_new", 0),
                    skipped=last_run.get("files_skipped", 0),
                    running=running,
                )
        except Exception:
            pass
    result_lines = [stats_line]
    if last_run_line:
        result_lines.append(last_run_line)
    return "\n".join(result_lines + lines)


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
    """Used on the "⚙ Configuración" screen: full CRUD controls, plus the
    optional second-copy (mirror) sub-section below them — see PLAN.md
    section 13. That sub-section stays a single discreet link when no
    mirror is configured, so it adds no noise for anyone not using it."""

    def __init__(self, master, profile: Profile, lang: str, callbacks: dict):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.profile = profile
        self.lang = lang
        self._syncing = False

        self.name_label = ctk.CTkLabel(self, text=profile.name, font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN)
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.status_label = ctk.CTkLabel(self, text=self._status_text(), text_color=TEXT_MUTED, justify="left")
        self.status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, padx=8, pady=6, sticky="e")
        self.btn_choose_dest = ctk.CTkButton(
            btns, width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_INK,
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
            btns, width=80, fg_color=RED, hover_color=RED_HOVER, text_color=TEXT_MAIN,
            command=lambda: callbacks["delete"](self.profile),
        )
        self.btn_delete.pack(side="left", padx=2)

        # -- Second copy (mirror) sub-section — two alternate layouts that
        # get shown/hidden via grid()/grid_remove(), never both at once.
        self.mirror_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.mirror_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.mirror_frame.grid_columnconfigure(0, weight=1)

        self.btn_configure_mirror = ctk.CTkButton(
            self.mirror_frame, fg_color="transparent", hover_color=CARD_BG_ALT,
            text_color=TEXT_MUTED, anchor="w", border_width=0,
            command=lambda: callbacks["choose_mirror"](self.profile),
        )

        self.mirror_configured_frame = ctk.CTkFrame(self.mirror_frame, fg_color="transparent")
        self.mirror_configured_frame.grid_columnconfigure(0, weight=1)
        self.mirror_status_label = ctk.CTkLabel(
            self.mirror_configured_frame, text="", text_color=TEXT_MUTED, justify="left"
        )
        self.mirror_status_label.grid(row=0, column=0, sticky="w", padx=4)
        mirror_btns = ctk.CTkFrame(self.mirror_configured_frame, fg_color="transparent")
        mirror_btns.grid(row=0, column=1, sticky="e", padx=4)
        self.btn_sync_mirror = ctk.CTkButton(
            mirror_btns, width=140, fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_INK,
            command=lambda: callbacks["sync_mirror"](self.profile),
        )
        self.btn_sync_mirror.pack(side="left", padx=2)
        self.btn_remove_mirror = ctk.CTkButton(
            mirror_btns, width=80, fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=TEXT_MAIN, hover_color=CARD_BG_ALT,
            command=lambda: callbacks["remove_mirror"](self.profile),
        )
        self.btn_remove_mirror.pack(side="left", padx=2)

        self._apply_button_text()
        self._refresh_mirror_section()

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
        self.btn_configure_mirror.configure(text=_t("btn_configure_mirror", self.lang))
        # While syncing, the button shows "Detener" instead -- don't stomp
        # that on a language switch mid-sync.
        sync_key = "btn_stop_mirror_sync" if self._syncing else "btn_sync_mirror"
        self.btn_sync_mirror.configure(text=_t(sync_key, self.lang))
        self.btn_remove_mirror.configure(text=_t("btn_remove_mirror", self.lang))

    def _refresh_mirror_section(self) -> None:
        if not self.profile.mirror_dir:
            self.mirror_configured_frame.grid_remove()
            self.btn_configure_mirror.grid(row=0, column=0, sticky="w")
            return
        self.btn_configure_mirror.grid_remove()
        self.mirror_configured_frame.grid(row=0, column=0, sticky="ew")

        if self._syncing:
            return  # set_sync_progress()/set_syncing() own the label/button while active

        status = get_mirror_status(self.profile.mirror_dir)
        if status is None:
            self.mirror_status_label.configure(text=_t("mirror_not_connected", self.lang, path=self.profile.mirror_dir))
            self.btn_sync_mirror.configure(state="disabled")
        else:
            if status.get("free_bytes") is not None and status.get("total_bytes") is not None:
                text = _t(
                    "mirror_status", self.lang, path=self.profile.mirror_dir, total=status["total_files"],
                    free=format_bytes(status["free_bytes"]), total_space=format_bytes(status["total_bytes"]),
                )
            else:
                text = _t(
                    "mirror_status_no_space_info", self.lang, path=self.profile.mirror_dir, total=status["total_files"],
                )
            self.mirror_status_label.configure(text=text)
            self.btn_sync_mirror.configure(state="normal")

    def set_syncing(self, syncing: bool, lang: str) -> None:
        """The sync button stays enabled while syncing (unlike other
        buttons) -- it toggles into a "Detener" stop button instead, same
        pattern as the main "Iniciar/Detener backup" button, so the user
        can cancel to e.g. safely eject the drive."""
        self._syncing = syncing
        self.lang = lang
        if syncing:
            self.btn_sync_mirror.configure(
                text=_t("btn_stop_mirror_sync", lang), fg_color=RED, hover_color=RED_HOVER, text_color=TEXT_MAIN,
            )
        else:
            self.btn_sync_mirror.configure(
                text=_t("btn_sync_mirror", lang), fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_INK,
            )
        self.btn_remove_mirror.configure(state="disabled" if syncing else "normal")
        if not syncing:
            self._refresh_mirror_section()

    def set_sync_progress(
        self, done: int, total: int, lang: str, free_bytes: int | None = None, total_bytes: int | None = None,
    ) -> None:
        self.lang = lang
        if free_bytes is not None and total_bytes is not None:
            text = _t(
                "mirror_syncing_progress", lang, done=done, total=total,
                free=format_bytes(free_bytes), total_space=format_bytes(total_bytes),
            )
        else:
            text = _t("mirror_syncing_progress_no_space", lang, done=done, total=total)
        self.mirror_status_label.configure(text=text)

    def update_data(self, profile: Profile, lang: str) -> None:
        lang_changed = lang != self.lang
        self.profile = profile
        self.lang = lang
        self.name_label.configure(text=profile.name)
        self.status_label.configure(text=self._status_text())
        if lang_changed:
            self._apply_button_text()
        self._refresh_mirror_section()


class SettingSwitchRow(ctk.CTkFrame):
    """Used on the "⚙ Configuración" screen for a single global on/off
    setting — same card + switch visual language as ProfileStatusRow."""

    def __init__(self, master, label_key: str, lang: str, initial: bool, on_toggle):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.label_key = label_key
        self.lang = lang
        self._on_toggle = on_toggle

        self.name_label = ctk.CTkLabel(
            self, text=_t(label_key, lang), font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
            wraplength=520, justify="left",
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        switch_frame = ctk.CTkFrame(self, fg_color="transparent")
        switch_frame.grid(row=0, column=1, padx=12, pady=8, sticky="e")
        self.state_label = ctk.CTkLabel(switch_frame, text=self._state_text(initial), text_color=TEXT_MUTED, width=70)
        self.state_label.pack(side="left", padx=(0, 6))
        self.switch_var = ctk.BooleanVar(value=initial)
        self.switch = ctk.CTkSwitch(
            switch_frame, text="", variable=self.switch_var, progress_color=ACCENT,
            command=self._toggled,
        )
        self.switch.pack(side="left")

    def _state_text(self, value: bool) -> str:
        return _t("toggle_on", self.lang) if value else _t("toggle_off", self.lang)

    def _toggled(self) -> None:
        value = self.switch_var.get()
        self.state_label.configure(text=self._state_text(value))
        self._on_toggle(value)

    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self.name_label.configure(text=_t(self.label_key, lang))
        self.state_label.configure(text=self._state_text(self.switch_var.get()))


class SettingNumberRow(ctk.CTkFrame):
    """Like SettingSwitchRow, but for a small bounded-integer setting
    (e.g. idle-timeout minutes) instead of an on/off switch.

    Explicit "Save" button instead of silent save-on-blur — the button
    is only enabled while the field holds an unsaved, valid change, and
    briefly confirms after a save, so it's always visually obvious
    whether a typed value actually took effect."""

    def __init__(
        self, master, label_key: str, lang: str, initial: int, on_change,
        minimum: int = 1, maximum: int | None = None,
    ):
        super().__init__(master, fg_color=CARD_BG, border_width=1, border_color=BORDER, corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.label_key = label_key
        self.lang = lang
        self._on_change = on_change
        self._minimum = minimum
        self._maximum = maximum
        self._value = initial

        self.name_label = ctk.CTkLabel(
            self, text=_t(label_key, lang), font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN,
            wraplength=520, justify="left",
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        entry_frame.grid(row=0, column=1, padx=12, pady=8, sticky="e")
        self.entry_var = ctk.StringVar(value=str(initial))
        self.entry = ctk.CTkEntry(
            entry_frame, textvariable=self.entry_var, width=56, justify="center",
            fg_color=BG, border_color=BORDER, text_color=TEXT_MAIN, corner_radius=8,
        )
        self.entry.pack(side="left")
        self.entry.bind("<Return>", lambda _e: self._commit())
        self.entry_var.trace_add("write", lambda *_a: self._on_entry_changed())
        self.suffix_label = ctk.CTkLabel(entry_frame, text=_t("minutes_suffix", lang), text_color=TEXT_MUTED)
        self.suffix_label.pack(side="left", padx=(6, 10))
        self.save_btn = ctk.CTkButton(
            entry_frame, text=_t("btn_save", lang), width=72, command=self._commit,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_INK,
            state="disabled",
        )
        self.save_btn.pack(side="left")

    def _is_valid(self, raw: str) -> int | None:
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        if value < self._minimum or (self._maximum is not None and value > self._maximum):
            return None
        return value

    def _on_entry_changed(self) -> None:
        value = self._is_valid(self.entry_var.get())
        dirty = value is not None and value != self._value
        self.save_btn.configure(
            state="normal" if dirty else "disabled",
            text=_t("btn_save", self.lang),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        )

    def _commit(self) -> None:
        value = self._is_valid(self.entry_var.get())
        if value is None:
            self.entry_var.set(str(self._value))  # revert — out of range or not a number
            return
        self.entry_var.set(str(value))
        if value != self._value:
            self._value = value
            self._on_change(value)
        self.save_btn.configure(state="disabled", text=_t("btn_saved", self.lang), fg_color=GREEN, hover_color=GREEN)
        self.after(1200, lambda: self.save_btn.configure(text=_t("btn_save", self.lang), fg_color=ACCENT, hover_color=ACCENT_HOVER))

    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self.name_label.configure(text=_t(self.label_key, lang))
        self.suffix_label.configure(text=_t("minutes_suffix", lang))
        if self.save_btn.cget("state") == "normal":
            self.save_btn.configure(text=_t("btn_save", lang))


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
        self._server_starting = False  # true only during start_with_retry()'s background attempt
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.log_visible = True
        self._extra_log_widgets: list[ctk.CTkTextbox] = []  # expanded-log popups also live-fed
        self._log_popup: ctk.CTkToplevel | None = None  # only one expanded window at a time
        # Per-profile idle-backup tracking, keyed by profile id: last seen
        # last_backup_at + wall-clock time it last changed + whether we've
        # already logged the "looks stopped" notice for this stretch of
        # inactivity (reset the moment new activity or a finished run shows
        # up) — see _check_idle_backups().
        self._idle_tracking: dict[str, dict] = {}
        self.current_screen = "main"
        self._principal_rows: dict[str, ProfileStatusRow] = {}
        self._principal_empty_label: ctk.CTkLabel | None = None
        self._settings_rows: dict[str, ProfileManageRow] = {}
        self._settings_empty_label: ctk.CTkLabel | None = None
        self._mirror_cancel_events: dict[str, threading.Event] = {}  # profile.id -> event, only while syncing

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
        self.after(1500, self._idle_check_loop)

        def _maximize() -> None:
            try:
                self.state("zoomed")  # open maximized by default (Windows)
            except Exception:
                pass  # cosmetic — never let this stop the app from opening

        # Setting "zoomed" synchronously during __init__() does nothing —
        # the OS window isn't actually mapped by the window manager until
        # mainloop() starts running (main() calls MainWindow() fully, THEN
        # mainloop()) — so this has to be deferred to right after the event
        # loop starts, once there's a real window for "zoomed" to apply to.
        self.after(10, _maximize)

        try:
            # Self-heals the registry entry's target path on every launch —
            # e.g. after a reinstall moves the .exe, or a dev/dist copy was
            # running last time this was toggled on.
            set_start_with_windows(self.cfg.start_with_windows)
        except Exception:
            pass  # best-effort; never block startup over a registry write

        if self.cfg.auto_start_backup:
            self._toggle_server()  # same behavior as clicking "Iniciar backup" by hand

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
            log_btn_row,
            text=self.t("hide_activity") if self.log_visible else self.t("show_activity"),
            command=self._toggle_log, anchor="w",
            fg_color=CARD_BG, hover_color=CARD_BG_ALT, border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        )
        self.log_toggle_btn.grid(row=0, column=0, sticky="ew")

        self.log_expand_btn = ctk.CTkButton(
            log_btn_row, text=self.t("expand_activity"), command=self._open_log_popup, width=110,
            fg_color=CARD_BG, hover_color=CARD_BG_ALT, border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        )
        self.log_expand_btn.grid(row=0, column=1, padx=(8, 0))

        self.log_frame = ctk.CTkFrame(parent, fg_color=CARD_BG_ALT, border_width=1, border_color=BORDER)
        self.log_box = ctk.CTkTextbox(
            self.log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#050505", text_color=TERMINAL_GREEN,
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")
        if self.log_visible:  # visible by default — see self.log_visible above
            self.log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

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

        self.preferences_title_label = ctk.CTkLabel(
            parent, text=self.t("settings_preferences_title"), font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_MAIN,
        )
        self.preferences_title_label.pack(anchor="w", padx=12, pady=(8, 4))

        self.start_with_windows_row = SettingSwitchRow(
            parent, "setting_start_with_windows", self.lang,
            self.cfg.start_with_windows, self._on_toggle_start_with_windows,
        )
        self.start_with_windows_row.pack(fill="x", padx=12, pady=(0, 6))

        self.auto_start_backup_row = SettingSwitchRow(
            parent, "setting_auto_start_backup", self.lang,
            self.cfg.auto_start_backup, self._on_toggle_auto_start_backup,
        )
        self.auto_start_backup_row.pack(fill="x", padx=12, pady=(0, 6))

        self.idle_timeout_row = SettingNumberRow(
            parent, "setting_idle_timeout", self.lang,
            self.cfg.idle_timeout_minutes, self._on_change_idle_timeout, minimum=1, maximum=30,
        )
        self.idle_timeout_row.pack(fill="x", padx=12, pady=(0, 10))

        header_row = ctk.CTkFrame(parent, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))
        self.profiles_title_label = ctk.CTkLabel(
            header_row, text=self.t("profiles_title"), font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_MAIN,
        )
        self.profiles_title_label.pack(side="left")
        self.add_profile_btn = ctk.CTkButton(
            header_row, text=self.t("add_profile"), width=140, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=ACCENT_INK, command=self._add_profile,
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

    def _on_toggle_start_with_windows(self, enabled: bool) -> None:
        self.cfg.start_with_windows = enabled
        self.cfg.save()
        try:
            set_start_with_windows(enabled)
        except Exception:
            import traceback

            details = traceback.format_exc()
            self._log_local(f"ERROR:\n{details}")
            show_error(self, self.lang, self.t("dlg_title_error"), self.t("err_unexpected", val=details))

    def _on_toggle_auto_start_backup(self, enabled: bool) -> None:
        self.cfg.auto_start_backup = enabled
        self.cfg.save()

    def _on_change_idle_timeout(self, minutes: int) -> None:
        self.cfg.idle_timeout_minutes = minutes
        self.cfg.save()

    def _apply_language(self) -> None:
        """Re-applies every translatable widget's text in place — no restart."""
        self.tagline_label.configure(text=self.t("tagline"))
        self.nav_main_btn.configure(text=self.t("nav_main"))
        self.nav_settings_btn.configure(text=self.t("nav_settings"))

        running = bool(self.controller and self.controller.running)
        self.start_btn.configure(text=self.t("btn_stop") if running else self.t("btn_start"))
        if self._server_starting:
            self.status_label.configure(text=self.t("status_starting"))
        else:
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
        self.preferences_title_label.configure(text=self.t("settings_preferences_title"))
        self.start_with_windows_row.set_lang(self.lang)
        self.auto_start_backup_row.set_lang(self.lang)
        self.idle_timeout_row.set_lang(self.lang)
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

        # Persists every line that ever reaches the on-screen activity log
        # (both server-side "backup_engine" records and GUI-only messages
        # like "Servidor iniciado" or the idle notice) so past activity can
        # be checked after the fact — the on-screen textbox alone is lost
        # the moment the app closes. Rotates daily, keeps ~6 months.
        log_dir = user_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_dir / "activity.log", when="midnight", backupCount=180, encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s > %(message)s", datefmt="%d-%m-%Y %H:%M:%S"))
        self._file_logger = logging.getLogger("punkbackup.activity_file")
        self._file_logger.setLevel(logging.INFO)
        self._file_logger.addHandler(file_handler)
        self._file_logger.propagate = False  # never feed into the root logger/console

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
        controller = ServerController(app_module.app, host="0.0.0.0", port=self.cfg.port)

        # A silent bind failure (port conflict, permission issue) used to
        # leave the GUI showing "Escuchando..." while nothing was really
        # listening, with no way for the user (or the iPhone) to tell
        # until "Could not connect to the server" showed up on the phone.
        # The retry below additionally covers a real, recurring cause of
        # that conflict: Avast intercepting the freshly-launched unsigned
        # exe, killing it, and relaunching it — during that brief window
        # Windows can still refuse to rebind the just-released port even
        # though nothing is genuinely holding it a few seconds later. The
        # retry loop blocks for a few seconds, so it runs off the Tkinter
        # thread; the button is disabled meanwhile so a double-click can't
        # start two attempts at once.
        self.start_btn.configure(state="disabled")
        self._server_starting = True
        self.status_label.configure(text=self.t("status_starting"), text_color=TEXT_MUTED)
        self._log_local(self.t("log_server_starting"))

        def worker() -> None:
            ok = controller.start_with_retry()
            self.after(0, lambda: self._on_server_start_result(controller, ok))

        threading.Thread(target=worker, daemon=True).start()

    def _on_server_start_result(self, controller: ServerController, ok: bool) -> None:
        self.start_btn.configure(state="normal")
        self._server_starting = False
        if not ok:
            details = controller.start_error or self.t("err_server_start_unknown")
            self.start_btn.configure(
                text=self.t("btn_start"), fg_color=GREEN, hover_color=GREEN_HOVER, text_color="#08120b"
            )
            self.status_label.configure(text=self.t("status_stopped"), text_color=TEXT_MUTED)
            self._log_local(f"ERROR: {self.t('log_server_start_failed', details=details)}")
            show_error(
                self, self.lang, self.t("dlg_title_error"),
                self.t("err_server_start_failed", details=details, port=self.cfg.port),
            )
            return

        self.controller = controller
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
            "choose_mirror": self._choose_profile_mirror,
            "remove_mirror": self._remove_profile_mirror,
            "sync_mirror": self._sync_profile_mirror,
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
    # Profiles — optional second copy (mirror). See PLAN.md section 13.
    # Deliberately never touches app_module/_engine_for — the iPhone-
    # facing path must never be affected by anything here.
    # ------------------------------------------------------------------
    def _choose_profile_mirror(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        chosen = filedialog.askdirectory(
            title=self.t("dlg_choose_mirror_title", name=current.name),
            initialdir=current.mirror_dir or None,
        )
        if not chosen:
            return
        try:
            self.profile_store.set_mirror_destination(profile.id, chosen)
        except ValueError:
            show_error(
                self, self.lang, self.t("dlg_mirror_same_folder_title"), self.t("dlg_mirror_same_folder_text")
            )
            return
        self._refresh_settings_profiles()

    def _remove_profile_mirror(self, profile: Profile) -> None:
        current = self.profile_store.get(profile.id) or profile
        if not ask_yes_no(
            self, self.lang, self.t("dlg_remove_mirror_title"), self.t("dlg_remove_mirror_text", name=current.name)
        ):
            return
        self.profile_store.clear_mirror_destination(profile.id)
        self._refresh_settings_profiles()

    def _sync_profile_mirror(self, profile: Profile) -> None:
        """Same single-button-toggles-behavior pattern as _toggle_server():
        while a sync for this profile is already running, this same
        button (now showing "Detener") stops it instead of starting a new
        one — e.g. so the user can safely eject the drive."""
        existing = self._mirror_cancel_events.get(profile.id)
        if existing is not None:
            existing.set()
            return

        current = self.profile_store.get(profile.id) or profile
        if not current.destination_dir or not current.mirror_dir:
            return  # button should be disabled in this case, but guard anyway

        primary_root = Path(current.destination_dir)
        mirror_root = Path(current.mirror_dir)
        try:
            # reap_dangling_runs=False: this is a SECOND ManifestDB on the
            # same primary destination the running server may already have
            # one open for -- without this, opening it here could reap a
            # real, still-in-progress run from the phone right out from
            # under it (confirmed live, 2026-09-22 -- see manifest_db.py).
            primary_db = ManifestDB(primary_root, reap_dangling_runs=False)
        except OSError as exc:
            show_error(self, self.lang, self.t("dlg_title_error"), self.t("err_mirror_sync_fatal", error=str(exc)))
            return

        cancel_event = threading.Event()
        self._mirror_cancel_events[profile.id] = cancel_event

        row = self._settings_rows.get(profile.id)
        if row is not None:
            row.set_syncing(True, self.lang)
        self._log_local(self.t("log_mirror_sync_started", name=current.name))

        def on_progress(done: int, total: int) -> None:
            self.after(0, lambda: self._on_mirror_progress(profile.id, done, total))

        def worker() -> None:
            # sync_mirror() itself never raises (see its docstring) -- an
            # uncaught exception here would skip the self.after(...) below
            # and leave the GUI stuck showing "Syncing..." forever with no
            # visible error, so this is defense in depth, not the primary
            # safety net.
            try:
                result = sync_mirror(
                    primary_root, primary_db, mirror_root,
                    progress_callback=on_progress, cancel_event=cancel_event,
                )
            except Exception as exc:
                result = MirrorSyncResult(fatal_error=str(exc))
            finally:
                try:
                    primary_db.close()
                except Exception:
                    pass
            self.after(0, lambda: self._on_mirror_sync_done(profile, result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_mirror_progress(self, profile_id: str, done: int, total: int) -> None:
        row = self._settings_rows.get(profile_id)
        if row is None:
            return
        free_bytes = total_bytes = None
        profile = self.profile_store.get(profile_id)
        if profile and profile.mirror_dir:
            try:
                usage = shutil.disk_usage(profile.mirror_dir)
                free_bytes, total_bytes = usage.free, usage.total
            except OSError:
                pass  # drive hiccup mid-sync -- just skip the space readout for this one update
        row.set_sync_progress(done, total, self.lang, free_bytes, total_bytes)

    def _on_mirror_sync_done(self, profile: Profile, result: MirrorSyncResult) -> None:
        self._mirror_cancel_events.pop(profile.id, None)
        row = self._settings_rows.get(profile.id)
        if row is not None:
            row.set_syncing(False, self.lang)
        if result.fatal_error:
            self._log_local(f"ERROR: {self.t('log_mirror_sync_fatal', name=profile.name, error=result.fatal_error)}")
            show_error(self, self.lang, self.t("dlg_title_error"), self.t("err_mirror_sync_fatal", error=result.fatal_error))
            self._refresh_settings_profiles()
            return
        if result.cancelled:
            # Not an error -- the user asked for this (e.g. to safely eject
            # the drive). Whatever was already copied+verified stays valid.
            self._log_local(self.t("log_mirror_sync_cancelled", name=profile.name, copied=result.copied))
            self._refresh_settings_profiles()
            return
        self._log_local(
            self.t(
                "log_mirror_sync_done", name=profile.name,
                copied=result.copied, verify_failed=result.verify_failed,
            )
        )
        if result.stopped_with_error:
            # The real OS error text, not just "something stopped it" --
            # previously only shown in the (transient, easy to dismiss and
            # lose) warning dialog below, with no way to check it after the
            # fact. Found the hard way (2026-09-21): guessed "disk full"
            # from a small USB without actually reading this string, which
            # turned out to be wrong once real free space was checked.
            self._log_local(f"  -> {result.stopped_with_error}")
        # elif, not two separate ifs: both can be true at once (confirmed on
        # a real device, 2026-09-21 -- a small mirror USB triggered the
        # up-front space warning AND then genuinely ran out mid-copy).
        # Stacking two modal dialogs back to back also surfaced a real
        # crash in the shared dialog code (see gui/dialogs.py) -- fixed
        # there too, but avoiding the stack in the first place is simply
        # better UX: stopped_with_error already explains what happened, a
        # second "might not have enough space" popup right after is just
        # redundant noise.
        if result.stopped_with_error:
            show_warning(
                self, self.lang, self.t("dlg_title_warning"),
                self.t("warn_mirror_stopped_with_error", error=result.stopped_with_error),
            )
        elif result.insufficient_space_warning:
            show_warning(self, self.lang, self.t("dlg_title_warning"), self.t("warn_mirror_low_space"))
        self._refresh_settings_profiles()

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
            stamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            line = f"{stamp} > {text}\n"
            try:
                self._file_logger.info(text)
            except Exception:
                pass  # persisting to disk is best-effort — never block the live display over it
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            for widget in list(self._extra_log_widgets):
                if not widget.winfo_exists():
                    self._extra_log_widgets.remove(widget)
                    continue
                widget.configure(state="normal")
                widget.insert("end", line)
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
                import traceback

                self._log_local(f"ERROR in _refresh_status_loop:\n{traceback.format_exc()}")
        self.after(1500, self._refresh_status_loop)

    def _idle_check_loop(self) -> None:
        """Deliberately its OWN after()-scheduled loop, separate from
        _refresh_status_loop above — a slow/failing stats refresh (e.g. a
        transient SQLite lock during a heavy upload burst) must never be
        able to silently starve idle detection of ticks just because they
        used to share one try/except block. Confirmed via a real missed
        notice (2026-09-18): a 14+ minute gap with zero log activity while
        a run stayed "running" produced no notice at all, with no error
        visible anywhere — see PLAN.md for the write-up."""
        try:
            self._check_idle_backups()
        except Exception:
            import traceback

            self._log_local(f"ERROR in _idle_check_loop:\n{traceback.format_exc()}")
        self.after(1500, self._idle_check_loop)

    def _check_idle_backups(self) -> None:
        """A run has no persistent connection to watch — the server can
        only infer "the phone stopped talking to us" from a lack of new
        files while a run is still marked "running" (no /run/finish yet).
        Logs a one-time notice per stretch of inactivity, per profile;
        resets the moment new activity shows up or the run finishes."""
        now = datetime.now(timezone.utc)
        for profile in self.profile_store.list():
            tracking = self._idle_tracking.setdefault(
                profile.id, {"last_backup_at": None, "seen_at": now, "notified": False, "error_logged": False}
            )

            try:
                st = app_module.get_status_for_profile(profile)
            except Exception:
                # Routine, expected conditions (e.g. a brand-new profile
                # with no destination folder chosen yet) raise here too —
                # not bugs. Log any exception only ONCE per stretch of
                # failures (not every 1.5s forever) so a real, unexpected
                # error is still never silent, but a normal "not set up
                # yet" state doesn't flood the log either.
                if not tracking["error_logged"]:
                    tracking["error_logged"] = True
                    import traceback

                    self._log_local(f"ERROR checking idle status for {profile.name}:\n{traceback.format_exc()}")
                continue
            tracking["error_logged"] = False

            if st["state"] != "running":
                tracking["last_backup_at"] = None
                tracking["notified"] = False
                continue

            current_backup_at = st.get("last_backup_at")
            if current_backup_at != tracking["last_backup_at"]:
                tracking["last_backup_at"] = current_backup_at
                tracking["seen_at"] = now
                tracking["notified"] = False
                continue

            idle_seconds = (now - tracking["seen_at"]).total_seconds()
            if idle_seconds >= self.cfg.idle_timeout_minutes * 60 and not tracking["notified"]:
                tracking["notified"] = True
                self._log_local(
                    self.t("log_backup_idle", name=profile.name, minutes=self.cfg.idle_timeout_minutes)
                )

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
