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
#define MyAppVersion "1.0.0"
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
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\punkbackup.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\punkbackup.ico"; Tasks: desktopicon

[Run]
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""PunkBackup"" dir=in action=allow protocol=TCP localport=8787 profile=private"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PunkBackup"""; Flags: runhidden; RunOnceId: "RemovePunkBackupFirewallRule"

[UninstallDelete]
; The app writes its config/profiles under %APPDATA%\PunkBackup (see server/paths.py).
; Left in place on uninstall by default — it holds each profile's secret tokens and
; destination history, which the user likely wants to keep if they reinstall later.
; Uncomment to also wipe it on uninstall:
; Type: filesandordirs; Name: "{userappdata}\PunkBackup"
