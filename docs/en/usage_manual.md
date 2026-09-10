# PunkBackup — Desktop App Usage Manual

> **Note on language**: the app's interface is currently **Spanish-only**.
> Every Spanish label below is followed by its English meaning in
> parentheses the first time it appears.

This guide explains what each screen and button does. For first-time setup,
see the **Installation Manual**; for problems, see the **Troubleshooting
Manual**.

## The window has 2 tabs

- **"Principal"** (Main): turn the backup server on/off, see the address
  your devices should connect to, and each profile's status.
- **"Perfiles"** (Profiles): create, configure, and manage each
  person/device.

---

## "Principal" (Main) tab

### "🤘 Iniciar backup" (Start backup) / "Detener backup" (Stop backup) button

This is the server's main on/off switch — it controls whether the PC is
**listening** on the network at all.

- **Off** ("Iniciar backup", green): your PC accepts no connections from
  any iPhone/iPad. This is the default — the app never turns itself on,
  even if left open.
- **On** ("Detener backup", red): your PC can now receive photos and
  videos from any **Activo** (Active) profile.

Right next to it, the **"Estado: ..."** (Status:) text confirms the mode:
`Detenido` (Stopped), or `Escuchando en el puerto 8787` (Listening on port
8787).

> You don't need to "select" which profile is backing up — as long as the
> server is on, **any Active profile can upload at any time**, even
> several at once.

### "Dirección del servidor" (Server address)

Two values you'll only need **once**, when setting up each iPhone/iPad's
Shortcut (they don't change per profile):

- **Dirección** (Address): `http://YOUR-PC-NAME.local:8787` — try this first.
- **IP alternativa** (Fallback IP): a numeric backup address, in case the
  one above doesn't resolve from a particular iPhone.

### "Perfiles conectados a este backup" (Profiles connected to this backup)

One card per profile you've created, showing:

- **Name** of the profile.
- **Última copia** (Last backup) and **Archivos** (Files): how many it has
  backed up so far.
- **Carpeta** (Folder): where it's saving its files.
- **USB**: if its folder is on a removable drive, that drive's label and
  free space.
- An **Activo / Pausado** (Active / Paused) switch — see below.

#### The Activo / Pausado (Active / Paused) switch

This is different from the big button above. That one turns **the whole
PC** on/off; this switch blocks or allows **one specific profile**,
without touching the others.

- **Activo** (Active): that device can upload normally.
- **Pausado** (Paused): that specific device can't upload anything (the
  server replies "profile paused"), while everyone else keeps working.
  Useful, for example, to cut off a guest's device without deleting its
  history.

Pausing/reactivating **deletes nothing** — it's fully reversible.

### "Última copia (todos los perfiles) / Total archivos" (Last backup, all profiles / Total files)

A combined summary across every profile — a glance to see whether anything
backed up recently, without checking each profile individually.

### "▼ Mostrar actividad" (Show activity)

**Hidden by default** to keep the screen uncluttered. Expanding it shows a
live, terminal-style (green text) log of each file as it arrives: new,
already existed, or conflict. Useful to confirm something is actually
happening in real time while you run the Shortcut on your iPhone.

---

## "Perfiles" (Profiles) tab

This is where identities are managed — one per person or device.

### "+ Agregar perfil" (+ Add profile)

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
| **Elegir carpeta...** (Choose folder...) | Changes where that profile saves its files (e.g. if you switched USB drives). Files already backed up in the previous folder are NOT moved or deleted. |
| **Historial USB** (USB history) | Shows the drives/folders that profile has used before — label, serial number, space — so you can recognize which USB is which even if Windows assigns it a different drive letter. |
| **Copiar token** (Copy token) | Copies the token to your clipboard again (in case you need to reconfigure the Shortcut). |
| **Renombrar** (Rename) | Changes only the name you see in the app — doesn't affect the token or folder. |
| **Renovar token** (Regenerate token) | Generates a new token for that profile. That device's Shortcut stops working until you paste the new token in — only use this if you suspect the token leaked. |
| **Eliminar** (Delete) | Revokes that profile's access (its token stops working). **Does not delete any already-backed-up file.** |

---

## Typical daily use

1. Open the app from the Desktop icon.
2. Click **"🤘 Iniciar backup"**.
3. Run the Shortcut on your iPhone (manually, or automatically if you set
   up the WiFi automation).
4. Watch it upload on the "Principal" tab (expand "Mostrar actividad" for
   live detail).
5. When you're done, you can close the app or leave it — it does nothing
   on its own unless you clicked "Iniciar backup".

## Good practices

- Create one profile per person or device — never share a token between
  two iPhones.
- If you're going to use a different USB for someone, just use "Elegir
  carpeta..." on their profile — no need to create a new one.
- Check "Historial USB" before plugging in a drive you don't use often, to
  confirm it's the right one.
