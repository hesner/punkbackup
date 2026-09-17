# PunkBackup — Installation Manual

> This manual shows the app in **English**. It opens in Spanish by
> default the very first time — go to **"⚙ Settings" → "English"** and
> everything switches instantly (no restart). Your choice is remembered
> after that.

## What this system does

Automatically backs up photos and videos from one or more iPhones/iPads to
your Windows PC, over local WiFi, no cable, no iCloud dependency. Each
person/device gets its own profile with its own destination folder.

## ⚠ Important: this app is not code-signed

PunkBackup is a small independent project — the `.exe` is **not** digitally
signed with a paid code-signing certificate (those cost money; see the
project's notes on this if you're curious why). This has two real, expected
consequences:

- **Windows SmartScreen** will warn you once at install time (see Step 2).
  This is normal and harmless — click through it as described below.
- **Your antivirus may go further than a warning.** Antivirus products use
  heuristics (behavior patterns), not just known-virus lists, and an
  unsigned new program that talks to the network can trip those heuristics
  — even though PunkBackup only talks to your own iPhone on your own WiFi
  and never sends anything anywhere else. **Avast in particular has been
  observed silently closing PunkBackup shortly after it opens**, with no
  error message from the app itself (it just vanishes). If that happens to
  you, it's Avast, not a bug in PunkBackup — see the fix below.

You can read the full source code yourself (this is an open-source project)
if you want to verify exactly what it does before trusting it.

### Fixing "Avast keeps closing the app"

1. Open **Avast** → **Menu → Quarantine** (or "Virus Chest") — if
   `PunkBackup.exe` is listed there, restore it and add an exception so it
   doesn't get grabbed again.
2. Or: **Avast → Menu → Settings → General → Exceptions** → add the
   install folder (default `C:\Program Files\PunkBackup\`) so Avast skips
   scanning/blocking it entirely.
3. Reopen PunkBackup from the Desktop icon — it should now stay open.

This is the same fix for other antivirus products that behave this way
(Windows Defender, Norton, etc.) — add an exception for the PunkBackup
install folder.

## Requirements

- **Windows 10 or 11** PC.
- **Internet** connection (only to download the installer).
- The iPhone/iPad and the PC must be able to reach the **same WiFi
  network** at backup time.
- **Administrator** rights on the PC (asked once, during install — to
  copy the program and add the Firewall rule).

## Step 1 — Download the installer

Download `PunkBackupSetup.exe` from the project's release page:

**https://github.com/hesner/punkbackup/releases/latest**

## Step 2 — Run the installer

1. Double-click `PunkBackupSetup.exe`.
2. Windows may show a **SmartScreen** warning ("Windows protected your PC")
   since this is a new program without a paid code-signing certificate —
   click **"More info"** → **"Run anyway"**.
3. Accept the **User Account Control (UAC)** prompt — the installer needs
   admin rights to copy the program into `Program Files` and to add the
   Firewall rule.
4. If your antivirus scans the file (e.g. Avast, "Suspicious file
   detected" / reputation scan), that's normal for a brand-new installer —
   let it finish, it shouldn't find anything.
5. Follow the wizard:
   - Pick the setup language (this does **not** set the app's language —
     the app has its own ES/EN switch in "⚙ Settings").
   - Keep **"Create a desktop icon"** checked to get the Desktop shortcut.
   - Keep the **Firewall rule** task checked (recommended — if you skip
     it, you'll need to add it manually later for your iPhone to connect).
   - Click **Install** and wait for it to finish.
6. At the end, leave "Launch PunkBackup" checked and click **Finish** —
   the app opens on its own.

## Step 3 — First launch

1. The app opens (dark window, two screens: "Main" and "⚙ Settings"),
   in Spanish by default — switch it to English per the note at the top
   of this manual, if you haven't already.
2. Go to **"⚙ Settings"** → click **"+ Add profile"** → name your device
   (e.g. "iPhone de [your name]") → pick the folder where you want your
   photos saved.
3. Go to **"Main"** → click **"🤘 Start backup"**.
4. If you didn't check the Firewall task during install, Windows may show
   the prompt here instead asking to allow the connection — accept it,
   checking at least **"Private networks"**.
5. It should say **"Status: Listening on port 8787 🤘"**.

## Step 4 — Set up your iPhone

Follow the separate **iPhone Setup Manual** to create the Shortcut and,
optionally, the WiFi automation.

## Is it working?

- Check **"⚙ Settings"** shows your profile with its destination folder.
- Run the Shortcut once on your iPhone as a test.
- Check the folder you chose — you should see Year/Month subfolders with
  your photos inside.

If something's not working, see the **Troubleshooting Manual**.
