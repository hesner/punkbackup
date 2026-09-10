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
   `Get-NetFirewallRule -DisplayName "iPhone WiFi Backup"`.

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

- Check **"Find Photos"** has no stray filter (it should just say "Find
  Photos" with no extra conditions, only Sort/Order/Limit) — a filter that
  sneaks in by accident makes it return 0 results silently, with no visible
  error.
- If "Find Photos" has a low **Limit** and you've run it several times, it
  may keep checking the same oldest photos over and over — raise the Limit
  to make progress.
- Confirm under **iPhone Settings → Privacy & Security → Photos** that the
  Shortcuts app has access ("All Photos" / "Always Allow").

## My library is huge (thousands of photos) and the full backup fails or freezes

- "Find Photos" with **no limit** scans your entire library at once — with
  very large libraries (thousands of photos) this can take a long time or
  cause iOS to interrupt the Shortcut with a generic error ("There was a
  problem running the shortcut"). This is a **known limitation**, without a
  definitive fix yet.
- In the meantime: use a **moderate Limit** (e.g. 300-500) and run the
  Shortcut several times manually — with a fixed limit it may never reach
  the oldest photos in a very large library, though. For the initial full
  backup of a large library, be patient, disable Auto-Lock and keep the
  phone plugged in, and if it fails, just run it again — the system is
  incremental, so progress already made isn't lost.

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
