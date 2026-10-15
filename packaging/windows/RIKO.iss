#ifndef AppSource
  #define AppSource "build/stage"
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{D630B455-215D-48E7-98CE-62F141D90BA5}
AppName=RIKO
AppVersion={#AppVersion}
AppPublisher=RIKO Project
DefaultDirName={localappdata}\Programs\RIKO
DefaultGroupName=RIKO
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputBaseFilename=RIKO-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\RIKO"; Filename: "{sys}\cmd.exe"; Parameters: "/D /C ""{app}\run-gui.bat"""; WorkingDir: "{app}"
Name: "{autoprograms}\RIKO CLI"; Filename: "{sys}\cmd.exe"; Parameters: "/D /K ""{app}\run.bat"""; WorkingDir: "{app}"

[Run]
Filename: "{sys}\cmd.exe"; Parameters: "/D /C ""{app}\install.bat"""; WorkingDir: "{app}"; StatusMsg: "Installing RIKO and downloading required models..."; Flags: waituntilterminated
