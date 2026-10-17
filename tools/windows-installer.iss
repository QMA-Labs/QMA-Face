#ifndef BuildRoot
#define BuildRoot SourcePath + "..\build\windows\stage\QMAFace"
#endif
#ifndef OutputRoot
#define OutputRoot SourcePath + "..\dist"
#endif
[Setup]
AppId={{B69C1AD3-A2B9-47EB-95DE-9725D039C820}
AppName=QMA Face Personal Research
AppVersion=0.14.0
AppVerName=QMA Face 0.14.0 · Personal Research
AppPublisher=QMA Face
DefaultDirName={localappdata}\Programs\QMA Face
DefaultGroupName=QMA Face
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir={#OutputRoot}
OutputBaseFilename=QMA-Face-0.14.0-Personal-Setup
SetupIconFile={#BuildRoot}\qma-face.ico
UninstallDisplayIcon={app}\QMAFace.exe
LicenseFile={#BuildRoot}\PERSONAL-USE.txt
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=no
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
LZMADictionarySize=8192
CloseApplications=yes
CloseApplicationsFilter=QMAFace.exe
RestartApplications=no
DisableProgramGroupPage=yes
SetupLogging=yes
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QMA Face"; Filename: "{app}\QMAFace.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\QMA Face"; Filename: "{app}\QMAFace.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\QMAFace.exe"; Description: "{cm:LaunchProgram,QMA Face}"; Flags: nowait postinstall skipifsilent

; User data lives outside {app}. Uninstall intentionally preserves saved chats and exports.
