[Setup]
AppName=Облік Ремонту
AppVersion=1.0
DefaultDirName={autopf}\ServiceManager
DefaultGroupName=Облік Ремонту
UninstallDisplayIcon={app}\main.exe
Compression=lzma2
SolidCompression=yes
OutputDir=installer_output
OutputBaseFilename=ServiceManager_Setup

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Облік Ремонту"; Filename: "{app}\main.exe"
Name: "{autodesktop}\Облік Ремонту"; Filename: "{app}\main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,Облік Ремонту}"; Flags: nowait postinstall skipifsilent
