"""Custom dark/punk-themed modal dialogs.

Replaces `tkinter.messagebox` (and `ctk.CTkInputDialog`'s default styling)
throughout the GUI. `messagebox` renders as a plain light/white native OS
dialog no matter what CustomTkinter's appearance mode is set to — it broke
the dark theme jarringly every time a profile was created, renamed, etc.
These are built from plain CTkToplevel + CTk widgets instead, so they
inherit the same palette as the rest of the app (see BG/CARD_BG/ACCENT in
gui/main_window.py — duplicated here rather than imported, to avoid a
circular import between the two modules).

Every function here is modal (blocks until the user responds) and centers
itself over its parent window, matching how messagebox/CTkInputDialog used
to behave — callers don't need to change their control flow, just the
import.
"""
from __future__ import annotations

import textwrap

import customtkinter as ctk

from server.paths import app_root

BG = "#0c0c0e"
CARD_BG = "#19191d"
CARD_BG_ALT = "#221418"
BORDER = "#2c2c32"
TEXT_MAIN = "#f2f2f5"
TEXT_MUTED = "#9a9aa3"
ACCENT = "#ff2d55"
ACCENT_HOVER = "#c81d4a"
ACCENT_INK = "#1a0308"
AMBER = "#ffb020"
RED = "#ff3b30"
RED_HOVER = "#c62828"

ICON_PATH = app_root() / "assets" / "punkbackup.ico"

_BUTTON_LABELS = {
    "ok": {"es": "Aceptar", "en": "OK"},
    "yes": {"es": "Sí", "en": "Yes"},
    "no": {"es": "No", "en": "No"},
    "cancel": {"es": "Cancelar", "en": "Cancel"},
    "copy": {"es": "📋 Copiar", "en": "📋 Copy"},
    "copied": {"es": "✓ Copiado", "en": "✓ Copied"},
}


def _btn_text(key: str, lang: str) -> str:
    return _BUTTON_LABELS[key].get(lang, _BUTTON_LABELS[key]["es"])


# Rough estimate of how many characters fit on one visual line of the
# message box (width=420, 13pt font, see _PunkDialog) — tuned against the
# real warn_*/err_* messages in gui/i18n.py, not derived from font metrics.
_CHARS_PER_LINE = 55


def _estimate_display_lines(message: str) -> int:
    """A pure-Python estimate of how many visual lines `message` will wrap
    to — deliberately does NOT ask Tk to measure the real rendered text
    (e.g. via CTkTextbox's underlying widget and its "displaylines" count),
    because getting an accurate answer that way requires pumping Tk's
    event loop with a FULL self.update() (update_idletasks() alone leaves
    the textbox's on-screen width unresolved) in the middle of building a
    modal dialog. Confirmed live (2026-09-24) that this froze the whole
    app: a dialog shown while another Tk callback was still in flight left
    an invisible, withdrawn window holding the modal grab forever, since
    _show_modal()'s own deiconify()/grab_set() was never reached — no
    button responded and no alert was visible, because the "visible"
    dialog never got shown. A character-count estimate is less accurate
    (worst case: a little extra blank space in the box) but involves zero
    Tk calls, so it can never hang the app. See AGENTS.md's dialogs
    lessons."""
    lines = 0
    for line in message.split("\n"):
        lines += len(textwrap.wrap(line, width=_CHARS_PER_LINE) or [""])
    return lines


def _capture_zoom(parent) -> bool:
    """True if `parent` (the main window) is currently maximized. Call
    this right before a modal dialog's `wait_window()` — see
    `_restore_zoom` for why."""
    try:
        return parent.state() == "zoomed"
    except Exception:
        return False


def _restore_zoom(parent, was_zoomed: bool) -> None:
    """Windows/Tk quirk, confirmed live (2026-09-24): destroying a
    transient, grabbed Toplevel while its owner is maximized can silently
    drop the owner back to its "normal" size the instant this dialog
    closes — nothing in this codebase ever asks for that; it's the OS
    returning focus to the owner after a modal grab ends. Re-asserts
    "zoomed" only if the owner really was zoomed before AND the OS
    actually changed it — never forces a maximize on a window the user
    had deliberately un-maximized themselves before opening the dialog."""
    if not was_zoomed:
        return
    try:
        if parent.winfo_exists() and parent.state() != "zoomed":
            parent.state("zoomed")
    except Exception:
        pass


class _PunkDialog(ctk.CTkToplevel):
    """Base modal: dark card, colored accent dot + title, message area,
    button row. Subclasses/helpers below just fill in the button row."""

    def __init__(self, parent, title: str, message: str, dot_color: str):
        super().__init__(parent)
        self.result = None
        self.configure(fg_color=BG)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        # `_e=None` (not just `_e`): a real Escape keypress passes the event
        # object, but this can also fire with zero arguments -- confirmed on
        # a real device (2026-09-21) when two of these dialogs got shown
        # back to back (see gui/main_window.py's mirror-sync warnings),
        # crashing with "<lambda>() missing 1 required positional argument:
        # '_e'". Same defensive default ask_input()'s _confirm/_cancel
        # already use below, applied here too.
        self.bind("<Escape>", lambda _e=None: self._cancel())

        card = ctk.CTkFrame(self, fg_color=BG)
        card.pack(fill="both", expand=True, padx=20, pady=18)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            header, text="●", text_color=dot_color, font=ctk.CTkFont(size=16),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            header, text=title, text_color=TEXT_MAIN,
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        ).pack(side="left", fill="x", expand=True)

        display_lines = _estimate_display_lines(message)
        box_height = max(40, min(display_lines * 20 + 24, 360))
        body = ctk.CTkTextbox(
            card, width=420, height=box_height, fg_color=CARD_BG, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER, corner_radius=8, wrap="word",
            font=ctk.CTkFont(size=13), activate_scrollbars=True,
        )
        body.pack(fill="both", expand=True, pady=(0, 14))
        body.insert("1.0", message)
        body.configure(state="disabled")
        self._body = body

        self.button_row = ctk.CTkFrame(card, fg_color="transparent")
        self.button_row.pack(fill="x")

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _make_button(self, text: str, command, *, primary: bool = False, danger: bool = False) -> ctk.CTkButton:
        if danger:
            fg, hover, ink = RED, RED_HOVER, TEXT_MAIN
        elif primary:
            fg, hover, ink = ACCENT, ACCENT_HOVER, ACCENT_INK
        else:
            fg, hover, ink = "transparent", CARD_BG_ALT, TEXT_MAIN
        border = 0 if (primary or danger) else 1
        return ctk.CTkButton(
            self.button_row, text=text, command=command, fg_color=fg, hover_color=hover,
            text_color=ink, border_width=border, border_color=BORDER, corner_radius=8, width=110,
        )

    def _show_modal(self):
        self.update_idletasks()
        parent = self.master
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = max(px + (pw - w) // 2, 0)
        y = max(py + (ph - h) // 2, 0)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_set()
        was_zoomed = _capture_zoom(parent)
        self.wait_window()
        _restore_zoom(parent, was_zoomed)
        return self.result


def _message_dialog(
    parent, lang: str, title: str, message: str, dot_color: str,
    *, buttons: list[tuple[str, object, bool, bool]], copy_value: str | None = None,
) -> object:
    """buttons: list of (label, result_value, is_primary, is_danger)."""
    dlg = _PunkDialog(parent, title, message, dot_color)

    if copy_value is not None:
        copy_btn_ref: dict[str, ctk.CTkButton] = {}

        def _do_copy() -> None:
            parent.clipboard_clear()
            parent.clipboard_append(copy_value)
            btn = copy_btn_ref.get("btn")
            if btn is not None:
                btn.configure(text=_btn_text("copied", lang))
                dlg.after(1200, lambda: btn.configure(text=_btn_text("copy", lang)) if btn.winfo_exists() else None)

        copy_btn = dlg._make_button(_btn_text("copy", lang), _do_copy)
        copy_btn.pack(side="left")
        copy_btn_ref["btn"] = copy_btn

    for label, value, is_primary, is_danger in buttons:
        def _click(v=value) -> None:
            dlg.result = v
            dlg.destroy()
        dlg._make_button(label, _click, primary=is_primary, danger=is_danger).pack(side="right", padx=(8, 0))

    return dlg._show_modal()


def show_info(parent, lang: str, title: str, message: str, *, copy_value: str | None = None) -> None:
    _message_dialog(
        parent, lang, title, message, ACCENT,
        buttons=[(_btn_text("ok", lang), True, True, False)], copy_value=copy_value,
    )


def show_warning(parent, lang: str, title: str, message: str) -> None:
    _message_dialog(parent, lang, title, message, AMBER, buttons=[(_btn_text("ok", lang), True, True, False)])


def show_error(parent, lang: str, title: str, message: str) -> None:
    _message_dialog(parent, lang, title, message, RED, buttons=[(_btn_text("ok", lang), True, False, True)])


def ask_yes_no(parent, lang: str, title: str, message: str, *, danger: bool = False) -> bool:
    result = _message_dialog(
        parent, lang, title, message, RED if danger else ACCENT,
        buttons=[
            (_btn_text("no", lang), False, False, False),
            (_btn_text("yes", lang), True, not danger, danger),
        ],
    )
    return bool(result)


def ask_input(parent, lang: str, title: str, prompt: str, *, initial: str = "") -> str | None:
    dlg = ctk.CTkToplevel(parent)
    dlg.configure(fg_color=BG)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(parent)
    try:
        dlg.iconbitmap(str(ICON_PATH))
    except Exception:
        pass
    dlg.result: str | None = None

    card = ctk.CTkFrame(dlg, fg_color=BG)
    card.pack(fill="both", expand=True, padx=20, pady=18)

    ctk.CTkLabel(
        card, text=prompt, text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
        anchor="w", justify="left", wraplength=360,
    ).pack(fill="x", pady=(0, 10))

    entry = ctk.CTkEntry(
        card, width=360, fg_color=CARD_BG, border_color=BORDER, text_color=TEXT_MAIN, corner_radius=8,
    )
    entry.insert(0, initial)
    entry.pack(fill="x", pady=(0, 14))
    entry.focus_set()
    entry.select_range(0, "end")

    button_row = ctk.CTkFrame(card, fg_color="transparent")
    button_row.pack(fill="x")

    def _confirm(_e=None) -> None:
        dlg.result = entry.get().strip() or None
        dlg.destroy()

    def _cancel(_e=None) -> None:
        dlg.result = None
        dlg.destroy()

    dlg.protocol("WM_DELETE_WINDOW", _cancel)
    dlg.bind("<Escape>", _cancel)
    entry.bind("<Return>", _confirm)

    ctk.CTkButton(
        button_row, text=_btn_text("ok", lang), command=_confirm, fg_color=ACCENT,
        hover_color=ACCENT_HOVER, text_color=ACCENT_INK, corner_radius=8, width=110,
    ).pack(side="right", padx=(8, 0))
    ctk.CTkButton(
        button_row, text=_btn_text("cancel", lang), command=_cancel, fg_color="transparent",
        hover_color=CARD_BG_ALT, text_color=TEXT_MAIN, border_width=1, border_color=BORDER,
        corner_radius=8, width=110,
    ).pack(side="right")

    dlg.update_idletasks()
    parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    w, h = dlg.winfo_width(), dlg.winfo_height()
    x = max(px + (parent_w - w) // 2, 0)
    y = max(py + (parent_h - h) // 2, 0)
    dlg.geometry(f"+{x}+{y}")
    dlg.grab_set()
    was_zoomed = _capture_zoom(parent)
    dlg.wait_window()
    _restore_zoom(parent, was_zoomed)
    return dlg.result
