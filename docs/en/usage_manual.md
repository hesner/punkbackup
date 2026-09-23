# PunkBackup — Desktop App Usage Manual

> This manual shows the app in **English** — go to **"⚙ Settings" →
> "English"** if it isn't already switched. For first-time setup, see the
> **Installation Manual**; for problems, see the **Troubleshooting Manual**.

## The window has 2 screens

- **"Main"**: turn the backup server on/off, see the address your devices
  should connect to, and each profile's status.
- **"⚙ Settings"**: switch the app's language, and create/manage each
  person or device (profiles).

Switch between them with the two buttons at the top, right under the app name.

The window opens **maximized** by default every time — resize/un-maximize it as usual if you'd rather have it smaller; that's a normal Windows window control, not something PunkBackup remembers between launches.

---

## "⚙ Settings" → Language

At the very top of Settings there are two buttons: **Español** / **English**.
Tap one and **the whole app switches language instantly** — buttons,
titles, messages, everything — no closing or restarting needed. Your
choice is remembered the next time you open the app.

In the top-right corner of that same card, and also in the window's
title bar, you'll see which version you have installed (e.g.
"PunkBackup v1.7.3") — useful if you're comparing against this manual or
reporting an issue.

---

## "⚙ Settings" → Preferences

Right below Language, three cards — same on/off switch style as each
profile's Active/Paused switch on the "Main" screen. Every change here
applies immediately, no restart needed.

- **Start PunkBackup with Windows**: adds (or removes) PunkBackup from
  Windows' own startup programs, so it opens automatically when you log
  in — no need to find the Desktop icon every time. **Off by default.**
- **Start backup when opening the app**: as soon as the app finishes
  opening, it automatically does the same thing as clicking
  **"🤘 Start backup"** yourself — including the same warnings if no
  profile is configured yet, or none has a destination folder set. Combine
  this with the switch above for a PC that starts listening for your
  iPhone completely hands-off after a reboot. **Off by default.**
- **Minutes of inactivity before flagging the backup as stopped**: a
  number field (1–30 minutes) controlling the idle-backup notice
  described above under "▼ Show activity". Type a new value and click
  **"Save"** (or press Enter) — the button only lights up while there's
  an unsaved, valid change, and briefly shows "✓ Saved" once it's
  applied, so it's always clear whether your edit actually took effect.
  **5 minutes by default.**

---

## "Main" screen

### "🤘 Start backup" / "Stop backup" button

This is the server's main on/off switch — it controls whether the PC is
**listening** on the network at all.

- **Off** ("Start backup", green): your PC accepts no connections from any
  iPhone/iPad. This is the default — the app never turns itself on, even
  if left open.
- **On** ("Stop backup", red): your PC can now receive photos and videos
  from any **Active** profile.

Right next to it, the **"Status: ..."** text confirms the mode: `Stopped`,
`Starting backup...` (briefly, right after clicking — usually just a
couple seconds, occasionally longer if the port needs a moment to free
up, e.g. right after antivirus software closes and reopens the app), or
`Listening on port 8787`. If starting genuinely fails (the port stays
unavailable), you'll get an error window explaining why instead of a
false "Listening" status.

> You don't need to "select" which profile is backing up — as long as the
> server is on, **any Active profile can upload at any time**, even
> several at once.

### "Server address (same for every profile):"

Two values you'll only need **once**, when setting up each iPhone/iPad's
Shortcut (they don't change per profile):

- **Address**: `http://YOUR-PC-NAME.local:8787` — try this first.
- **Fallback IP**: a numeric backup address, in case the one above doesn't
  resolve from a particular iPhone.

### "Profiles connected to this backup:"

One card per profile you've created, showing:

- **Name** of the profile.
- **Total in destination**: how many files are in that profile's folder
  in total (everything backed up so far, across every run), plus the
  date of the last backup.
- **Last run**: how many files were saved specifically in the Shortcut's
  most recent run (new vs. already had) — if that run is still going,
  it's marked "(in progress...)".
- **Folder**: where it's saving its files.
- **USB**: if its folder is on a removable drive, that drive's label and
  free space.
- An **Active / Paused** switch — see below.

#### The Active / Paused switch

This is different from the big button above. That one turns **the whole
PC** on/off; this switch blocks or allows **one specific profile**,
without touching the others.

- **Active**: that device can upload normally.
- **Paused**: that specific device can't upload anything (the server
  replies "profile paused"), while everyone else keeps working. Useful,
  for example, to cut off a guest's device without deleting its history.

Pausing/reactivating **deletes nothing** — it's fully reversible.

### "Last backup (all profiles) / Total files"

A combined summary across every profile — a glance to see whether anything
backed up recently, without checking each profile individually.

### "▼ Show activity"

**Visible by default** — collapse it with the same button if you want a
cleaner screen. It shows a live, terminal-style (green text) log of each
file as it arrives: new, already existed, or conflict. Useful to confirm
something is actually happening in real time while you run the Shortcut
on your iPhone. It also clearly marks when each run **starts** and
**finishes** (with the final summary: new/already had/conflicts/errors),
so you can see at a glance where each backup begins and ends in the log
history.

Every line is stamped with the **local date and time** it happened
(`DD-MM-YYYY HH:MM:SS`), followed by **which profile/device it's about**
(e.g. `iPhone de Hesner`, `iPad`, or `-` for a line that isn't about any
one profile, like the server starting/stopping) — so with more than one
device backing up, you can tell at a glance which line belongs to which
one, not just guess from the message text. A log that spans several days
(if you leave the app open) still reads clearly either way — you can tell
exactly when each backup ran, not just their order.

If a run stays "in progress" without receiving any new file for a while
(e.g. WiFi dropped, or you closed the Shortcut on the phone mid-backup),
the log shows a notice like `⏸ "[profile]": no activity for 5+ minutes —
the backup looks like it stopped` — once per stretch of inactivity, not
repeated while it stays idle. How many minutes of inactivity count as
"stopped" is configurable — see "⚙ Settings" → Preferences below.

Next to that button is a smaller **"⤢ Expand"** button, which opens the
same log in a separate, larger, resizable window — handy when a long run
generates more text than the small embedded panel comfortably shows.

Every line is also saved to a file on disk
(`%APPDATA%\PunkBackup\logs\activity.log`), so past activity can still be
checked after closing the app — not just what's currently visible on
screen. It rotates daily and automatically deletes anything older than
about 6 months, so it never grows forever.

---

## "⚙ Settings" → Profiles

Below the language switch is where identities are managed — one per
person or device.

### "+ Add profile"

1. Type a name identifying the device (e.g. `iPhone de María`, `iPad de
   Diego`) — it doesn't need to be technical, it's just so you recognize it.
2. The app generates a unique **token** for that profile and copies it to
   your clipboard automatically — you'll paste it into that device's
   Shortcut (see the iPhone Setup Manual).
3. It then asks you to pick that profile's **destination folder** — any
   folder, on your internal disk or an external USB drive.

### Per-profile buttons

| Button | What it does |
|---|---|
| **Choose folder...** | Changes where that profile saves its files (e.g. if you switched USB drives). Files already backed up in the previous folder are NOT moved or deleted. |
| **USB history** | Shows the drives/folders that profile has used before — label, serial number, space — so you can recognize which USB is which even if Windows assigns it a different drive letter. |
| **Copy token** | Copies the token to your clipboard again (in case you need to reconfigure the Shortcut). |
| **Rename** | Changes only the name you see in the app — doesn't affect the token or folder. |
| **Regenerate token** | Generates a new token for that profile. That device's Shortcut stops working until you paste the new token in — only use this if you suspect the token leaked. |
| **Delete** | Revokes that profile's access (its token stops working). **Does not delete any already-backed-up file.** |

### Second copy (optional)

Below the buttons, each profile can have a **second copy** — a copy of
everything on its main destination, kept on a different folder/USB. Not
required, and off by default; it's for anyone who wants their photos on
more than one physical drive.

- **"+ Configure second copy (optional)"** — appears when you haven't set
  one up yet. Tap it, choose a folder (it can't be the same folder as your
  main destination), and you're done configuring it.
- Once configured, you'll see how many files it has and how much free
  space is left on it, plus a **"🔄 Sync now"** button.
- Tapping **"🔄 Sync now"** copies whatever's missing from your main
  destination to the second copy — newest photos first — and verifies
  each one after copying, so a bad USB write gets caught and retried
  automatically instead of silently leaving a broken copy. This never
  runs on its own; you decide when to sync.
- While it's syncing, that same button turns into **"⏹ Stop"** — use it
  if you need to unplug the second drive before a sync finishes. Nothing
  is lost either way: whatever was already copied and verified stays, and
  the next sync picks up exactly where it left off.
- **"Remove"** stops syncing to that folder — it does **not** delete any
  file already copied there.
- If your main drive is ever lost or damaged, this second copy is a real,
  independent backup: just point your profile's main destination at that
  folder (using "Choose folder..." above) and the app recognizes exactly
  what it already has — nothing needs to be re-uploaded from the phone.

---

## Typical daily use

1. Open the app from the Desktop icon.
2. Click **"🤘 Start backup"**.
3. Run the Shortcut on your iPhone (manually, or automatically if you set
   up the WiFi automation).
4. Watch it upload on the "Main" screen (expand "Show activity" for live
   detail).
5. When you're done, you can close the app or leave it — it does nothing
   on its own unless you clicked "Start backup".

## Good practices

- Create one profile per person or device — never share a token between
  two iPhones.
- If you're going to use a different USB for someone, just use "Choose
  folder..." on their profile — no need to create a new one.
- Check "USB history" before plugging in a drive you don't use often, to
  confirm it's the right one.
