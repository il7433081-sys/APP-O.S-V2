; Instalador Inno Setup — App Ordem de Servico Digital

#define MyAppName "App OS Digital"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Oficina Nautica"
#define MyAppExeName "App_OS_Digital.exe"
#define MyAppId "{{6D6A3F26-44A8-4B46-9452-573A9A430D10}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Setup_App_OS_Digital
SetupIconFile=icone_os_digital.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "installer_input\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_input\config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_input\config.ini"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "installer_input\icone_os_digital.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
