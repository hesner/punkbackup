# PunkBackup — Installation Manual

> This manual shows the app in **English**. It opens in Spanish by
> default the very first time — go to **"⚙ Settings" → "English"** and
> everything switches instantly (no restart). Your choice is remembered
> after that.

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
   location, e.g. `C:\PunkBackup`.
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
$projectDir = "C:\PunkBackup"
$target = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
$script = Join-Path $projectDir "main.py"
$icon = Join-Path $projectDir "assets\punkbackup.ico"
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "PunkBackup.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $target
$Shortcut.Arguments = '"' + $script + '"'
$Shortcut.WorkingDirectory = $projectDir
$Shortcut.IconLocation = $icon + ",0"
$Shortcut.Save()
```

You should now see a new **"PunkBackup"** icon on your Desktop.

## Step 5 — First launch and Firewall rule

1. Double-click the Desktop icon — the app opens (dark window, two
   screens: "Main" and "⚙ Settings").
2. Go to **"⚙ Settings"** → tap **"English"** at the top (if it isn't
   already selected).
3. Still in **"⚙ Settings"**, click **"+ Add profile"** → name your device
   (e.g. "iPhone de [your name]") → pick the folder where you want your
   photos saved.
4. Go to **"Main"** → click **"🤘 Start backup"**.
5. The first time, Windows may show a **Firewall** prompt asking to allow
   the connection — accept it, checking at least **"Private networks"**.
6. It should say **"Status: Listening on port 8787 🤘"**.

## Step 6 — Set up your iPhone

Follow the separate **iPhone Setup Manual** to create the Shortcut and,
optionally, the WiFi automation.

## Is it working?

- Check **"⚙ Settings"** shows your profile with its destination folder.
- Run the Shortcut once on your iPhone as a test.
- Check the folder you chose — you should see Year/Month subfolders with
  your photos inside.

If something's not working, see the **Troubleshooting Manual**.
