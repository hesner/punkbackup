# Uninstallation Manual

Uninstalling this system is safe and **does not delete any of your already
backed-up photos** — only the program itself is removed; your backup
folders (on your disk or USB) stay exactly where they were.

## Step 1 — Stop the server

1. Open the app (Desktop icon) if it isn't open.
2. If it says "Escuchando en el puerto...", click **"Detener backup"**.
3. Close the window.

## Step 2 — Remove the Firewall rule (optional)

Open PowerShell **as administrator** and run:

```powershell
Remove-NetFirewallRule -DisplayName "iPhone WiFi Backup"
```

## Step 3 — Delete the Desktop shortcut

Delete the **"Backup Fotos y Videos"** icon from your Desktop (right-click
→ Delete), like any other shortcut.

## Step 4 — Delete the program folder

Delete the folder where you installed the project (e.g. `C:\Backup Photos
and Videos`). This removes the program, its configuration, and the list of
profiles/tokens — it does **not** touch your already-backed-up photo
folders, which live in a different location (the destination folder you
chose per profile).

## Step 5 — (Optional) Remove the Shortcut from the iPhone

1. On the iPhone, open **Shortcuts**.
2. Long-press the shortcut (e.g. "Backup Fotos y Videos") → **Delete**.
3. If you created a WiFi automation, go to the **Automation** tab →
   long-press it → **Delete**.
4. If you created a "Respaldado" album in an older version of this system
   (no longer needed in the current version), you can delete it from
   Photos → Albums.

## What about my already-backed-up photos?

They stay exactly where they were, in the folder you chose — the system
never moves or modifies them when uninstalled. You can keep using them
normally, or reinstall the system later pointing at that same folder to
pick up where you left off (the internal index lives inside that folder,
so it's recognized automatically).
