; PunkBackup Windows installer script (Inno Setup).
;
; Packages the PyInstaller --onedir build (dist\PunkBackup\) produced by:
;   pyinstaller --noconfirm --onedir --windowed --name PunkBackup \
;     --icon assets\punkbackup.ico --collect-data customtkinter \
;     --add-data "assets;assets" main.py
;
; Build the PyInstaller output FIRST, then compile this script with:
;   iscc installer\PunkBackup.iss
; Output lands in installer\output\PunkBackupSetup.exe
;
; Requires admin privileges (PrivilegesRequired=admin below) because it writes
; to Program Files and adds a Windows Firewall rule. This means the whole
; installer runs elevated once — the launched app itself is de-elevated back
; to the original user via the "runasoriginaluser" flag on the finish-page
; launch so PunkBackup.exe never runs as admin day-to-day.

#define MyAppName "PunkBackup"
; Keep in sync with APP_VERSION in server/version.py (shown in the app's
; own window title + Settings screen) -- Inno Setup's preprocessor can't
; read that Python file directly, so this has to be bumped by hand too.
#define MyAppVersion "1.7.9"
#define MyAppPublisher "PunkBackup"
#define MyAppURL "https://github.com/hesner/punkbackup"
#define MyAppExeName "PunkBackup.exe"

[Setup]
; Fixed GUID so future versions upgrade in place instead of installing side-by-side.
AppId={{6F1B6B4E-6B3E-4B8A-9B1E-5B6B1E6B6B1E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=output
OutputBaseFilename=PunkBackupSetup
SetupIconFile=..\assets\punkbackup.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "firewall"; Description: "Allow PunkBackup through Windows Firewall (required so your iPhone can reach it over WiFi) / Permitir PunkBackup en el Firewall de Windows (necesario para que el iPhone lo alcance por WiFi)"; GroupDescription: "Network / Red"; Flags: checkedonce

[Files]
Source: "..\dist\PunkBackup\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; PyInstaller 6+ onedir builds put everything except the launcher .exe under
; a _internal\ subfolder (that's also where sys._MEIPASS points at runtime,
; per server/paths.py's app_root()) — the bundled assets/punkbackup.ico
; therefore lives at {app}\_internal\assets\punkbackup.ico, NOT {app}\assets\.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\punkbackup.ico"
; Fixed English name (NOT the localized {cm:UninstallProgram,...} constant):
; that constant's text changes depending on which setup LANGUAGE was picked
; on a given install run, so a later reinstall in a different language
; creates a second, differently-named "Uninstall" shortcut instead of
; replacing the first one — confirmed leaving an orphaned
; "Desinstalar PunkBackup.lnk" alongside "Uninstall PunkBackup.lnk" after
; installing once in Spanish and once in English. A fixed name is
; upgraded in place every time, regardless of setup language.
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\punkbackup.ico"; Tasks: desktopicon

[Run]
; Delete before add, every install run — `netsh ... add rule` has no
; "replace if exists" mode, so re-running the installer (e.g. an update)
; without this kept piling up duplicate identical rules (confirmed: 10
; copies after today's several reinstalls). Harmless functionally (they
; all just Allow), but pure clutter. `delete rule` removes every rule
; matching this name, so it also cleans up any duplicates left over from
; a version before this fix.
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PunkBackup"""; Flags: runhidden; Tasks: firewall
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""PunkBackup"" dir=in action=allow protocol=TCP localport=8787 profile=private"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PunkBackup"""; Flags: runhidden; RunOnceId: "RemovePunkBackupFirewallRule"

[UninstallDelete]
; Explicit, rather than relying on Inno's own "did this install create it"
; tracking for the desktopicon Task — Inno remembers a Task's checked state
; from a previous install of the same AppId and pre-fills the Tasks page
; with it, so a shortcut can exist on disk (created by an earlier run, or
; fixed up by hand) without this install run being the one that put it
; there. Deleting it unconditionally on uninstall avoids ever leaving a
; dangling shortcut that points at a now-removed PunkBackup.exe.
Type: files; Name: "{autodesktop}\{#MyAppName}.lnk"

; Also clean up any leftover *localized* uninstall shortcut from a
; version built before the fixed-English-name fix above (e.g. someone
; who installed in Spanish under an older build still has
; "Desinstalar PunkBackup.lnk" sitting alongside the current one).
Type: files; Name: "{group}\Desinstalar {#MyAppName}.lnk"
Type: files; Name: "{group}\Uninstall {#MyAppName}.lnk"

; The app writes its config/profiles under %APPDATA%\PunkBackup (see server/paths.py).
; Left in place on uninstall by default — it holds each profile's secret tokens and
; destination history, which the user likely wants to keep if they reinstall later.
; Uncomment to also wipe it on uninstall:
; Type: filesandordirs; Name: "{userappdata}\PunkBackup"
