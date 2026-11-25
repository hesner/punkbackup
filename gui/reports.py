"""The "Reportes" screen, phase 1 (PLAN.md section 27): summary, timeline and run
history per profile, from what each destination's index already records.

`compute_report()` is a plain function that never touches Tk: it runs on a
background thread (AGENTS.md lesson 22) and reads the index read-only, never through
ManifestDB, so it can't close a run that's really in progress (lesson 16).
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from server.mirror import get_mirror_status

from .i18n import t as _t

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".3gp", ".mkv", ".mts", ".wmv"}
PHOTO_EXTS = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".dng", ".webp", ".tif", ".tiff", ".bmp", ".raw"}
RUNS_SHOWN = 20
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})")


def size_text(size_bytes: int, lang: str) -> str:
    """GB with one decimal, MB below 1 GB; Spanish uses a decimal comma."""
    if size_bytes >= 1e9:
        text = f"{size_bytes / 1e9:.1f} GB"
    elif 0 < size_bytes < 1e6:
        text = "<1 MB"  # a few small files never read as nothing
    else:
        text = f"{size_bytes / 1e6:.0f} MB"
    return text.replace(".", ",") if lang == "es" else text


def count_text(n: int, lang: str) -> str:
    text = f"{n:,}"
    return text.replace(",", ".") if lang == "es" else text


def _kind(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in VIDEO_EXTS:
        return "videos"
    if ext in PHOTO_EXTS:
        return "photos"
    return "other"


def _date_only(taken_at: Optional[str]) -> Optional[str]:
    m = re.match(r"^\d{4}-\d{2}-\d{2}", taken_at or "")
    return m.group(0) if m else None


def compute_report(dest_dir: str, mirror_dir: Optional[str] = None) -> dict:
    """Everything the screen shows for one destination. Never raises: a problem
    comes back as `state` ("unreachable", "empty" or "error")."""
    root = Path(dest_dir) if dest_dir else None
    if root is None or not root.is_dir():
        return {"state": "unreachable", "path": dest_dir or ""}
    db_path = root / ".iphone_backup_index" / "index.sqlite"
    if not db_path.exists():
        return {"state": "empty"}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            files = conn.execute("SELECT filename, size_bytes, taken_at, received_at FROM backed_up_files").fetchall()
            runs = conn.execute(
                "SELECT id, started_at, finished_at, source, files_new, files_skipped, files_conflict, files_error "
                "FROM runs ORDER BY started_at DESC LIMIT ?", (RUNS_SHOWN,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"state": "error", "error": str(exc)}
    if not files and not runs:
        return {"state": "empty"}

    kinds = {k: [0, 0] for k in ("photos", "videos", "other")}
    undated = [0, 0]
    years: dict[str, list[int]] = {}
    months: dict[str, dict[str, list[int]]] = {}
    oldest = newest = last_received = None
    total_bytes = 0
    for filename, size, taken_at, received_at in files:
        size = size or 0
        total_bytes += size
        k = kinds[_kind(filename)]
        k[0] += 1
        k[1] += size
        m = _YEAR_MONTH.match(taken_at or "")
        if m:
            y, mo = m.group(1), m.group(2)
            years.setdefault(y, [0, 0])
            years[y][0] += 1
            years[y][1] += size
            months.setdefault(y, {}).setdefault(mo, [0, 0])
            months[y][mo][0] += 1
            months[y][mo][1] += size
            day = _date_only(taken_at)
            if oldest is None or day < oldest:
                oldest = day
            if newest is None or day > newest:
                newest = day
        else:
            undated[0] += 1
            undated[1] += size
        if received_at and (last_received is None or received_at > last_received):
            last_received = received_at

    run_rows = []
    for i, (rid, started, finished, source, new, skipped, conflict, error) in enumerate(runs):
        if finished:
            state = "done"
        else:
            state = "running" if i == 0 else "open"
        run_rows.append({
            "id": rid, "started_at": started, "finished_at": finished, "source": source or "wifi",
            "new": new or 0, "skipped": skipped or 0, "conflict": conflict or 0, "errors": error or 0,
            "state": state, "seconds": _seconds_between(started, finished),
        })

    try:
        usage = shutil.disk_usage(root)
        free, total = usage.free, usage.total
    except OSError:
        free = total = None

    mirror: Optional[dict] = None
    if mirror_dir:
        status = get_mirror_status(mirror_dir)
        if status is None:
            mirror = {"state": "not_connected"}
        else:
            missing = max(len(files) - status.get("total_files", 0), 0)
            mirror = {"state": "ok" if missing == 0 else "behind", "files": status.get("total_files", 0), "missing": missing}

    return {
        "state": "ok",
        "files": len(files), "bytes": total_bytes,
        "kinds": {k: tuple(v) for k, v in kinds.items()},
        "undated": tuple(undated),
        "oldest": oldest, "newest": newest, "last_received": last_received,
        "years": [(y, *years[y]) for y in sorted(years)],
        "months": {y: [(mo, *months[y][mo]) for mo in sorted(months[y])] for y in months},
        "runs": run_rows,
        "free_bytes": free, "total_bytes": total,
        "mirror": mirror,
    }


def _seconds_between(start: Optional[str], end: Optional[str]) -> Optional[float]:
    if not start or not end:
        return None
    try:
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if a.tzinfo is None:
            a = a.replace(tzinfo=timezone.utc)
        if b.tzinfo is None:
            b = b.replace(tzinfo=timezone.utc)
        return max((b - a).total_seconds(), 0.0)
    except ValueError:
        return None


def duration_text(seconds: Optional[float], lang: str) -> str:
    if seconds is None:
        return "—"
    minutes = int(round(seconds / 60))
    if minutes < 1:
        return _t("rep_duration_short", lang)
    if minutes < 60:
        return _t("rep_duration_min", lang, m=minutes)
    return _t("rep_duration_h", lang, h=minutes // 60, m=minutes % 60)


def local_time(iso_utc: Optional[str]) -> str:
    if not iso_utc:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_utc


def summary_lines(report: dict, lang: str) -> list[str]:
    """The summary card's text, one entry per line (pure, tested)."""
    if report["state"] != "ok":
        return []
    lines = [_t("rep_total", lang, count=count_text(report["files"], lang), size=size_text(report["bytes"], lang))]
    for kind in ("photos", "videos", "other"):
        n, b = report["kinds"][kind]
        if n or kind != "other":
            lines.append(_t(f"rep_{kind}", lang, count=count_text(n, lang), size=size_text(b, lang)))
    if report["oldest"]:
        lines.append(_t("rep_range", lang, oldest=report["oldest"], newest=report["newest"]))
    if report["undated"][0]:
        n, b = report["undated"]
        lines.append(_t("rep_undated", lang, count=count_text(n, lang), size=size_text(b, lang)))
    lines.append(_t("rep_last", lang, last=local_time(report["last_received"])))
    if report["free_bytes"] is not None:
        lines.append(_t("rep_disk", lang, free=size_text(report["free_bytes"], lang), total=size_text(report["total_bytes"], lang)))
    mirror = report["mirror"]
    if mirror is None:
        lines.append(_t("rep_mirror_none", lang))
    elif mirror["state"] == "not_connected":
        lines.append(_t("rep_mirror_off", lang))
    elif mirror["state"] == "ok":
        lines.append(_t("rep_mirror_ok", lang, count=count_text(mirror["files"], lang)))
    else:
        lines.append(_t("rep_mirror_behind", lang, missing=count_text(mirror["missing"], lang)))
    return lines


def run_line(run: dict, lang: str) -> str:
    return _t(
        "rep_run_line", lang,
        start=local_time(run["started_at"]),
        source=_t("rep_source_cable" if run["source"] == "cable" else "rep_source_wifi", lang),
        duration=duration_text(run["seconds"], lang),
        new=count_text(run["new"], lang),
        errors=count_text(run["errors"], lang),
        state=_t(f"rep_state_{run['state']}", lang),
    )


def month_name(month: str, lang: str) -> str:
    names = _t("rep_month_names", lang).split(",")
    try:
        return names[int(month) - 1]
    except (ValueError, IndexError):
        return month


class ReportsScreen(ctk.CTkScrollableFrame):
    """Built like the other screens; colors come in as the active palette. It only
    calculates while it's on screen, when asked (on show, profile change, Refresh)."""

    def __init__(self, master, pal: dict, lang: str, get_profiles: Callable[[], list]):
        super().__init__(master, fg_color=pal["BG"])
        self.pal = pal
        self.lang = lang
        self._get_profiles = get_profiles
        self._report: Optional[dict] = None
        self._profile_id: Optional[str] = None
        self._generation = 0
        self._open_years: set[str] = set()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=4, pady=(4, 8))
        self.profile_label = ctk.CTkLabel(top, text="", text_color=pal["TEXT_MAIN"])
        self.profile_label.pack(side="left", padx=(4, 6))
        self.profile_menu = ctk.CTkOptionMenu(
            top, values=[""], command=self._on_pick, fg_color=pal["CONTROL_BG"], text_color=pal["CONTROL_TEXT"],
            button_color=pal["ACCENT"], button_hover_color=pal["ACCENT_HOVER"],
        )
        self.profile_menu.pack(side="left")
        self.refresh_btn = ctk.CTkButton(
            top, text="", width=110, command=self.refresh, fg_color=pal["ACCENT"], hover_color=pal["ACCENT_HOVER"],
            text_color=pal["ACCENT_INK"],
        )
        self.refresh_btn.pack(side="left", padx=8)
        self.state_label = ctk.CTkLabel(top, text="", text_color=pal["TEXT_MUTED"])
        self.state_label.pack(side="left", padx=4)

        self.summary_card = self._card()
        self.timeline_card = self._card()
        self.runs_card = self._card()
        self._set_texts()

    # -- building blocks -------------------------------------------------------
    def _card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=self.pal["CARD_BG"], border_width=self.pal["BORDER_WIDTH"],
                            border_color=self.pal["BORDER"], corner_radius=8)
        card.pack(fill="x", padx=4, pady=(0, 10))
        return card

    def _title(self, card, key: str) -> None:
        ctk.CTkLabel(card, text=_t(key, self.lang), font=ctk.CTkFont(weight="bold"),
                     text_color=self.pal["TEXT_MAIN"]).pack(anchor="w", padx=12, pady=(10, 4))

    def _text(self, card, text: str, muted: bool = True, pady=(0, 2)) -> ctk.CTkLabel:
        label = ctk.CTkLabel(card, text=text, justify="left", anchor="w",
                             text_color=self.pal["TEXT_MUTED" if muted else "TEXT_MAIN"])
        label.pack(anchor="w", fill="x", padx=12, pady=pady)
        return label

    @staticmethod
    def _clear(card) -> None:
        for child in card.winfo_children():
            child.destroy()

    def _set_texts(self) -> None:
        self.profile_label.configure(text=_t("rep_profile", self.lang))
        self.refresh_btn.configure(text=_t("rep_refresh", self.lang))

    # -- profiles and calculation ----------------------------------------------
    def _eligible(self) -> list:
        return [p for p in self._get_profiles() if p.destination_dir]

    def on_show(self) -> None:
        profiles = self._eligible()
        names = [p.name for p in profiles]
        if not profiles:
            self.profile_menu.configure(values=[""])
            self.profile_menu.set("")
            self._profile_id = None
            self._report = {"state": "no_profiles"}
            self._render()
            return
        self.profile_menu.configure(values=names)
        if self._profile_id not in {p.id for p in profiles}:
            self._profile_id = profiles[0].id
        current = next(p for p in profiles if p.id == self._profile_id)
        self.profile_menu.set(current.name)
        self.refresh()

    def _on_pick(self, name: str) -> None:
        match = next((p for p in self._eligible() if p.name == name), None)
        if match is not None and match.id != self._profile_id:
            self._profile_id = match.id
            self._open_years.clear()
            self.refresh()

    def refresh(self) -> None:
        profile = next((p for p in self._eligible() if p.id == self._profile_id), None)
        if profile is None:  # deleted or lost its folder since: pick again
            if self._eligible():
                self._profile_id = None
                self.on_show()
            return
        self._generation += 1
        generation = self._generation
        self.state_label.configure(text=_t("rep_loading", self.lang))
        self.refresh_btn.configure(state="disabled")
        dest, mirror = profile.destination_dir, getattr(profile, "mirror_dir", None) or None

        def work():
            try:
                report = compute_report(dest, mirror)
            except Exception as exc:  # compute_report shouldn't raise; never leave the screen stuck
                report = {"state": "error", "error": str(exc)}
            try:
                self.after(0, lambda: self._done(generation, report))
            except RuntimeError:
                pass  # window already closed

        threading.Thread(target=work, daemon=True).start()

    def _done(self, generation: int, report: dict) -> None:
        if generation != self._generation or not self.winfo_exists():
            return  # a newer request (another profile, Refresh) is on its way
        self.refresh_btn.configure(state="normal")
        self.state_label.configure(text="")
        self._report = report
        self._render()

    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self._set_texts()
        if self._report is not None:
            self._render()

    # -- rendering ---------------------------------------------------------------
    def _render(self) -> None:
        report = self._report or {}
        for card in (self.summary_card, self.timeline_card, self.runs_card):
            self._clear(card)
        state = report.get("state")
        self._title(self.summary_card, "rep_summary_title")
        if state != "ok":
            message = {
                "no_profiles": _t("rep_no_profiles", self.lang),
                "unreachable": _t("rep_unreachable", self.lang, path=report.get("path", "")),
                "empty": _t("rep_empty", self.lang),
                "error": _t("rep_error", self.lang, error=report.get("error", "")),
            }.get(state, "")
            self._text(self.summary_card, message, muted=False, pady=(0, 10))
            self.timeline_card.pack_forget()
            self.runs_card.pack_forget()
            return
        self.timeline_card.pack(fill="x", padx=4, pady=(0, 10))
        self.runs_card.pack(fill="x", padx=4, pady=(0, 10))
        lines = summary_lines(report, self.lang)
        for i, line in enumerate(lines):
            self._text(self.summary_card, line, muted=i != 0, pady=(0, 10) if i == len(lines) - 1 else (0, 2))
        self._render_timeline(report)
        self._render_runs(report)

    def _bar_row(self, parent, label: str, n: int, b: int, biggest: int, command=None, indent: int = 0) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=(12 + indent, 12), pady=1)
        row.grid_columnconfigure(1, weight=1)
        if command is not None:
            ctk.CTkButton(row, text=label, width=70, height=22, command=command, fg_color="transparent",
                          hover_color=self.pal["NAV_HOVER"], text_color=self.pal["TEXT_MAIN"], anchor="w",
                          ).grid(row=0, column=0, sticky="w")
        else:
            ctk.CTkLabel(row, text=label, width=70, anchor="w", text_color=self.pal["TEXT_MUTED"]).grid(row=0, column=0, sticky="w")
        bar = ctk.CTkProgressBar(row, height=10, progress_color=self.pal["ACCENT"], fg_color=self.pal["PROGRESS_TRACK"])
        bar.grid(row=0, column=1, sticky="ew", padx=8)
        bar.set(n / biggest if biggest else 0)
        key = "rep_count_size_one" if n == 1 else "rep_count_size"
        ctk.CTkLabel(row, text=_t(key, self.lang, count=count_text(n, self.lang), size=size_text(b, self.lang)),
                     width=190, anchor="w", text_color=self.pal["TEXT_MUTED"]).grid(row=0, column=2, sticky="w")

    def _render_timeline(self, report: dict) -> None:
        card = self.timeline_card
        self._title(card, "rep_timeline_title")
        self._text(card, _t("rep_timeline_hint", self.lang), pady=(0, 6))
        biggest = max([n for _, n, _ in report["years"]] + [report["undated"][0], 1])
        rows = ctk.CTkFrame(card, fg_color="transparent")
        rows.pack(fill="x", pady=(0, 10))
        for year, n, b in report["years"]:
            opened = year in self._open_years
            self._bar_row(rows, ("▾ " if opened else "▸ ") + year, n, b, biggest, command=lambda y=year: self._toggle_year(y))
            if opened:
                months = report["months"].get(year, [])
                top = max([mn for _, mn, _ in months] + [1])
                for month, mn, mb in months:
                    self._bar_row(rows, month_name(month, self.lang), mn, mb, top, indent=24)
        if report["undated"][0]:
            n, b = report["undated"]
            self._bar_row(rows, _t("rep_undated_row", self.lang), n, b, biggest)

    def _toggle_year(self, year: str) -> None:
        self._open_years.symmetric_difference_update({year})
        self._clear(self.timeline_card)
        self._render_timeline(self._report)

    def _render_runs(self, report: dict) -> None:
        card = self.runs_card
        self._title(card, "rep_runs_title")
        if not report["runs"]:
            self._text(card, _t("rep_runs_none", self.lang), pady=(0, 10))
            return
        for run in report["runs"]:
            self._text(card, run_line(run, self.lang), muted=run["state"] == "done")
        self._text(card, _t("rep_runs_note", self.lang, n=RUNS_SHOWN), pady=(6, 10))
