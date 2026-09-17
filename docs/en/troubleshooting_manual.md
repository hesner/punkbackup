# PunkBackup — Troubleshooting Manual

> This manual shows the app in **English** — go to **"⚙ Settings" →
> "English"** if it isn't already switched (instant, no restart).

## The app closes by itself shortly after opening

**This is Avast** (or a similar antivirus), not a bug in PunkBackup — see
the "⚠ Important: this app is not code-signed" section of the Installation
Manual for why, and the fix (add an exception for the PunkBackup install
folder in Avast, restore it from Quarantine/Virus Chest if it landed
there).

## "Start backup" does nothing / doesn't change state

- Fully close the app (not just minimize it) and reopen it from the
  Desktop icon.
- If it happens again, you should now get an error window with the exact
  detail (instead of failing silently) — send us that text.
- Make sure there isn't another copy of the app already open (check the
  taskbar).

## The iPhone can't reach the server

1. Confirm the iPhone and the PC are on the **same WiFi network** (check
   the exact name in WiFi settings on both — some routers have separate
   2.4GHz/5GHz networks with similar-looking names).
2. From Safari on the iPhone, try opening the address the app shows you
   (e.g. `http://PC-NAME.local:8787/health`). If it doesn't load, try the
   "Fallback IP" the app also shows.
3. Confirm the server is on in the PC app ("Status: Listening on port...").
4. Check the Firewall rule exists: PowerShell (as administrator) →
   `Get-NetFirewallRule -DisplayName "PunkBackup"`. If it's missing (e.g.
   you skipped that checkbox during install), add it with
   `New-NetFirewallRule -DisplayName "PunkBackup" -Direction Inbound
   -Protocol TCP -LocalPort 8787 -Profile Private -Action Allow`.

## 401 error "Missing or invalid X-Backup-Token header"

- The token in the Shortcut doesn't match your profile's token on the PC.
- In the Shortcut, check **every** action with an `X-Backup-Token` header —
  the value must be the `Token` variable **chip** (colored background),
  never the literal word "Token" typed as plain text.
- Copy the token again from the app ("Copy token" button on the profile)
  and paste it into the corresponding **Text** action in the Shortcut.

## 403 error "This profile is paused"

- The profile is **Paused**. Open the app → "Main" or "⚙ Settings" →
  switch it to **Active**.

## 409 error "no destination folder configured"

- That profile has no destination folder. Go to **"⚙ Settings"** →
  "Choose folder..." for that profile.

## The Shortcut runs but doesn't upload any new photo

- Check **"Find Photos"** has no stray filter beyond the `Date Taken is
  before Limite` one described in the iPhone Setup Manual — a different
  filter sneaking in makes it return 0 results silently, with no visible
  error.
- Check **`Limit`** is turned **on** and set to **50** on `Find Photos` —
  this is mandatory (not optional): without it, `Find Photos` fails outright
  on a large library, even doing nothing but counting results.
- Confirm under **iPhone Settings → Privacy & Security → Photos** that the
  Shortcuts app has access ("All Photos" / "Always Allow") — with limited
  access, a photo you just took or saved may simply not be visible to the
  Shortcut yet, with no error shown.

## All new photos are landing in the same folder (the current month)

This happens when the server receives an empty date for each photo, and
`_year_month_dir()` falls back to "right now" — so everything ends up in
the current month's folder regardless of when the photo was actually
taken.

- **Almost always confirmed cause**: the chip inside the **Format Date**
  action (the one that builds the `TakenAt` variable, section 4 of the
  iPhone Setup Manual) got silently reconfigured to point at a different
  attribute (e.g. "Name") instead of **Date Taken**. This usually happens
  with no visible error, right after adding or moving another action
  inside the same "Repeat" block — Shortcuts sometimes silently
  reconfigures neighboring chips.
- **How to confirm it**: inside the Shortcut, open section 4's "Format
  Date" action and tap its chip — it should say **Date Taken**. If it
  says anything else, that's the problem.
- **Fix**: re-select "Date Taken" on that chip. Photos uploaded AFTER
  this fix will land in their correct folder automatically — nothing
  else needs to change for new uploads.
- **Photos already uploaded to the wrong folder** (before the fix) don't
  reorganize themselves — they stay where they landed. If this happened
  to a large number of files, it's a one-off maintenance job (reading the
  real date directly from each file, or forcing a re-send from the
  phone), not something the Shortcut or server fixes automatically.

## My library is huge (thousands of photos) — will the full backup ever finish?

The Shortcut sweeps your library backward in bounded blocks of 50, newest
photos first, advancing automatically block after block within one run —
see the "Set up the backward block-sweep" step of the iPhone Setup Manual.
This is what makes a large library actually finish, instead of either
timing out (no `Limit`) or getting stuck re-checking the same fixed set
forever (a plain `Limit` with no way to advance).

- The number of blocks per run is controlled by the `Repeticiones` variable
  (a `Text` action near the top, defaults to `50`). Confirmed working with
  `Repeticiones` up to 50 (≈2500 photos checked in one run). For your very
  first full backfill of a large library, it's fine to run the Shortcut
  several times in a row rather than pushing `Repeticiones` very high on
  the first try — watch the PC app's activity log (use "⤢ Expand" for a
  bigger view) to see it's keeping up before raising the number.
- **Videos can currently arrive empty (0 bytes) — sometimes consistently,
  not just occasionally.** The server always detects and rejects this
  automatically, so it's never recorded as a real backup and the same
  video is simply retried on a later run instead — but the underlying
  cause (why the iPhone sometimes sends an empty body for a video
  specifically) isn't fully understood yet: it's not iCloud storage
  optimization, not a fixed file-size limit, and it isn't reliably fixed
  by keeping the Shortcuts app in the foreground either — this is an open
  issue, not a solved one. Photos are unaffected (confirmed reliable).
  Keeping the screen on and the Shortcuts app in the foreground during a
  large manual run may still help, and does no harm, but don't count on it
  fixing every case.
- If a run gets interrupted (you leave home, or tap Stop), nothing is lost
  — anything already uploaded stays backed up permanently. The next run
  just starts sweeping from your newest photos again rather than exactly
  where it left off; the already-completed blocks re-check quickly (no
  file transfer) before it reaches new ground.
- If the Shortcut itself appears to freeze with no error and no visible
  cause (rare, but a known Shortcuts app quirk unrelated to this system),
  force-quit it from the app switcher and run it again — nothing gets
  corrupted by an interrupted run, see the point above.

## The phone freezes while the Shortcut runs

- Go to **iPhone Settings → Display & Brightness → Auto-Lock → Never**
  (temporarily, while running a large backup).
- Runs with thousands of photos can take several minutes — that's normal,
  not a freeze.
- If it truly stops responding: a forced restart of the iPhone is safe,
  nothing is lost (the server-side run is just left unfinished, harmlessly).

## The Shortcut's final notification shows blank numbers (New/Already had/Conflicts)

**This never affects the actual backup** — files keep uploading and
saving correctly even when the notification comes back blank. If it
happens, check the **"Get Contents of URL"** action pointing at
`/run/finish` (section 5 of the iPhone Setup Manual):

- The `X-Backup-Token` header must be under **Headers**, not inside
  **Request Body → Form**.
- **Request Body → Form** needs a `run_id` field set to the `RunID`
  variable — without it, the server rejects the request and the rest of
  that section (reading the counters, building the message) gets
  silently skipped, leaving the summary blank.

To confirm something was really saved while you check, look at the
destination folder directly (see next section).

## How to check files are really being saved

No technical steps needed: open the destination folder you chose in
Windows Explorer — you should see Year/Month subfolders with your photos
and videos inside.

## Still not working

Contact whoever helped you install the system, or check the project's
GitHub repository to report the issue.
