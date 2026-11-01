<img src="assets/punkbackup.png" alt="PunkBackup" width="120" />

# PunkBackup 🤘

**Tus recuerdos. Tu USB. Cero dependencia de la nube.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d6.svg)](https://github.com/hesner/punkbackup/releases/latest)
[![Client: iOS Shortcuts](https://img.shields.io/badge/iOS%20client-Shortcuts%20app-black.svg)](shortcuts/SHORTCUT_INSTRUCTIONS.md)

**[🌐 punkbackup.com](https://punkbackup.com)**

A one-directional (iPhone/iPad → PC) photo and video backup system over
local WiFi, with an optional USB cable mode for a first or very large backup.
No iCloud, no subscription, no Docker, no NAS — just a Windows PC, a USB drive,
and your iPhone's built-in Shortcuts app.
Multiple people/devices, each with their own profile and their own
destination drive.

## Why

Cloud photo backups are convenient and also: a recurring bill, someone
else's server, and a company that can change the terms whenever it wants.
Self-hosted photo servers like Immich or PhotoPrism solve the cloud part,
but trade it for a different chore — Docker, a reverse proxy, a NAS or a
server that has to stay on 24/7. PunkBackup skips both: it copies your
files to a drive you own, over a network you control or a USB cable, using
nothing but your iPhone's built-in Shortcuts app and a small Python server on your own
PC that only listens when you tell it to.

**PunkBackup isn't trying to replace your photo gallery app** — it doesn't
do face recognition, albums, or sharing. It does one thing: get every
photo and video off your iPhone and onto a drive you physically own,
incrementally, without ever touching or deleting anything on the phone.
If you want a full self-hosted Google Photos replacement, Immich or
PhotoPrism do more than this ever will — PunkBackup is for when you just
want the boring backup part, with nothing else to configure or maintain.

|  | **PunkBackup** | Immich / PhotoPrism | PhotoSync | iCloud / Google Photos |
|---|---|---|---|---|
| Server runs | Only when you turn it on | 24/7 (Docker/NAS) | — (device-to-device) | Someone else's, always |
| Setup | One `.exe` + one iOS Shortcut | Docker + reverse proxy + storage | App Store app | Just sign in |
| Your files live on | A USB drive you own | A disk/NAS you own | Flexible (local, cloud, NAS) | Their cloud |
| Cost | Free, open source | Free, open source | Paid app | Subscription past the free tier |
| Good for | "Just back up my iPhone, nothing fancy" | A full photo library: search, AI, sharing | Flexible power-user sync without self-hosting | Zero setup, don't mind the lock-in |

## How it works

1. A small program runs on your Windows PC. Its WiFi server listens when you start
   it, or when you open the app if you turn that option on. Backup by cable is also
   available for fast, bulk copies.
2. Each person/device gets a **profile**: its own secret token, its own
   destination folder (can be a different USB drive per person).
3. A native iOS **Shortcut** (no App Store install) checks your Photos
   library against what's actually in your current destination folder, and
   uploads whatever's missing — manually, or automatically when you
   connect to your home WiFi.
4. Nothing is ever deleted, moved, or modified on the iPhone. Nothing is
   ever silently overwritten at the destination — a genuine name+content
   conflict keeps both files.
5. Optionally, each profile can also keep a **second copy** on a
   different drive — a manual, verified, one-way sync, so your photos
   don't live on only one piece of hardware.

6. For a first backup or a large volume, **backup by cable** reads the iPhone
   over USB with no network and no server, using the same destination and rules.
   Cable and WiFi recognize each other's files by content, even under different
   names, so you can use both. Run the Shortcut afterward: the cable only sees what
   the iPhone shows over USB.

See [`PLAN.md`](PLAN.md) for the full architecture and design decisions, and
[`AGENTS.md`](AGENTS.md) if you're an AI agent (or a human) rebuilding or
extending this from scratch — it documents several non-obvious iOS
Shortcuts limitations that shaped the API, so you don't have to rediscover
them the hard way.

## Getting started

**[⬇ Download PunkBackupSetup.exe](https://github.com/hesner/punkbackup/releases/latest)** — Windows 10/11, no Python required. Run it, accept the one admin prompt (Program Files + Firewall rule), done.

> ⚠ **Not code-signed.** This is an independent open-source project without
> a paid code-signing certificate, so Windows SmartScreen will warn you once
> at install, and some antivirus software (Avast in particular) may flag or
> even close the app on heuristics alone. Both are expected — see the
> Installation Manual's "not code-signed" section for the one-time fix.
> Read the source yourself if you want to verify what it does first.

- [Installation Manual (PDF, EN)](docs/pdf/PunkBackup%20-%20Installation%20Manual%20(EN).pdf) · [Manual de instalación (PDF, ES)](<docs/pdf/PunkBackup - Manual de Instalacion (ES).pdf>)
- [Usage Manual (PDF, EN)](<docs/pdf/PunkBackup - Usage Manual (EN).pdf>) · [Manual de uso (PDF, ES)](<docs/pdf/PunkBackup - Manual de Uso (ES).pdf>)
- [iPhone Setup Manual (PDF, EN)](<docs/pdf/PunkBackup - iPhone Setup Manual (EN).pdf>) · [Configuración del iPhone (PDF, ES)](<docs/pdf/PunkBackup - Configuracion del iPhone (ES).pdf>)
  - Prefer to build the Shortcut by hand instead of importing the file? [Manual Build guide (PDF, EN)](<docs/pdf/PunkBackup - iPhone Setup Manual - Manual Build (EN).pdf>) · [Construcción manual (PDF, ES)](<docs/pdf/PunkBackup - Configuracion del iPhone - Construccion Manual (ES).pdf>)
- [Troubleshooting Manual (PDF, EN)](<docs/pdf/PunkBackup - Troubleshooting Manual (EN).pdf>) · [Solución de problemas (PDF, ES)](<docs/pdf/PunkBackup - Manual de Solucion de Problemas (ES).pdf>)
- [Uninstallation Manual (PDF, EN)](<docs/pdf/PunkBackup - Uninstallation Manual (EN).pdf>) · [Desinstalación (PDF, ES)](<docs/pdf/PunkBackup - Manual de Desinstalacion (ES).pdf>)

## Development

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe main.py
```

To try the interface with a simulated iPhone and throwaway data, without touching
real profiles or drives: `.venv\Scripts\python.exe tools\ui_preview.py`

## License

MIT — see [`LICENSE`](LICENSE).
