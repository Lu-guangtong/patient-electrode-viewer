#define MyAppName "Patient Electrode Viewer"
#define MyAppVersion GetEnv("APP_VERSION")
#if MyAppVersion == ""
#define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Patient Electrode Viewer Contributors"
#define MyAppExeName "PatientElectrodeViewer.exe"
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define DistDir ProjectRoot + "\dist\PatientElectrodeViewer"

[Setup]
AppId={{AC90F26B-C0CC-4B21-94F4-0C4DDDD5D9E3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PatientElectrodeViewer
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir={#ProjectRoot}\dist\installer
OutputBaseFilename=PatientElectrodeViewer-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#ProjectRoot}\31_patient_electrode_viewer\patient_electrode_viewer.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Data Preparation Guide"; Filename: "{app}\docs\DATA_PREPARATION.md"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
