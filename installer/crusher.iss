; Inno Setup script. Built by build.ps1 (or: ISCC.exe installer\crusher.iss)
#define AppName "Crusher"
#define AppVersion "1.0.0"
#define AppExe "Crusher.exe"

[Setup]
AppId={{B7E2C1A4-6F3D-4E8B-9A21-5C0D7F4E8A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=KumaStar
AppPublisherURL=https://github.com/KumaStar/Crusher
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=Crusher-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\crusher.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "contextmenu"; Description: "Add 'Crusher' to the right-click menu for all files"; Flags: checkedonce

[Files]
Source: "..\dist\Crusher\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Same verbs as install_context_menu.ps1, per-user (HKCU), no admin needed
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Crusher"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher"; ValueType: string; ValueName: "SubCommands"; ValueData: ""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher\shell\1crush"; ValueType: string; ValueName: ""; ValueData: "Crush to target size"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher\shell\1crush\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --crush ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher\shell\2open"; ValueType: string; ValueName: ""; ValueData: "Open in Crusher"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Crusher\shell\2open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Crusher"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
