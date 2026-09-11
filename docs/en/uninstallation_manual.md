# PunkBackup — Uninstallation Manual

Uninstalling this system is safe and **does not delete any of your already
backed-up photos** — only the program itself is removed; your backup
folders (on your disk or USB) stay exactly where they were.

## Step 1 — Stop the server (optional)

If the app is open and says "Status: Listening on port...", click
**"Stop backup"** and close the window. Not required — the uninstaller can
close the app for you — but it's tidier to do it by hand first.

## Step 2 — Uninstall from Windows

1. Open **Settings** → **Apps** → **Installed apps** (or search
   "Add or remove programs" in the Start menu).
2. Find **"PunkBackup"** in the list.
3. Click the three dots (or right-click) → **Uninstall**.
4. Accept the **User Account Control (UAC)** prompt.
5. Follow the wizard and click **Finish** when it's done.

This automatically removes:

- The program (`Program Files\PunkBackup`).
- The Desktop and Start Menu shortcuts.
- The Firewall rule added during install.

And **intentionally keeps**:

- Your profiles and tokens (`%APPDATA%\PunkBackup`) — so if you reinstall
  later, you don't have to recreate every profile or re-paste tokens into
  each iPhone's Shortcut.
- Your already-backed-up photo folders (on whichever disk/USB you chose
  per profile) — the uninstaller never touches those.

If you also want to wipe your profiles/tokens, delete the
`%APPDATA%\PunkBackup` folder by hand after uninstalling.

## Step 3 — (Optional) Remove the Shortcut from the iPhone

1. On the iPhone, open **Shortcuts**.
2. Long-press the shortcut (`PunkBackup`) → **Delete**.
3. If you created a WiFi automation, go to the **Automation** tab →
   long-press it → **Delete**.

## What about my already-backed-up photos?

They stay exactly where they were, in the folder you chose — the system
never moves or modifies them when uninstalled. You can keep using them
normally, or reinstall the system later pointing at that same folder to
pick up where you left off (the internal index lives inside that folder,
so it's recognized automatically).
