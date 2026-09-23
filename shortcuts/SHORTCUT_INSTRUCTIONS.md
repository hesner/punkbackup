# PunkBackup — iPhone Setup (WiFi Backup Shortcut)

> This manual shows the PC app in **English** — go to **"⚙ Settings" →
> "English"** if it isn't already switched (instant, no restart).

This guide walks you through installing, on your iPhone, the Shortcut that
sends your new photos and videos to your PC over WiFi. It uses the
ready-made Shortcut file — no need to build any action by hand.

> **Prefer to build it yourself, or want to understand what each action
> does?** There's a separate, longer guide for that: the **Manual Build**
> guide (`shortcuts/MANUAL_BUILD_INSTRUCTIONS.md`, also published as its own
> PDF). Nothing here requires it — this is the complete path for almost
> everyone.

## Before you start, have these ready

This system supports several devices/people (profiles) on the same PC.
**Each device needs its own profile and its own token** — so if you're
setting up more than one iPhone/iPad, repeat these steps in the PC app for
each one.

On your PC:
1. Open the app and click **"🤘 Start backup"**.
2. In **"⚙ Settings"**, click **"+ Add profile"** and name it after THIS
   device (e.g. `iPhone de María`), then choose its destination folder
   when prompted.
3. The app shows you (and auto-copies) that profile's **token** — it only
   works for this one device.

Note down these values:

| Value | Where to find it in the app | Example |
|---|---|---|
| Server address (same for every profile) | "Address" field | `http:​/​/​[YOUR_PC_NAME].​local:​8787` |
| Fallback IP (in case the address above doesn't resolve from the iPhone) | "Fallback IP" field | `http:​/​/​192.​168.​1.​50:​8787` |
| This profile's token | "Copy token" button on the profile row you just created | a long string of letters/numbers |

> Your iPhone and your PC must be on the **same WiFi network**.
> If you add another device later, create its own profile — never reuse
> another device's token.

> **Design note**: this shortcut does NOT use any "already backed up" album
> on the iPhone. The decision of what to upload is always made by the
> server, by checking what actually exists in your profile's destination
> folder right now — so if you switch USB drives/destination folders on the
> PC, the system adjusts itself automatically instead of incorrectly
> "remembering" something that never actually made it to that folder.

---

## Step 1 — Install the Shortcut on your iPhone

1. On your **iPhone**, open Safari and go to this address (type it in, or
   have it texted/emailed to yourself so you can tap it directly):

   **[⬇ Download PunkBackup.shortcut](https://github.com/hesner/punkbackup/releases/latest/download/PunkBackup.shortcut)**

   Safari downloads the file and offers to open it in the **Shortcuts**
   app. (If you instead downloaded it on your PC, send it to your iPhone
   first — AirDrop, iCloud Drive, email, whatever you have — then open it
   from there.)

2. **iOS will likely block it at first with a security warning** ("Untrusted
   Shortcut" / "Unable to Add Shortcut"). This is expected — iOS doesn't
   trust shortcut files by default when they don't come from the built-in
   Shortcuts gallery. To allow it, **just this once**:
   - Go to **iPhone Settings → Shortcuts → Advanced**.
   - Turn on **"Allow Untrusted Shortcuts"**.
   - Go back and open the `PunkBackup.shortcut` file again (from the Files
     app, or by re-downloading it) — it should now open normally in
     Shortcuts.
   - This is a one-time setting per iPhone; you won't need to repeat it for
     future updates to this same Shortcut.
3. Tap **"Add Shortcut"**.

## Step 2 — Set your own address and token

The Shortcut arrives wired up correctly except for two placeholder values.
Open it for editing (tap and hold its tile → **Edit**) and change:

- The first **Text** action (currently `http://your-pc.local:8787`) → your
  real **Server address** (from the table above).
- The second **Text** action (currently `TOKEN HERE`) → this profile's real
  **Token** (from the table above).

Save, and you're done building it.

## Step 3 — Test it

1. Tap the `PunkBackup` shortcut once, manually, from the Shortcuts app (or
   your Home Screen if you added it there).
   > **On a brand-new device/profile, you may see**: *"This action is
   > trying to share [N] photos items, which is not allowed. You can allow
   > this in Settings."* This is a separate iOS gate from the "Untrusted
   > Shortcut" one in Step 1 — it shows up specifically when a Shortcut
   > tries to hand off a large batch of items at once, which happens on a
   > brand-new profile because everything still needs to be uploaded for
   > the first time. To allow it, **just this once**:
   > - Go to **iPhone Settings → Shortcuts**.
   > - Turn on **"Allow Sharing Large Amounts of Data"**.
   > - Run the `PunkBackup` shortcut again.
   > - This is also a one-time setting per iPhone/iPad.
2. You should see a notification at the end with counts (New / Already had
   / Conflicts). It's fine if the very first run's numbers show it uploaded
   several files — that's your first backup running.
3. On your PC, open the destination folder you chose for this profile in
   Windows Explorer — you should see Year/Month subfolders with your
   photos and videos landing inside.

If either step doesn't work as described, see the Troubleshooting Manual.

> Optional: there's also a short "Backup Status" shortcut you can build to
> check status without running a full backup — see Step 2 of the **Manual
> Build** guide if you want it (it isn't part of the ready-made file).

---

## Step 4 — Automate it: run on its own when you get home

1. Open **Shortcuts** → **Automation** tab → **+** → **Create Personal Automation**.
2. Choose **Wi-Fi** → select your home network: `[YOUR_WIFI_NETWORK]`.
3. Leave **Connects** checked.
4. Tap **Next** → **Add Action** → search for and choose your `PunkBackup` shortcut.
5. Tap **Next** → **Done**.
6. Important: turn off **"Ask Before Running"** for this automation. The
   first time it runs it may ask for a one-time security confirmation —
   accept it. After that it will run silently every time you join that WiFi.

> You can also run `PunkBackup` manually anytime by tapping it in the
> Shortcuts app, or saying "Hey Siri, PunkBackup".

> ⚠️ **A brief WiFi drop can re-trigger this automation.** Since it's
> set to fire on "Connects," walking somewhere in your house with a weak
> signal and reconnecting counts as a new connection — the automation can
> fire again on top of a backup that's still running (or just got cut
> off). Confirmed on a real device: no photos are lost either way (the
> self-healing design handles it), but you may see a couple of
> overlapping runs in the PC app's activity log after that happens —
> that's expected, not a bug.

---

## Notes
- The system **never deletes or modifies anything on your iPhone** — it
  only reads photos and uploads them.
- The truth about "what's already backed up" lives **only in the PC's
  destination folder**, never on the iPhone. If you switch your profile's
  folder/USB drive on the PC, the shortcut automatically re-sends whatever
  is missing from the new folder — you don't need to do anything different
  on the iPhone.
- Updating later: if this guide's Shortcut file changes in a future
  PunkBackup release, download it again and repeat Steps 1-2 — your
  Server address and Token carry over the same way.
