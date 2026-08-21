; GGU_VDOD Windows installer (Inno Setup 6)
; Compiled by build_exe.ps1 with:
;   ISCC.exe /DAppVersion=x.y.z /DSourceDir=dist\GGU_VDOD installer\GGU_VDOD.iss
; Produces a per-user installer: no admin rights, installs to
; %LOCALAPPDATA%\Programs\GGU_VDOD, adds Start Menu + optional desktop
; shortcuts and a proper Windows uninstaller entry.
; Copyright @XerumGG
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif

#ifndef SourceDir
#define SourceDir "dist\GGU_VDOD"
#endif

[Setup]
AppId={{1618653F-DA21-4DAE-9403-FC5A7748C2A5}
AppName=GGU_VDOD
AppVersion={#AppVersion}
AppPublisher=XerumGG 
DefaultDirName={localappdata}\Programs\GGU_VDOD
DisableDirPage=no
DefaultGroupName=GGU_VDOD
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=GGU_VDOD-setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\GGU_VDOD.exe
CloseApplications=yes
RestartApplications=no

[Messages]
WelcomeLabel2=This will install GGU_VDOD, the desktop media downloader and local converter, on your computer.%n%nIt installs for your Windows user only - no administrator rights are needed.

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "temp_cookies,temp_cookies\*,auth_sessions.json,auth_sessions.dat"

[Icons]
Name: "{group}\GGU_VDOD"; Filename: "{app}\GGU_VDOD.exe"
Name: "{group}\Uninstall GGU_VDOD"; Filename: "{uninstallexe}"
Name: "{autodesktop}\GGU_VDOD"; Filename: "{app}\GGU_VDOD.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\GGU_VDOD.exe"; Description: "{cm:LaunchProgram,GGU_VDOD}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data in %LOCALAPPDATA%\GGU_VDOD is intentionally preserved on uninstall.
Type: filesandordirs; Name: "{app}\temp_cookies"
