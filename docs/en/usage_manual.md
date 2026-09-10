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

---

## "⚙ Settings" → Language

At the very top of Settings there are two buttons: **Español** / **English**.
Tap one and **the whole app switches language instantly** — buttons,
titles, messages, everything — no closing or restarting needed. Your
choice is remembered the next time you open the app.

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
or `Listening on port 8787`.

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
- **Last backup** and **Files**: how many it has backed up so far.
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

**Hidden by default** to keep the screen uncluttered. Expanding it shows a
live, terminal-style (green text) log of each file as it arrives: new,
already existed, or conflict. Useful to confirm something is actually
happening in real time while you run the Shortcut on your iPhone.

---

## "⚙ Settings" → Profiles

Below the language switch is where identities are managed — one per
person or device.

### "+ Add profile"

1. Type a name identifying the device (e.g. `iPhone de Laura`, `iPad de
   Hesner`) — it doesn't need to be technical, it's just so you recognize it.
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
