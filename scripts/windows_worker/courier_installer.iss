; Courier Symphony - Inno Setup Installer Script
; Target: Per-User Clean-Machine Windows Installation (docs/V1_RULE_0.md)
; Requirements: PrivilegesRequired=lowest, local app data persistence, clean uninstall.

#define MyAppName "Courier Symphony"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Courier Symphony Team"
#define MyAppURL "https://couriersymphony.de"
#define MyAppExeName "Courier.exe"

[Setup]
; Unique Application ID
AppId={{5E4F8B2C-1D3A-4E9B-9876-C5A1D2E3F4B5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Per-User Installation: Does not require Administrator privileges (UAC prompt bypassed)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\CourierWorker
DisableDirPage=no

DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

OutputDir=.
OutputBaseFilename=CourierSetup-v1
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Uninstall behavior
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Courier Symphony automatically on Windows login"; GroupDescription: "Automation:"; Flags: unchecked

[Files]
; Dist payload files
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userprograms}\{#MyAppName}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up app directory while explicitly preserving user data in %LOCALAPPDATA%\Courier
Type: filesandordirs; Name: "{app}\*"
