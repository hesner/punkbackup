# AGENTS.md — Building PunkBackup from scratch

This document is for an AI agent (or a human developer) tasked with
rebuilding this system from nothing, or extending it correctly. It captures
not just *what* to build, but *why* — including several non-obvious lessons
learned the hard way during real device testing. Skipping these will
reproduce the exact bugs already found and fixed once.

Read `PLAN.md` first for the full architecture and current decisions; this
file is about **how to build it correctly and in the right order**.

## 1. What this system is

A one-directional (iPhone/iPad → PC) photo/video backup system:
- No USB cable, no iCloud. Transfer happens over the local WiFi network.
- Multiple people/devices ("profiles"), each with its own secret token and
  its own destination folder (possibly a different USB drive per person).
- Incremental: never re-uploads what's already at the destination, never
  overwrites, never deletes anything from the source (the iPhone).
- The PC-side server is off by default; a human turns it on. No autostart.
- Client side is a native iOS **Shortcuts** automation — nothing installed
  from the App Store.

## 2. Build order (do not skip steps or reorder)

1. **Core backup engine** (`server/storage.py`, `server/manifest_db.py`) —
   pure filesystem + SQLite logic, no network yet. Get this fully unit
   tested before writing any HTTP layer. The rules that matter:
   - Same filename + same sha256 → no-op.
   - Same filename + different sha256 → keep BOTH, timestamp-suffix the
     new one, never overwrite.
   - Organize as `<dest>/<YYYY>/<MM>/<filename>` from a `taken_at` ISO
     date string (fallback to server "now" if missing/unparseable).
   - The index (SQLite) lives **inside** the destination folder itself
     (`<dest>/.iphone_backup_index/index.sqlite`), not in the app's own
     config directory. This is what makes a destination self-contained and
     portable across drives/PCs.
2. **Multi-profile identity layer** (`server/profiles.py`) — before writing
   any HTTP auth. A `Profile` has: id, name, slug, token, enabled,
   destination_dir, destination_history (volume label/serial/free-space
   snapshots — see `server/diskinfo.py`, Windows-only via ctypes
   `GetVolumeInformationW`). Persisted to `config/profiles.json`
   (gitignored — it holds secrets). **Destination is per-profile, not a
   single shared root** — this was a deliberate correction after initially
   building a shared-destination-with-subfolders design; the user's real
   use case (multiple people, each with their own USB) needs full
   independence per profile, including the ability for one profile's drive
   to be unplugged without affecting any other profile.
3. **HTTP API** (`server/app.py`, FastAPI). See section 4 for the exact
   contract — it looks simple but every field shape here was chosen to
   work around a real iOS Shortcuts limitation (section 5).
4. **GUI** (`gui/main_window.py`, CustomTkinter, PunkBackup dark theme;
   `gui/i18n.py` for translations, `gui/dialogs.py` for the custom dark
   dialogs replacing the native `messagebox`, `gui/autostart.py` for the
   Windows-launch-at-login registry toggle) — a custom nav bar (not
   `CTkTabview` — its tab identity is tied to its display text, which
   breaks live language switching) toggles two screens: "Principal"
   (server on/off + profile status + connection info + activity log,
   visible by default, also persisted to
   `%APPDATA%\PunkBackup\logs\activity.log`) and "⚙ Configuración" (a
   language switch, ES/EN, applied instantly via `gui/i18n.py`'s
   `t(key, lang)` — every translatable widget is stored as a `self.xxx`
   attribute so `_apply_language()` can reconfigure its text in place —
   then a **Preferences** section: start-with-Windows, auto-start-backup,
   and a configurable idle-timeout with an explicit Save button, same
   card/switch visual language as a profile row — then full profile
   CRUD below that). Two independent controls, not one: a server-wide
   on/off switch, and a per-profile Activo/Pausado switch — because the
   server has no notion of "the active profile"; any number of enabled
   profiles can upload concurrently, each isolated to its own folder.
   Verify this with a real concurrent-upload test (two threads, two
   profiles, two temp dirs) — it's the core guarantee the multi-profile
   design exists to provide.
5. **iOS Shortcut** — build and test on a real device. Do not assume any
   Shortcuts UI behavior without verifying on-device; see section 5.
6. **Desktop shortcut, Firewall rule, docs, tests, packaging** — last.

## 3. Non-negotiable design invariants

- **The destination folder is the only source of truth for "already backed
  up."** Never let the phone decide this on its own (e.g. via a Photos
  album marker) — a phone-side marker breaks the moment the user points a
  profile at a different/new destination (different USB), because the
  phone has no way to know the new destination is empty. The original
  design used a "Respaldado" Photos album as a pre-filter; it was removed
  entirely after the user caught this exact bug. The lightweight `/check`
  endpoint (section 4) exists specifically to let the *server* answer "do
  you already have this" against the *current* destination, every time.
- **`/upload`'s hash check is the final authority**, even though `/check`
  is a cheaper, looser pre-filter (filename+date path existence only, no
  content comparison — see section 5 for why). This two-tier design trades
  a little precision in the cheap check for something Shortcuts can
  actually send, while `/upload` still guarantees no silent overwrite.
- **Never autostart.** The server is 100% off when Windows boots. A Desktop
  shortcut launches the GUI on demand; the user clicks "Iniciar backup"
  to actually start listening. This was an explicit, repeated user
  requirement — don't "helpfully" add a startup task or a tray-autostart
  option.
- **Never touch the phone.** No delete, no move, no write back to Photos
  beyond what the user's own Shortcut does (nothing, in the current
  design — no album marker at all anymore).
- **The optional second-copy (mirror, `server/mirror.py`) can never affect
  the iPhone-facing path.** It's a GUI-triggered, PC-side-only copy — no
  HTTP dependency, no import from `server/app.py`. If the second USB
  fails catastrophically mid-sync, the primary backup from the phone must
  keep working exactly as if the mirror didn't exist. This is also why
  `sync_mirror()` is designed to never raise (every failure mode comes
  back as a field on its result instead, see PLAN.md section 13 and
  lesson 15 below) — a background-thread exception escaping a GUI
  callback is a silent-failure shape this project has hit and fixed
  repeatedly (see lesson 11, PLAN.md section 5.13).

## 4. HTTP API contract

All endpoints except `/health` require header `X-Backup-Token`, resolved to
a `Profile` server-side. Unknown token → 401. Valid token but
`profile.enabled == False` → 403. No `destination_dir` set for that profile
→ 409 on any endpoint needing the engine.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/health` | — | No auth. `{"status":"ok","configured":bool,"profiles":int}` |
| POST | `/run/start` | — | Returns `{"run_id": "...", "profile": "..."}` |
| POST | `/check` | Form: `filename`, `taken_at` | **No `size_bytes`** — see section 5. Returns `{}` if already backed up, `{"missing": true}` if not. **Presence-of-key, not a JSON boolean** — see section 5 for why. |
| POST | `/upload` | **Raw POST body = the file bytes.** Query params: `filename`, `taken_at`, `run_id` | **Not multipart form-data** — see section 5 for why. Returns `{"status": "new"\|"skipped_duplicate"\|"conflict_kept_both", "dest_path": "..."}`. |
| POST | `/run/finish` | Form: `run_id` | Returns the run's counters: `files_new`, `files_skipped`, `files_conflict`, `files_error`. |
| GET | `/status` | — | Per-profile: `state`, `last_backup_at`, `total_files_backed_up`, `last_run`. |

`/upload`'s `filename` and `taken_at` are treated as best-effort hints,
not guarantees: if `filename` has no extension at all, the server sniffs
the real format from the file's own byte signature (JPEG/PNG/GIF/MOV/MP4/
HEIC) and appends it — never overriding an extension that IS present. If
`taken_at` is empty, the server tries reading EXIF `DateTimeOriginal`
straight from the file (JPEG/HEIC only) before falling back to "now".
Both cover the same real, narrow class of Photos items that Shortcuts
sometimes can't report these attributes for — see `server/storage.py`'s
`_detect_extension()`/`_read_exif_taken_at()` and PLAN.md §5.4.
Separately, every successfully-received video (`.mov`/`.mp4`/`.m4v`) with
a known `taken_at` gets its own embedded container metadata
(`creation_time` in `mvhd`/every `mdhd`) patched to match — see
`server/video_metadata.py` and PLAN.md §5.11.

`server/app.py`'s `configure(profile_store)` / `is_configured()` /
`_engine_for(profile)` / `forget_profile(id)` pattern: engines are built
lazily per-profile and cached; **any code that changes
`profile.destination_dir` must call `forget_profile(id)` right after**, or
the cached engine keeps writing to the old folder.

## 5. Hard-won iOS Shortcuts lessons (read before building the Shortcut)

These cost real debugging time against a physical device. Each one changed
the API contract above — don't revert the API to something "cleaner" that
reintroduces these problems.

1. **A Photos item inserted into a multipart Form field's "File" type value
   does not carry raw bytes.** Tapping the inserted "Repeat Item" chip a
   second time (to pick a sub-property) is the only way Shortcuts exposes
   for that slot, and it forces a choice among named attributes (Name,
   Album, Width, Height, File Size, ...) — none of which is "the raw file
   content," and the default selection ("Name") silently sends a **string**
   as the value. The server sees `Expected UploadFile, received: <class
   'str'>`. There is no way found to leave it as "the whole item" once
   you've tapped into that submenu — not even by deselecting. **Fix**:
   don't use multipart Form for the file at all. Send it as the raw POST
   body (`Request Body: File` in Shortcuts) with metadata as URL query
   parameters instead. This is also the pattern most third-party
   Shortcuts-to-API tutorials use, for the same reason.
2. **Shortcuts' "File Size" property is always locale-formatted** (e.g.
   `"1,2 MB"`, comma decimal separator depending on region) — there is no
   "give me a plain integer byte count" option in the attribute picker.
   Do not design any endpoint that needs a `size_bytes: int` from the
   Shortcut directly form a Photos item's File Size attribute; FastAPI's
   `int` parsing will 422 on the formatted string. `/check` was
   redesigned to not need a size at all — filename+date path existence is
   good enough for a cheap pre-filter, with `/upload`'s hash check as the
   real authority.
3. **`Get Dictionary Value` results don't support boolean equality
   reliably.** An "If" action against a raw JSON boolean only offers
   `has any value` / `does not have any value` as comparison operators in
   practice — not `is true` / `is false`. Design API responses around
   **presence/absence of a key**, not a boolean value, when the result
   feeds an "If" in Shortcuts: `/check` returns `{}` (key absent → "does
   not have any value" → already backed up) or `{"missing": true}` (key
   present → "has any value" → upload it).
4. **The `X-Backup-Token` (or any) header value is easy to leave as the
   literal typed word instead of the variable chip**, especially when a
   user configures the same header in 3-4 different actions by hand —
   watch for this specifically if auth errors appear after any manual
   Shortcut edit; check every header row, not just the first one found
   broken.
5. **"Find Photos" with a fixed `Limit` and no advancing cursor always
   returns the same N items**, sorted however you specified — there is no
   built-in pagination. Removing the `Limit` entirely to backfill a large
   library does NOT work either — confirmed on a real device: `Find Photos`
   with no `Limit` fails outright, even doing nothing but counting results
   (no per-item processing at all). A `Limit` is mandatory, not optional.

   **Solved** with a backward block-sweep, entirely inside one Shortcut
   execution: an outer `Repeat` loop advances a `Limite` (Date) variable
   backward from "tomorrow", 50 items at a time (`Find Photos` filtered
   `Date Taken is before Limite`, `Latest First`, `Limit 50`), updating
   `Limite` to the oldest item's date (minus a 1-minute safety buffer, for
   same-timestamp burst photos at a block boundary) after each block, and
   stopping (`Stop This Shortcut`) once a block comes back empty. See
   `shortcuts/SHORTCUT_INSTRUCTIONS.md` for the full build and PLAN.md §5.1
   for the design rationale.

   An earlier design cursor based on `MAX(taken_at)` already backed up
   (server-side, forward-advancing) was tried and rejected: `Date Taken` is
   **not monotonic** with library growth — a photo forwarded via WhatsApp
   or downloaded from Google Photos can enter the library today carrying an
   EXIF capture date from years ago, and a forward cursor would skip it
   forever once past that date. Confirmed on a real device with an actual
   photo (family photo from 2018, downloaded via Google Photos, which
   preserves real EXIF — unlike WhatsApp, which strips it and makes every
   WhatsApp-saved item's `Date Taken` = today, a safe case for date
   cursors). The block-sweep design sidesteps this: it examines the full
   library within one run rather than trusting any date as a permanent
   boundary, so there's no forward-only blind spot — deliberately NOT a
   Photos album marker either (that's exactly the anti-pattern invariant 1
   forbids), and no server endpoint needed for it at all (the boundary is
   computed entirely from `Find Photos` results on-device).

   Remaining known gap: the server can't distinguish "upload never arrived"
   from "genuinely empty file" from a 0-byte POST body alone — it rejects
   both the same way (see points 11-12 below). This is a deliberate, safe
   trade-off (never silently recording a broken backup), not a missed edge
   case.

   **Open finding (2026-09-21, unconfirmed root cause)**: "already backed
   up, skip" is NOT near-instant in practice, contrary to what you'd
   expect from a `/check`-only round trip with zero file transfer.
   Measured from real `activity.log` timestamps (consecutive "already
   backed up" lines): median ~20.5s per skip (n=26, noisy — up to several
   minutes). This means a re-sweep of blocks that are mostly already
   backed up (e.g. resuming an interrupted large backfill) can take
   *longer* wall-clock time than uploading the same number of brand-new
   items, not less — the opposite of what earlier guidance in this file
   and PLAN.md §5.1 assumed. Root cause not yet isolated: candidates are
   per-action overhead inherent to the Shortcuts app itself (each `Get
   Contents of URL` action has its own fixed latency, independent of
   payload size — plausible given point 2's confirmed `File Size` oddity
   is in the same family of "Shortcuts actions aren't free/instant"
   surprises), or `Find Photos` itself re-scanning the whole library on
   every block as `Limite` moves further back. See PLAN.md §5.12 for the
   full measurement and the user-facing writeup in the Troubleshooting
   Manual's "How fast is a backup, really?" section.
6. **A stray filter can silently attach to "Find Photos"** (e.g. filtering
   against an unrelated variable like a `run_id`) if a filter row gets
   added by accident while configuring the action — always visually
   verify with a screenshot that no filter is present when none is wanted;
   it fails silently (0 results, no error).
7. **`pythonw.exe` (no console) makes `sys.stdout`/`sys.stderr` be `None`.**
   uvicorn's default logging setup calls `sys.stdout.isatty()`
   unconditionally and crashes with `AttributeError` — invisible to the
   user since there's no console to show it. Fixed two ways: pass
   `log_config=None` to `uvicorn.Config(...)` (skip uvicorn's own logging
   setup), and replace `sys.stdout`/`sys.stderr` with `io.StringIO()` in
   `main.py` if they're `None`, before any other import that might assume
   a real stream.
8. **Any uncaught exception in a Tkinter callback is silently swallowed
   under `pythonw.exe`** (no console to print the traceback to) — override
   `Tk.report_callback_exception` to show a `messagebox.showerror` with the
   full traceback, and wrap risky top-level handlers (like the
   start/stop-server button) in their own try/except that does the same.
   This was essential to actually diagnosing bug #7 — the user could only
   report the real error once this was in place.
9. **A magic-variable chip's bound attribute (Name/Date Taken/File
   Extension/...) can silently change when you edit a NEARBY action in the
   same loop** — not just the chip you're actively working on. Confirmed
   real instances: the `/upload` `File` field's chip losing its raw-item
   binding, and — months later — the `Format Date` action building
   `TakenAt` getting silently reconfigured from "Date Taken" to "Name"
   right after the `UltimaFecha`-capture step (point 5's block-sweep) was
   inserted just above it in the same "Repeat" block. Both broke with
   zero visible error in the editor; the second one wasn't caught for
   ~2000 uploads because the server dutifully accepted the empty date and
   fell back to "now" (see `BackupEngine._year_month_dir`), silently
   misfiling everything into the current month instead of failing loudly.
   **Any chip whose bound attribute matters (not just "the raw item")
   deserves a periodic sanity check** — after any edit to a loop, not just
   the action you touched — and server-side, prefer surfacing a
   suspicious-default loudly (e.g. log or reject an empty/fallback value)
   over silently "doing something reasonable," since that's what let this
   one run undetected so long.
10. **A one-off script that writes to `index.sqlite` while the app might be
    running needs real retry logic around every `commit()`, not just
    `connect(timeout=...)`/`PRAGMA busy_timeout`.** The GUI polls
    `ManifestDB.get_status()` every 1.5s (`main_window.py`'s
    `_refresh_status_loop`) for as long as it's open, and the destination
    folder is commonly a slow external USB drive — the two combined
    produced sustained `database is locked` errors that outlasted a 30-60s
    `busy_timeout` more than once. Retry `commit()` specifically (~10
    attempts, several seconds apart) **on the same open connection** — do
    NOT open a fresh connection per retry attempt; an early version of a
    maintenance script did that, and each failed attempt left its own
    connection dangling with an uncommitted (still-locked) transaction,
    which piled up and self-deadlocked far worse than the original
    contention. Also order disk-vs-DB operations so a crash mid-retry
    never leaves the DB pointing at a file that no longer exists (e.g.
    delete the DB row and commit it BEFORE deleting the file on disk, not
    after). Simplest real fix when available: just ask the user to close
    the GUI app for the duration of the script.
11. **A non-2xx HTTP response silently aborts the REST of that loop
    iteration in Shortcuts — but the outer loop keeps going to the next
    item.** Confirmed on a real device: `/upload` returning `422` for a
    rejected 0-byte video caused every subsequent action in that same
    iteration (the retry logic in point 12 below) to simply never run,
    with no visible error — 7 videos in a row failed at the exact same
    point across a live sweep that still kept processing hundreds of
    other items normally. The SAME mechanism, independently, caused the
    project's oldest unsolved bug: the final run summary showing blank
    numbers since day one, because `/run/finish` was rejecting a
    malformed request (a missing required `run_id` form field) and
    everything after that call in section 5 of the Shortcut silently
    never executed. **Design rule this forces**: any endpoint whose
    result needs to be inspected or acted on by LATER actions in the
    same Shortcut iteration must return HTTP 200 even when reporting a
    logical failure, with the failure encoded in the body instead (same
    idiom as `/check`'s presence-of-key `missing` field, point 3 above)
    — never rely on a non-2xx status code being something the Shortcut
    can react to, only on whether it stops silently.
12. **Videos (not photos) sometimes arrive as a genuinely empty 0-byte
    body — `Content-Length: 0` on the wire from the very start, not a
    network drop mid-transfer.** Confirmed via a temporary header-dump
    (`Content-Length`/`Content-Type`/`User-Agent`) that a real failing
    upload had `content_type=None`, meaning Shortcuts never actually
    attached real file data at all. Tried and ruled out: "Save File"
    (fails identically for imported AND camera-native videos, to any
    destination including local "On My iPhone" — not an iCloud-sync
    issue), a `Wait` before upload (rules out "still processing"), no
    `Limit`/pagination cause. **What works**: an **Encode Media** action
    (search "Encode", NOT "Convert Video" — that action doesn't exist)
    with **Size: Passthrough** forces Shortcuts to actually read the
    full asset data, and its output uploads successfully where the raw
    `Repeat Item` didn't. Confirmed via `ffprobe` this is a true remux,
    not a re-encode — identical codec/resolution/framerate/bitrate/frame
    count against the real original file; only stream order and one
    metadata tag differ (0.002% file size difference). **Don't apply
    this to every item** — camera-native videos upload fine directly and
    Encode Media costs real time/battery; wire it as a conditional retry
    instead (upload the raw item first, check the response for an error
    per point 11's pattern, only THEN Encode Media + retry). Quick Look
    previews of raw/converted video items are NOT a trustworthy pass/
    fail signal during this kind of debugging (showed blank/"No Items"
    inconsistently, including for items later proven to have real data)
    — always verify via the real server response or its DB, never an
    on-device preview.

    **Downstream consequence, found later (real user report via
    PhotoPrism)**: Encode Media's Passthrough remux also stamps the
    container's OWN `creation_time` metadata (in `moov/mvhd` and every
    `moov/trak/mdia/mdhd`) with the moment of the re-encode — not the
    real capture date — even though PunkBackup's `taken_at` (captured
    independently before Encode Media ever runs) stays correct the whole
    time for folder placement and the DB. External tools that trust the
    file's own embedded date (PhotoPrism, Finder, etc.) show the wrong
    ("today") date as a result. Fixed server-side, not Shortcut-side, in
    keeping with this project's general preference (see point 11's
    "prefer surfacing/fixing on the server" pattern and PLAN.md §5.4's
    extension/EXIF fix): `server/video_metadata.py` patches those exact
    fields back to the real `taken_at` via direct ISO-BMFF box editing —
    a pure-Python, dependency-free, surgical in-place patch (no resize,
    no re-encode) — rather than bundling `ffmpeg` just for a metadata
    rewrite. See PLAN.md §5.11 for the full validation (byte-level diff
    proof against a real device file) before trusting this kind of fix
    on real backup data.

13. **A "download this file from the repo" instruction in a manual is not
    a real distribution path for a non-technical user**, even when the
    file is already committed and public — a usability audit (2026-09-21)
    found `shortcuts/PunkBackup.shortcut` had been referenced in both
    iPhone setup manuals for months as a "faster alternative" with no
    actual download link anywhere, and wasn't attached to the GitHub
    release either (only `PunkBackupSetup.exe` was). Fixed by
    `gh release upload vX.Y.Z shortcuts/PunkBackup.shortcut` and linking
    the evergreen `https://github.com/<repo>/releases/latest/download/
    PunkBackup.shortcut` URL directly in the manual — **this evergreen
    link requires the file to be re-uploaded to every future release**
    (there's no "carry over from last release" default); forgetting it
    makes that link 404 silently for every reader until caught. Also
    found in the same audit: iOS's "Allow Untrusted Shortcuts" gate
    (Settings → Shortcuts → Advanced) is a real, common blocker when
    importing a `.shortcut` file from outside the built-in gallery, and
    is easy to forget to document since it never comes up when *you're*
    the one testing (you already flipped that switch on your own device
    ages ago).

14. **A destination drive filling up mid-write (`OSError`/`ENOSPC`) used to
    propagate as a raw, unhandled exception in `/upload`** — found by code
    review (2026-09-21), not a user report. Same category of bug as point
    11 (non-2xx silently aborts the Shortcut's loop), just a different
    trigger: nothing in this codebase pre-computes "is there enough total
    space for the whole library" before starting (correct — the system is
    supposed to try file-by-file and only fail on the one that genuinely
    doesn't fit), but the actual failure at that point wasn't caught, so it
    surfaced as a bare 500 instead of the established always-200-with-
    `detail` pattern. Fixed in both `server/app.py`'s `/upload` (the real
    iPhone-facing path) and `server/storage.py`'s `process_upload`/
    `stage_bytes` (the path the test suite drives directly) — catch
    `OSError` specifically, clean up the partial staging file, never record
    it as backed up (so `/check` keeps it "missing" for an automatic retry
    once space is freed). **Fully testable without a real device**:
    `monkeypatch` a real (not fake) file object whose `write()` raises
    `OSError(28, "No space left on device")` — lets the file genuinely
    exist on disk first, so the cleanup path gets exercised for real, not
    just skipped because a mock never touched the filesystem. Confirmed
    both new tests actually catch the bug (failed against the pre-fix code,
    passed after) before trusting them — see PLAN.md §5.13.

15. **CustomTkinter (`gui/`) has its own set of gotchas, found building the
    second-copy feature (2026-09-21), that don't fit the Shortcuts/server
    sections above but matter just as much for anyone extending this GUI:**

    - **A `CTkButton` with a colored `fg_color` but no explicit
      `text_color` silently falls back to CustomTkinter's own default text
      color — which does NOT reliably contrast against this app's brand
      colors** (`ACCENT` pink, `RED`). This app already has the correct
      fix defined (`ACCENT_INK = "#1a0308"` for text on `ACCENT`,
      `TEXT_MAIN` for text on `RED` — used correctly on the main
      Start/Stop button and in `gui/dialogs.py`'s primary buttons since
      day one) but **6 other buttons across `gui/main_window.py`** (some
      pre-dating this feature: "Choose folder...", "Delete",
      "+ Add profile"; some new: the mirror Sync/Stop button in both its
      states) were built without ever passing `text_color`, and nobody
      noticed until a real screenshot showed barely-readable text. There
      is no lint/test that catches this — a `CTkButton(..., fg_color=X)`
      call without `text_color` is syntactically fine and silently wrong.
      **When adding any new colored button, always pass `text_color`
      explicitly** (`ACCENT_INK` on `ACCENT`, `TEXT_MAIN` on `RED`/`GREEN`
      unless the specific shade calls for the opposite — check by eye).
    - **`CTkButton.configure(fg_color=X)` without `text_color` does NOT
      reset `text_color`** — it stays whatever it was set to at
      construction (confirmed directly against CustomTkinter). This means
      a button that DID set `text_color` once, at construction, is safe to
      `.configure()` repeatedly afterward without repeating it (see
      `save_btn` in `SettingNumberRow`) — the bug above only affects
      buttons that never set it in the first place, not ones that stop
      repeating it in later `.configure()` calls.
    - **A modal `_PunkDialog` (`gui/dialogs.py`) can crash if a second one
      gets shown immediately after the first is dismissed.** Confirmed
      live: `_on_mirror_sync_done` showed two `show_warning(...)` calls
      back to back for the same event (space warning + stopped-with-error,
      both true at once) and hit `TypeError:
      _PunkDialog.__init__.<locals>.<lambda>() missing 1 required
      positional argument: '_e'` — the `<Escape>` key binding
      (`lambda _e: self._cancel()`) got invoked with zero arguments by
      something in that dismiss/show sequence. **Fixed with a default**
      (`lambda _e=None: ...`, same defensive pattern `ask_input`'s
      `_confirm`/`_cancel` already used) — but the deeper lesson is:
      **never show two of these modal dialogs back to back for the same
      logical event; consolidate into one message (`elif`, not two
      separate `if`s).** Both the bug and the redundant double-popup UX
      go away together.
    - **A progress counter that resets to "1" on a resumed/incremental
      operation looks like data was lost, even when it wasn't.** The
      mirror's `sync_mirror()` originally reported progress as `i` of
      `len(pending)` — technically correct for *that run*, but showing
      "1/6885" right after 128 files were already safely copied and
      verified looked, to a real user watching it, exactly like starting
      over from zero. Fixed by reporting progress cumulatively against the
      operation's real total (`baseline + i` of `baseline + len(pending)`,
      where `baseline` = what was already there) — a UI/UX lesson as much
      as a technical one: **when an operation can resume, its progress
      display must never contradict "nothing was lost."**
    - **`_PunkDialog`'s message-box height, estimated only from literal
      `"\n"` characters in the message, left a long single-paragraph
      warning (zero explicit newlines, the shape of every `warn_*` dialog
      added in AGENTS.md lessons 26/27) clipped behind a scrollbar
      instead of showing its 2-3 word-wrapped visual lines.** Confirmed
      via a real screenshot (2026-09-24): the estimate computed
      `line_count = message.count("\n") + 1` — always 1 for these
      messages — giving a ~44px box for text that actually wrapped to 2-3
      lines at the dialog's fixed width. **First fix attempt (v1.7.16)
      shipped, then caused a real production freeze the same day and had
      to be reverted**: it measured the REAL wrapped line count via the
      raw `tkinter.Text` widget CTkTextbox wraps internally
      (`ctk_textbox._textbox`) and its Tcl-level `count(start, end,
      "displaylines")` — confirmed that this genuinely needs a FULL
      `self.update()`, not `update_idletasks()` (idletasks alone leaves
      the textbox's on-screen width unresolved at a placeholder
      `winfo_width() == 1`, so `displaylines` returns nonsense — measured
      ~98 "lines" for text that only wraps to 2). The user reported the
      whole app frozen shortly after this shipped: no button responded,
      no dialog was visible, yet the process still answered Windows'
      "are you responding" ping and used near-zero CPU — consistent with
      a `_PunkDialog` stuck construction never reaching
      `_show_modal()`'s `deiconify()`/`grab_set()`, i.e. an invisible
      window nonetheless in the way. **Root cause: a full `self.update()`
      pumps Tk's ENTIRE event queue re-entrantly, including whatever
      other callback (the ~1.5s background-status `self.after(...)` tick,
      another queued click, …) happens to be pending at that exact
      instant** — safe in isolated manual testing (nothing else was ever
      pending then), unsafe in the always-something-scheduled reality of
      a running app. **Final fix**: dropped the live Tk measurement
      entirely in favor of `_estimate_display_lines()`, a pure-Python
      `textwrap.wrap()`-based estimate tuned against this app's real
      `warn_*`/`err_*` strings — zero Tk calls, so it cannot re-enter the
      event loop and cannot hang, at the cost of being a rough estimate
      (worst case: a little unused blank space in the box) rather than
      pixel-perfect. Verified safe two ways before shipping: (1) an
      isolated smoke test wrapped in a hard `timeout` guard, so a hang
      would be caught by the test itself rather than trusted to "look
      fine"; (2) a deliberately adversarial stress test — three dialogs
      back to back with near-instant (<5ms) automated clicks — which DID
      turn up a real but unrelated, low-severity CustomTkinter-internal
      quirk (below) and, crucially, did NOT reproduce any hang, which a
      human could never trigger anyway (no real click lands in <5ms).
      **General lesson: a full `update()`/`update_idletasks()` call
      inside any callback that itself might be running from within
      another Tk callback is a real re-entrancy hazard, not just a
      performance concern — prefer a measurement or estimate that
      touches zero live UI state over one that requires pumping the
      event loop, even when the live measurement is more accurate.**
    - **Found while stress-testing the fix above, NOT the cause of the
      freeze, no fix needed**: CustomTkinter's own internal Windows
      dark-titlebar workaround (`CTkToplevel._windows_set_titlebar_color`
      → `self.withdraw()` then `self.after(5,
      _revert_withdraw_after_windows_set_titlebar_color)`) throws
      `_tkinter.TclError: bad window path name` if the dialog is
      destroyed within that internal 5ms window — reproduced with
      automated `.invoke()` clicks fired in a tight polling loop, NOT
      reproduced at all with a human-realistic ~400ms delay before
      clicking. Left alone: no real user closes a dialog in under 5
      milliseconds, so this is a latent quirk in a third-party library,
      not a practical bug — recorded here so a future "why did this
      exact traceback appear once in a log" question doesn't restart the
      investigation from zero.
    - **Destroying a transient, grabbed `Toplevel` while its owner window
      is maximized ("zoomed") can silently drop the owner back to
      "normal" size the instant the dialog closes** — a Windows/Tk
      quirk, confirmed live (2026-09-24) via a direct before/after
      `root.state()` check around a real dialog's `wait_window()`
      returning. Nothing in this codebase ever asks for this; it's a
      side effect of the OS returning focus to the owner once the modal
      grab ends. **Fixed** with `_capture_zoom(parent)` /
      `_restore_zoom(parent, was_zoomed)` in `gui/dialogs.py`, called
      immediately before/after every dialog's `wait_window()` (both
      `_PunkDialog._show_modal()` and `ask_input()`, since `ask_input`
      builds its own raw `CTkToplevel` outside the `_PunkDialog` class
      hierarchy and has the exact same modal-grab shape) — re-asserts
      `"zoomed"` ONLY if the owner really was zoomed before AND the OS
      actually changed it, confirmed by a direct smoke test that a window
      the user had deliberately left un-maximized before opening a
      dialog stays un-maximized afterward (never forces a maximize that
      wasn't there to begin with).

      **Addendum, found the very next day (2026-09-24, v1.7.18)**:
      `_capture_zoom`/`_restore_zoom` above only protects a dialog shown
      AFTER the window is genuinely already zoomed — it does nothing for
      one shown WHILE the window is still in the process of becoming
      zoomed. `MainWindow.__init__` sets `"zoomed"` via a deferred
      `self.after(10, _maximize)` (synchronous `state("zoomed")` during
      `__init__` does nothing — the OS hasn't mapped the window yet), and
      the "Iniciar backup al abrir el programa" preference used to call
      `_toggle_server()` synchronously, back in `__init__`, i.e.
      BEFORE that 10ms callback could ever run. If no destination was
      configured yet, this showed a warning dialog whose
      `_capture_zoom()` correctly saw "not zoomed yet" (true, at that
      exact instant) — but the deferred maximize then fired WHILE the
      dialog's `wait_window()` was still pumping events, zooming the
      window while the modal dialog stayed open. The dialog's own close
      then hit the very quirk `_restore_zoom` exists to fix, except
      `_restore_zoom` never intervened, since it only saw the
      pre-maximize "not zoomed" snapshot. **Confirmed with the real
      `MainWindow` class, not a simplified reproduction**: an early,
      simplified Tk-only repro script consistently did NOT reproduce
      the bug (the timing happened to land differently with far fewer
      widgets being constructed), which nearly led to shipping the wrong
      conclusion — only a faithful repro (the actual `MainWindow`, an
      isolated temp `%APPDATA%`, `auto_start_backup=True`, zero
      profiles) reproduced it reliably, and — via `git stash` on just
      the one-line ordering fix — reproduced a genuine hang against the
      pre-fix code for the exact same script, confirming the repro
      actually exercises the real bug rather than coincidentally passing.
      **Fixed** by moving the `_toggle_server()` call to run FROM WITHIN
      `_maximize()` itself, strictly after `state("zoomed")` — auto-start
      can now never show a dialog before the window is genuinely
      maximized, which isn't a timing coincidence but a structural
      guarantee (same callback, same synchronous sequence). **General
      lesson: when two independent deferred/async operations both touch
      the same piece of window state (one sets it, one reacts to it), a
      fix that "usually works" because of typical timing is not a fix —
      make the ordering structurally guaranteed (one triggers the other
      directly) rather than relying on two independently-scheduled
      callbacks racing in the right order.**

16. **`ManifestDB`'s dangling-run reap (see point 10, and AGENTS.md §6's
    "ad-hoc read-only status checks" lesson) can fire on a run that is
    genuinely, currently in progress — not just a leftover from a crashed
    previous process — if a SECOND `ManifestDB` gets opened on the same
    `dest_root` from within the SAME still-running app process.** Found
    live (2026-09-22): `gui/main_window.py::_sync_profile_mirror` opens
    its own `ManifestDB(primary_root)` to read the primary destination's
    index for the copy list — while the phone's own `/run/start` had
    genuinely just begun uploading, 11 seconds earlier, through the
    server's own separately-cached engine (`server/app.py::_engine_for`).
    The reap logic's core assumption ("a run still open must be from a
    previous process lifetime, since `RunID` never survives past one
    Shortcut execution") is only true for the FIRST `ManifestDB` opened on
    a given `dest_root` per process — a second one, opened later in the
    same process, has no way to tell "genuinely still running" apart from
    "orphaned by a crash." The reap closed the live run's `finished_at`
    early; the actual `/upload` calls kept landing files correctly
    regardless (nothing in `bump_run`/`record_file` checks `finished_at`),
    but the GUI's "still in progress" indicator vanished, making a real,
    still-working backup look stalled. **Fixed**: `ManifestDB.__init__`
    gained `reap_dangling_runs: bool = True` — pass `False` for any
    ManifestDB opened purely to *read* a destination that another part of
    the running app might already be actively writing to. Test:
    `test_reap_dangling_runs_false_never_touches_a_genuinely_live_run`.
    **When adding any new code path that opens a `ManifestDB` on a
    destination folder the server might also have open, ask first: could
    a real run be genuinely in progress right now? If yes, pass
    `reap_dangling_runs=False`.**

17. **Any periodic per-profile check (like `_check_idle_backups`) must
    explicitly skip disabled/not-yet-configured profiles up front, not
    rely on catching the exception they'd otherwise raise.** A disabled
    or destination-less profile always fails `get_status_for_profile`
    (403/409) — that's correct and expected, not a bug, but treating it
    as a caught-exception case still logged a full traceback once per app
    restart for something that's a completely normal state. Filter these
    out with a plain `if not profile.enabled or not profile.destination_dir:
    continue` before the exception-prone call, rather than only
    softening how the exception gets logged afterward.

18. **When two files "should be the same content" but a container format
    lets an intermediate step re-stamp arbitrary metadata, compare the
    actual payload — never try to enumerate and mask every metadata field
    that might change.** Point 12's Encode Media retry doesn't just touch
    `mvhd`/`mdhd` `creation_time` (already known and patched by
    `video_metadata.py::fix_creation_time`) — real-world duplicate copies
    (2026-09-22, 54 copies of one video, 2.46GB wasted) proved it rewrites
    more of `moov` than that. A first fix attempt that hashed the whole
    file with just those two known fields zeroed out was verified against
    the real duplicates and still produced 55 distinct "signatures" for
    55 byte-for-byte-the-same-content files — enumerating fields is a losing
    game against a black-box encoder. The fix that actually worked
    (verified: 1 signature for all 55 real files) was to stop trying to
    identify what metadata changes and instead hash only the `mdat` box —
    the actual audio/video sample data, which passthrough re-encoding
    never touches. See `server/video_metadata.py::content_signature()` and
    PLAN.md §5.4.1. **General lesson: when "same content, different
    wrapper" needs detecting, look for the part of the format that's
    guaranteed stable (the payload) rather than the part that's
    guaranteed to vary (the metadata) — masking the latter is fragile even
    when a docstring says it's been "confirmed."**

19. **After editing code that a PyInstaller `--onedir` build already
    packaged, the installed `.exe` still runs the OLD code until you
    rebuild AND reinstall — an edit + a live phone test is not evidence
    the fix works.** Cost real debugging time (2026-09-22): a fix was
    committed, then "tested live" against the already-open, already-built
    app from earlier that session — it reproduced the exact bug the fix
    was supposed to solve, because the running `.exe` predated the commit
    by over an hour. Confirmed by comparing `Program Files\PunkBackup\
    PunkBackup.exe`'s mtime against the source files' mtime. **Before
    declaring any server/GUI code fix "confirmed working" against the
    installed app, check the installed `.exe`'s build time against the
    fix's commit/edit time — if the exe is older, rebuild
    (`pyinstaller --onedir ...`) and reinstall
    (`installer/output/PunkBackupSetup.exe`) first.**

20. **A "cheap pre-check" endpoint (`/check`) is only as good as the exact
    string it's asked to match — if a LATER step can change that string
    server-side, the cheap check needs to know about it too, or it lies
    forever.** Found live (2026-09-22): `/check` compares the Shortcut's
    as-sent filename against a path on disk, but the file's actual
    extension often gets appended server-side during `/upload`'s
    content-sniffing (see point 9/PLAN.md §5.4) — a fact `/check` never
    learns, since it's deliberately byte-less. Confirmed directly: `POST
    /check filename=ScreenRecording_09-14-2026` returned `{"missing":
    true}` while `filename=ScreenRecording_09-14-2026.mov` (same item,
    extension included) returned `{}` — for an item like this (no
    extension AND no `taken_at`), `/check` is WRONG about "missing"
    forever, on every single future sweep, even though the file is
    genuinely backed up. For a video in point 12's Encode Media category,
    that means paying the re-encode cost every sweep, not once.
    **Fixed by recording ground truth, not by guessing**:
    `backed_up_files` gained an `original_filename` column (the exact
    as-sent name, captured once, the first time an item is genuinely
    matched/recorded) that `check_exists()` falls back to when the sent
    name has no extension. The naive alternative — matching "any
    extension, same stem" — was considered and rejected: these
    no-`taken_at` items already have zero other distinguishing metadata,
    so two genuinely different items that happen to share a base name
    (plausible for unsuffixed screen recordings) would silently merge,
    and the second one would never get backed up. An exact match against
    a name that was verifiably sent and processed before has no such
    risk. Rows that predate this column self-heal the next time they're
    re-encountered (one more unavoidable round-trip, then never again) —
    no migration script needed, same self-healing philosophy as the
    0-byte retry (point 12) and the reap logic (point 16).

21. **This project's activity log has TWO independent formatting paths —
    a real `logging` pipeline (server-side messages) and a hand-rolled
    one (`gui/main_window.py::_log_local`, GUI-only messages like
    "Servidor iniciado") — that both feed the SAME on-screen panel and
    the SAME `activity.log` file. Adding a new field to "every log line"
    means finding and updating BOTH paths, not just the obvious one.**
    Confirmed when adding per-profile attribution (2026-09-22): the real
    fix touches `logging.LoggerAdapter(logger, {"profile": ...})` on
    `ManifestDB`/`BackupEngine` (each instance already knows its own
    profile — reuse that instead of threading a new parameter through
    every individual `logger.info(...)` call site) AND `_log_local`'s
    queue payload (changed from a bare string to a `(profile, message)`
    tuple) AND `_drain_log_queue`'s three-way dispatch (real `LogRecord`
    vs. tuple vs. legacy plain string — `getattr(record, "profile", "-")`
    for the first, so any record from a call site that's missed falls
    back safely instead of crashing) AND the file handler's `Formatter`
    string. Missing any one of these four spots would silently produce
    inconsistent log lines (some tagged, some not) rather than an error —
    the kind of bug that's easy to miss without deliberately checking
    both a server-triggered line AND a GUI-triggered line side by side.

22. **Tkinter (and CustomTkinter) is single-threaded — ANY blocking call
    made from an `after()`-scheduled callback stalls the ENTIRE window,
    not just the widget being updated**, including reacting to a click,
    switching between this app's own screens, and even Windows' own
    "repaint this window" message when the user alt-tabs into it. This
    project's periodic ~1.5s refresh loops (`_refresh_status_loop`,
    `_idle_check_loop`) used to call `app_module.get_status_for_profile()`
    (a real SQLite query) and `get_mirror_status()` (`shutil.disk_usage()`
    + another SQLite query) directly, per profile, per tick — all on the
    main thread. Confirmed as the cause of a real, reported ~10-second
    freeze switching to/from this app's window (2026-09-22): once a
    second profile's destination and a first profile's mirror destination
    ended up sharing the same physical USB drive, several synchronous
    disk touches to that one drive, back to back, every 1.5s, were enough
    to stall the whole GUI whenever the drive had any latency at all — not
    just the specific label being refreshed, the entire window, because
    Tkinter has nothing else to process events with while the Python call
    is running. **Fixed** by moving every actual disk/SQLite call into one
    plain module-level function (`_compute_status_snapshot`, deliberately
    NOT a `MainWindow` method — makes it obvious by construction that it
    never touches a Tk widget, since Tk widgets are not thread-safe to
    touch from a background thread) run on a background thread via
    `_poll_tick`; the result comes back to the main thread via
    `self.after(0, ...)` as a plain dict, and every widget-refresh
    function (`_refresh_principal_profiles`, `_refresh_settings_profiles`,
    `_refresh_aggregate_stats`, `_check_idle_backups`) now reads from that
    precomputed snapshot instead of fetching anything itself — pure
    in-memory dict lookups and `.configure()` calls, provably no I/O.
    Guard against overlapping polls with a simple `self._poll_in_flight`
    flag (never start a second background poll while one is still
    running). **When adding ANY new periodic GUI refresh that needs data
    from disk, a database, or the network: compute it on a background
    thread and hand back only the already-computed result — never call
    something that can block inside an `after()` callback itself.** Fully
    unit-testable without any Tkinter dependency at all, since the
    snapshot function is pure: see `tests/test_gui_status_poller.py`.

23. **SQLite's per-write `commit()` is a real `fsync` to physical media,
    not a cheap bookkeeping call — on USB flash it can dominate total
    time even when the actual file I/O it's protecting is fast.**
    Measured directly (2026-09-23, instrumenting `server/mirror.py`'s
    sync loop with per-step timers, on real pending production files,
    with the app fully closed to rule out contention as a confound):
    copying a file took a median 205ms, hashing it to verify took a
    median 1ms (never the bottleneck — pure CPU, no disk touch at all),
    and **committing its one-row database record took a median 4,856ms
    — 81% of total per-file time** — for files a few hundred KB to a few
    MB in size, where none of that time should plausibly be about the
    number of bytes involved. **Fixed** by giving `ManifestDB.record_file()`
    an optional `commit: bool = True` param and a separate explicit
    `commit()` method, so a caller with many inserts in a row (only
    `server/mirror.py::sync_mirror()` so far — the real iPhone-facing
    upload path keeps its default per-file commit, unchanged, since batching
    it wasn't asked for and has different risk/benefit characteristics)
    can defer the expensive part until `COMMIT_BATCH_SIZE` (25) files have
    accumulated, plus an unconditional flush in a `finally` block so an
    interruption never leaves more than one batch's worth of
    already-verified work uncommitted. **Validated end-to-end against 30
    real pending production files with the app closed: 960ms/file
    average, a 4-5x real speedup**, with the copy and hash-verify steps
    completely untouched — same strictness, same protection against USB
    write corruption, only the commit *cadence* changed. Safe specifically
    because this project's manifest DB is already designed to be
    self-healing: a row that never got committed (crash, power loss)
    simply isn't in the index next time it's opened, so the file just
    gets harmlessly re-copied and re-verified — never silently
    mis-recorded, never a data-loss risk, the same tolerance already
    relied on for the 0-byte retry (point 12) and the reap logic
    (point 16). **A more elaborate alternative was considered and
    deliberately not built**: copying into a staging folder via
    independent worker threads, verifying in batches, then moving
    verified files into place. It would have worked, but it targets the
    COPY step (only 18.8% of measured time) rather than the commit
    (81.2%), and adds real new complexity (thread coordination, a
    staging-to-final move step, tracking which staged files are verified)
    for a smaller win than the much simpler commit-batching fix already
    captures. **When a "batch of many small operations" is slow, measure
    which SPECIFIC step is slow before reaching for concurrency — a
    single sequential fix to the actual bottleneck can outperform a much
    more complex parallel design that speeds up the wrong step.**

    **Addendum, same day, found testing the fix above in real production
    conditions**: a progress callback that reports the LOOP INDEX (every
    attempt) instead of a genuine success count is actively misleading
    whenever failures are possible — confirmed live: under real drive
    contention, a sync attempted 83 files and succeeded on exactly 0 of
    them, yet the on-screen counter climbed the whole time, indistinguishable
    from a healthy sync, because it was reporting `i` (the loop index)
    instead of `result.copied` (real successes). Cost real debugging time
    (comparing the mirror folder's actual file count against the DB
    against the on-screen number) before the mismatch was even noticed.
    **Any progress indicator over an operation where individual items can
    fail must report the count of confirmed successes, not attempts** —
    and pairing it with a live failure count (`⚠ N failed`, shown only
    when nonzero) turns "is this actually working?" from a forensic
    investigation into something visible at a glance.

24. **If a file's hash gets recorded, then something ELSE modifies that
    same file's bytes afterward, the recorded hash is now permanently
    wrong — even though nothing about the recording step itself was
    buggy.** Found the same day as point 23, initially misdiagnosed as
    "disk contention" (a 0% mirror-sync success rate looked plausible
    under real concurrent load) until the user pushed back: "it's not
    expected behavior that NO file copies correctly" — correctly refusing
    to accept a plausible-sounding explanation without evidence. Real
    cause: `finalize_upload()` recorded a video's sha256, THEN called
    `_maybe_fix_video_creation_time()` (point 12's in-place `mvhd`/`mdhd`
    patch), which changes real bytes on disk — but the already-recorded
    hash never gets updated to match. Confirmed directly, no mirror
    involved at all: a real video's CURRENT on-disk sha256 didn't match
    its own primary database's stored sha256. 100% reproducible for every
    video with a known `taken_at` (the vast majority) — not flaky, not
    contention, a permanent, silent mismatch baked in at upload time. Had
    zero visible symptom on the primary path (nothing there re-hashes an
    existing file against its own stored value) but made the mirror's
    hash verification fail on every single video. **Fixed by reordering,
    not by re-verifying later**: apply the byte-changing operation FIRST,
    then compute (or recompute) the hash that actually gets recorded —
    never record a hash before every mutation the same upload will still
    perform on that file has happened. Recomputing costs one extra
    read+hash pass, but only for files that were genuinely modified (a
    boolean return from the patch function gates it), so untouched files
    (all photos, videos with no known date) pay nothing extra, and no
    second database write is needed if the corrected hash is threaded
    into the SAME `record_file()` call that was always going to happen.
    **General lesson: any pipeline step that both hashes a file for
    identity AND separately mutates that file's bytes must guarantee the
    hash is computed AFTER the last mutation — if a later refactor adds a
    new byte-changing step, it must go before the hash, not be tacked on
    after.** Confirmed the regression test actually catches this: reverted
    the fix via `git stash`, watched the new test fail with the exact
    mismatch, restored the fix, watched it pass — never trust a new test
    without watching it fail first. **Retroactive fix run the same day**
    against both real production destinations (`ManifestDB.update_sha256`,
    same commit-batching pattern as point 23): 540 videos checked, 529
    corrected, 0 errors — the 11 that needed no correction were exactly
    the 11 mislabeled-HEIC-as-mp4 files from this project's very first
    test batch (point 12's downstream note), which never go through the
    video patch at all, a clean consistency check that the fix targeted
    the right rows.

25. **A retroactive data-correction script that only touches ONE of two
    related databases leaves them mutually inconsistent — and the code
    that reads both may not be prepared for that.** Direct consequence of
    point 24, confirmed live the very next real sync after the retroactive
    fix ran (2026-09-23): correcting the PRIMARY destination's stale video
    hashes without also correcting the MIRROR's own already-recorded copy
    of those same facts left the mirror's `already_have` set stale — a
    file the mirror genuinely already had now looked "still pending"
    (its new primary hash wasn't in the mirror's old hash set), got
    re-copied and re-verified successfully, and then crashed the whole
    sync trying to INSERT a second row at a `dest_path` that already had
    one (`UNIQUE constraint failed`). **Two real fixes, at two different
    levels**: (1) the immediate one-off — re-ran the same retroactive
    correction against the mirror's own database too, confirmed zero
    remaining mismatches between the two before moving on; (2) the
    durable one — `ManifestDB.record_file()` now upserts
    (`INSERT ... ON CONFLICT(dest_path) DO UPDATE`) instead of a plain
    INSERT, since a collision on `dest_path` specifically can never mean
    "two different files disputing one record" — it's one physical
    location with a newer fact to record — so overwriting is always
    correct, never a real conflict to reject. **When a fix touches
    "the same logical fact" stored in more than one place (a primary and
    its mirror, a cache and its source, two replicas), a partial
    correction is often WORSE than no correction — it creates a new kind
    of inconsistency instead of removing the old one.** Also reinforces
    point 17's earlier lesson from the same day: making a database write
    tolerant of "this exact fact may already be recorded" (upsert instead
    of insert-or-die) is generally safer than trying to guarantee it can
    never happen.

26. **An unreachable destination (USB unplugged) used to be completely
    invisible in real-time — no server log line, and the profile card
    showed the exact same "0 files, never backed up" text as a genuine,
    reachable, empty destination.** Found live (2026-09-24): the user
    ran the phone's Shortcut with the destination USB unplugged and
    reported "the app shows nothing, but the Shortcut is still active" —
    plus a follow-up question that turned out to already have a clean
    answer available in the codebase's OWN mirror feature, just not
    applied to the primary destination. Root cause, two independent gaps:
    (1) `_engine_for()`'s `except OSError` branch (the code path that
    already correctly turns a failed `mkdir()` into a `503`) never logged
    anything before raising — so a real Shortcut sweep hammering `/check`/
    `/upload` against a disconnected drive left zero trace in the activity
    log at the moment it actually happened; the only log line that could
    ever appear was a full Python traceback from `_check_idle_backups`'s
    periodic poller, and only the FIRST time it happened after app
    startup (rate-limited to once via its own `error_logged` flag) — so by
    the time the user actually ran the Shortcut minutes or hours later,
    that traceback (if it had fired at all) had already scrolled by with
    no new activity to explain what was happening right now. (2) The
    profile card's stats text (`_profile_stats_text`) only ever received
    a `status` dict or `None` — a `None` from "genuinely never backed up"
    and a `None` from "currently unreachable" were indistinguishable, so
    both rendered the identical "Total: 0 files | Last: never" line.
    **Fixed by extending an already-correct pattern to the primary path,
    not inventing a new one**: `get_mirror_status()` already returns a
    clean `None` for "not connected" that the GUI already renders as a
    distinct `mirror_not_connected` message — the primary destination just
    never got the equivalent treatment. (a) `_engine_for`'s `except OSError`
    now calls `_warn_destination_unreachable()`, which logs one clear line
    via the SAME `"backup_engine"` logger `BackupEngine`/`ManifestDB`
    already use (so it reaches the GUI's live activity panel for free,
    same as every other server-side event), rate-limited to once per 60s
    per profile (`_UNREACHABLE_WARN_COOLDOWN`) via a small
    `_state["unreachable_warned"]: dict[profile_id, float]` timestamp map
    — cleared the moment that profile's `mkdir()` next succeeds, so a
    disconnect → reconnect → disconnect cycle inside one cooldown window
    still warns immediately on the second disconnect rather than staying
    wrongly silent. (b) `_compute_status_snapshot` now catches
    `HTTPException` specifically and checks `status_code == 503` to set a
    new `entry["destination_unreachable"]` flag, kept distinct from
    `status_error` (any OTHER, genuinely unexpected exception still gets
    the full traceback treatment, unchanged) — `_profile_stats_text` then
    renders a dedicated `stats_dest_not_connected` line ("⚠ USB no
    conectada: {path}") instead of the normal stats block, on BOTH the
    Principal and Settings screens. **Critical distinction that made the
    naive version of this fix wrong at first**: a brand-new profile
    pointed at a destination folder that simply doesn't exist YET on an
    otherwise-reachable drive must NOT be flagged unreachable — `mkdir(
    parents=True, exist_ok=True)` legitimately auto-creates it on the
    first real request, which is correct, existing, load-bearing behavior
    (see `test_snapshot_has_independent_entries_per_profile`'s `dest2`,
    never explicitly created, still works). The fix therefore does NOT do
    a cheap `Path.is_dir()` pre-check (which would have wrongly flagged
    every not-yet-first-used profile) — it lets `_engine_for`'s real
    `mkdir()` attempt run exactly as before and only distinguishes the
    OUTCOME (503 = drive root itself unreachable, e.g. `E:\` doesn't exist
    at all, vs. success = drive reachable, subfolder created fine).
    **When a feature already solved this exact class of problem elsewhere
    in the codebase (mirror's `None`-means-not-connected pattern), check
    for that existing solution and extend it consistently before
    designing a new one from scratch** — the two code paths now agree on
    what "not connected" looks like to the user, instead of the primary
    path inventing its own, worse-communicated version of the same fact.

    **Addendum, found the next day (2026-09-24, v1.7.19)**: the 60-second
    cooldown above was a deliberate design choice, reasoned through and
    documented at the time — but in practice, on a real long-running
    disconnect, it still produced a near-identical log line once a
    minute for as long as the drive stayed unplugged, which the user
    flagged directly from a real screenshot as still too repetitive (four
    almost-identical lines inside a few minutes for one unchanging fact).
    **Changed from a timer-based cooldown to a plain "already warned"
    flag** (`_state["unreachable_warned"]` went from a `{profile_id:
    last_warned_timestamp}` dict to a `set` of profile ids) — logs
    exactly once per disconnect EPISODE, however long that episode lasts,
    and only warns again once the destination has been reachable at
    least once in between (same clearing point as before, `_engine_for`'s
    success path). This also let `_UNREACHABLE_WARN_COOLDOWN` and the
    `time` import it needed be deleted entirely — a simpler mechanism for
    a design the user judged still too noisy, not a more complex one.
    **Lesson: a periodic-reminder design that was reasoned through and
    documented is still worth revisiting once real usage (not the
    reasoning) shows it's noisier than intended — "we thought about this
    already" is not a reason to resist a direct report from actually
    using it.**

27. **A server that binds the port with zero profiles able to receive
    anything used to fail late, per-request, instead of refusing to start
    at all — and there was no clean way to make a stuck Shortcut stop
    without editing the Shortcut itself.** Direct follow-up to lesson 26,
    same day (2026-09-24): the user asked for a way to make an
    already-running Shortcut finish without touching its configuration.
    The real lever turned out to be on the PC side, not the phone —
    a 503 response (lesson 26) still lets Shortcuts' "Get Contents of
    URL" succeed at the network level (it got A response, just an error
    one), so per lesson 11 it silently skips to the next item instead of
    stopping. A connection that's refused outright (nothing listening on
    the port at all) is a different failure class Shortcuts treats as a
    genuine action failure — so the fix was to stop letting the server
    bind the port in the first place when it's pointless to do so.
    **Implemented as an explicit readiness gate in `_start_server()`**
    (`gui/main_window.py`), checked in order, each with its own message
    (both a popup AND a matching activity-log line via the new
    `_block_server_start()` helper, so a refusal is never invisible or
    dialog-only): (1) zero profiles created at all, (2) profiles exist
    but none is enabled, (3) enabled profiles exist but none has a
    destination folder configured. Deliberately does NOT check whether a
    configured destination's drive is CURRENTLY plugged in — that's a
    separate, recoverable runtime state lesson 26 already handles well
    (a profile whose USB is briefly unplugged is still "ready," just
    temporarily unreachable; gating server start on live hardware
    presence would force a restart for something that self-heals on its
    own). On a successful start, one log line per actually-ready profile
    ("Waiting for backup from profile ...") confirms at a glance which
    profiles the server is really listening for, instead of leaving that
    implicit. **Server-side counterpart**: once the server IS listening
    (because some OTHER profile is ready), a request against a profile
    that ISN'T ready — unknown token (401), paused (403), or no
    destination (409) — now also gets ONE log line via
    `_warn_unknown_request()`/`_warn_profile_not_ready()`, but unlike
    lesson 26's 60-second cooldown, this is logged exactly ONCE per
    source (client IP for an unknown token, `profile.id` for a known but
    not-ready one) for the life of the server-listening session, not on
    a repeating timer — a stray/misconfigured device's requests can't
    "become" valid by waiting, so repeating the same fact every minute
    for a whole failed sweep would add nothing lesson 26's cooldown
    doesn't already prove out. **When designing a "log this once" rule,
    match the reset behavior to whether the underlying condition can
    plausibly change on its own**: lesson 26's unreachable-drive case
    can resolve itself any second (someone plugs the USB back in), so it
    warrants periodic reminders; an unknown-token or disabled-profile
    request cannot resolve itself without a human fixing the Shortcut or
    the profile, so one mention per session is enough.

    **Addendum, same day**: the first version of the readiness gate only
    checked whether a destination was *selected* (`destination_dir` set),
    not whether it was actually *usable* right now — so it let the server
    start even when every configured destination's drive was currently
    unplugged (exactly today's live scenario), because "selected" and
    "reachable" got conflated. The user caught this from a real
    screenshot and asked for a 4th tier: refuse to start if NONE of the
    active profiles' destinations can actually be written to. **Then
    caught a second, more fundamental framing mistake before it shipped**:
    the natural first instinct was to call this "is the USB connected"
    (matching lesson 26's vocabulary) — wrong, because a destination
    doesn't have to be a USB drive at all; this project has always
    allowed any folder, including one on an internal drive, which is
    "valid" or not regardless of whether anything is physically plugged
    in. **Fixed by naming and messaging around validity, not hardware
    type**: `_destination_is_valid(path)` — a small, pure, module-level
    function (same testability pattern as `_compute_status_snapshot`,
    deliberately NOT a `MainWindow` method) that attempts the exact same
    `mkdir(parents=True, exist_ok=True)` `_engine_for` already uses
    server-side, so both agree on what "valid" means, including the same
    not-yet-created-but-on-a-writable-location case counting as valid
    (mkdir creates it). The dialog and log text say "no tiene una carpeta
    válida" / "no valid folder", never "USB" or "unidad" — this matters
    because a future reader could otherwise "fix" the wording back to a
    USB-specific phrasing that would be actively wrong for anyone backing
    up to an internal drive or network share. **General lesson: when
    reusing a check from a feature built for one storage type (USB), ask
    whether the check's NAME still holds for every storage type the
    system actually supports before shipping the wording, even if the
    underlying mechanism (a reachability test) is correctly type-agnostic
    already.**

- Unit tests against `BackupEngine`/`ManifestDB` directly (no HTTP) for the
  dedup/conflict/incremental rules — fast, exhaustive.
- `fastapi.testclient.TestClient` end-to-end tests for the real ASGI app,
  including a genuine multi-threaded concurrent-upload test (two profiles,
  `concurrent.futures.ThreadPoolExecutor`) to prove profile isolation under
  real concurrency, not just sequential calls.
- **None of the Shortcuts-specific bugs in section 5 were catchable by
  server-side tests** — they only surfaced building the real Shortcut on a
  real device and reading actual error responses via a temporary
  `Quick Look` action inserted right after the suspect network call. When
  debugging a "the Shortcut ran but nothing happened" report, insert a
  `Quick Look` immediately after the earliest network call in the chain,
  re-run, and work forward one action at a time — this was the single most
  effective debugging technique used throughout this build. Don't
  guess; ask for the raw response.
- **`ManifestDB(dest_root)` is not safe for a read-only ad-hoc status
  check while the real app might be running.** Its `__init__` reaps any
  run still `finished_at IS NULL` (see section 5's stale-run-reap note),
  treating whatever process constructs it as a fresh app launch — so a
  one-off diagnostic script instantiating it against the SAME destination
  the live app is using can prematurely "finish" a run that's still
  genuinely in progress, contaminating the very state you're trying to
  observe (confirmed: this happened during a debugging session, 2026-09-18).
  For any external/one-off inspection of `index.sqlite`, connect directly
  and read-only instead: `sqlite3.connect(f"file:{db_path}?mode=ro",
  uri=True)`.

## 7. What "done" looks like

- `pytest tests -q` passes (91 tests as of this writing, covering engine
  rules, profile isolation/pause/delete, destination-switch correctness,
  concurrent uploads, the `/check` contract, the 0-byte-upload rejection,
  its self-healing retry error-count behavior, a stale-run reap on
  reopen (and its distinct log line vs. a genuine `/run/finish`),
  content-based extension/EXIF-date fallbacks for items Shortcuts sends
  with no extension or no `taken_at`, `ServerController`'s bind
  verification + auto-retry on a transient port conflict, the in-place
  video `creation_time` metadata patch against a synthetic ISO-BMFF
  fixture, the second-copy mirror sync engine — newest-first order,
  hash verification/corruption detection, resumability, cancellation,
  cumulative progress, and the promote-to-primary scenario with no
  reconciliation step needed — and the unreachable-destination warning
  (once-per-cooldown server log line, cleared on reconnect, and the GUI
  snapshot's distinct `destination_unreachable` flag vs. a genuinely
  unexpected `status_error` — the server-start readiness gate plus its
  once-per-session "unknown token"/"profile not ready" log lines, and
  `_destination_is_valid`'s writable-folder check used by that gate's
  4th tier).
- A real iPhone can run the Shortcut manually, and files appear in the
  chosen destination with correct extensions, organized by Year/Month, and
  `<dest>/.iphone_backup_index/index.sqlite`'s `backed_up_files` table
  shows real rows matching what's on disk.
- Re-running the Shortcut with nothing new uploads nothing (idempotent).
- Pausing a profile blocks only that profile; other profiles keep working.
- Pointing a profile at a brand-new empty folder makes everything "missing"
  again for that profile, regardless of what was already backed up
  elsewhere.
