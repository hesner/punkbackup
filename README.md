<img src="assets/punkbackup.png" alt="PunkBackup" width="120" />

# PunkBackup 🤘

**Tus recuerdos. Tu USB. Cero dependencia de la nube.**

**[🌐 punkbackup.com](https://punkbackup.com)**

A one-directional (iPhone/iPad → PC) photo and video backup system over
local WiFi. No cable, no iCloud, no subscription. Multiple people/devices,
each with their own profile and their own destination drive.

## Why

Cloud photo backups are convenient and also: a recurring bill, someone
else's server, and a company that can change the terms whenever it wants.
PunkBackup does the boring, useful thing instead — it copies your files to
a drive you own, over a network you control, using nothing but your
iPhone's built-in Shortcuts app and a small Python server on your own PC.

## How it works

1. A small server runs on your Windows PC (off by default — you turn it on
   when you want it).
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

## License

MIT — see [`LICENSE`](LICENSE).
