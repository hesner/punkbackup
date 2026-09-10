# PunkBackup — Installation Manual

> **Note on language**: the app's interface is currently **Spanish-only**.
> Screenshots and quoted button text below are in Spanish, with an English
> translation in parentheses the first time each one appears.

## What this system does

Automatically backs up photos and videos from one or more iPhones/iPads to
your Windows PC, over local WiFi, no cable, no iCloud dependency. Each
person/device gets its own profile with its own destination folder.

## Requirements

- **Windows 10 or 11** PC.
- **Internet** connection (only for the initial install).
- The iPhone/iPad and the PC must be able to reach the **same WiFi
  network** at backup time.
- **Administrator** rights on the PC (asked once, for the Firewall rule).

> This version requires a few Terminal (PowerShell) steps to install
> Python. A future double-click installer will remove this requirement.

## Step 1 — Install Python

1. Open **PowerShell** (search it in the Start menu).
2. Run:
   ```
   winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
   ```
3. Wait for it to finish (a few minutes).

## Step 2 — Copy the project to your PC

1. Copy the whole project folder (the one shared with you) to a permanent
   location, e.g. `C:\Backup Photos and Videos`.
2. Open PowerShell **inside that folder** (right-click the folder → "Open
   in Terminal", or navigate there with `cd`).

## Step 3 — Set up the environment

Run these one at a time, inside the project folder:

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Step 4 — Create the Desktop shortcut

Run in PowerShell (adjust the path if you copied the project elsewhere):

```powershell
$projectDir = "C:\Backup Photos and Videos"
$target = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
$script = Join-Path $projectDir "main.py"
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "PunkBackup.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $target
$Shortcut.Arguments = '"' + $script + '"'
$Shortcut.WorkingDirectory = $projectDir
$Shortcut.IconLocation = $target + ",0"
$Shortcut.Save()
```

You should now see a new **"PunkBackup"** icon on your Desktop.

## Step 5 — First launch and Firewall rule

1. Double-click the Desktop icon — the app opens (dark window, two tabs:
   "Principal" (Main) and "Perfiles" (Profiles)).
2. Go to the **"Perfiles"** (Profiles) tab → **"+ Agregar perfil"** (+ Add
   profile) → name your device (e.g. "iPhone de [your name]") → pick the
   folder where you want your photos saved.
3. Go to **"Principal"** (Main) → click **"🤘 Iniciar backup"** (Start backup).
4. The first time, Windows may show a **Firewall** prompt asking to allow
   the connection — accept it, checking at least **"Private networks"**.
5. It should say **"Estado: Escuchando en el puerto 8787"** (Status:
   Listening on port 8787).

## Step 6 — Set up your iPhone

Follow the separate **iPhone Setup Manual** to create the Shortcut and,
optionally, the WiFi automation.

## Is it working?

- Check the Perfiles tab shows your profile with its destination folder.
- Run the Shortcut once on your iPhone as a test.
- Check the folder you chose — you should see Year/Month subfolders with
  your photos inside.

If something's not working, see the **Troubleshooting Manual**.
