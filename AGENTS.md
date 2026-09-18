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

## 6. Testing approach that actually caught bugs

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

- `pytest tests -q` passes (35 tests as of this writing, covering engine
  rules, profile isolation/pause/delete, destination-switch correctness,
  concurrent uploads, the `/check` contract, the 0-byte-upload rejection,
  its self-healing retry error-count behavior, a stale-run reap on
  reopen (and its distinct log line vs. a genuine `/run/finish`),
  content-based extension/EXIF-date fallbacks for items Shortcuts sends
  with no extension or no `taken_at`, and `ServerController`'s bind
  verification + auto-retry on a transient port conflict).
- A real iPhone can run the Shortcut manually, and files appear in the
  chosen destination with correct extensions, organized by Year/Month, and
  `<dest>/.iphone_backup_index/index.sqlite`'s `backed_up_files` table
  shows real rows matching what's on disk.
- Re-running the Shortcut with nothing new uploads nothing (idempotent).
- Pausing a profile blocks only that profile; other profiles keep working.
- Pointing a profile at a brand-new empty folder makes everything "missing"
  again for that profile, regardless of what was already backed up
  elsewhere.
