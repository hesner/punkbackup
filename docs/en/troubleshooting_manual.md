# PunkBackup — Troubleshooting Manual

> This manual shows the app in **English** — go to **"⚙ Settings" →
> "English"** if it isn't already switched (instant, no restart).

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
- **Videos can occasionally arrive empty (0 bytes)**, especially when the
  Shortcut runs with the screen locked/app backgrounded (the WiFi
  automation runs this way by design) — the server now detects and rejects
  this automatically, so it's never recorded as a real backup; the same
  video is simply retried on a later run instead. Keeping the screen on and
  the Shortcuts app in the foreground during a large manual run makes this
  much less likely to begin with.
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

Known cosmetic issue — the step that closes out the run (`/run/finish`)
sometimes doesn't complete, so the summary doesn't always carry the
numbers. **This doesn't affect the actual backup**: files still upload and
save correctly. To confirm something was really saved, check the
destination folder directly (see next section).

## How to check files are really being saved

No technical steps needed: open the destination folder you chose in
Windows Explorer — you should see Year/Month subfolders with your photos
and videos inside.

## Still not working

Contact whoever helped you install the system, or check the project's
GitHub repository to report the issue.
