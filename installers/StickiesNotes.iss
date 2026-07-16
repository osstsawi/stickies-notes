; Instalador nativo de Windows para stickies-notes (Inno Setup 6).
;
; Compila el build --onedir de PyInstaller en un unico StickiesNotes-Setup.exe:
; asistente clasico, acceso directo, autoinicio opcional y desinstalador
; registrado en "Agregar o quitar programas". No requiere Python en la maquina.
;
; Compilar (necesita dist\StickiesNotes\ ya generado por build_exe.ps1):
;   ISCC.exe installers\StickiesNotes.iss
; Salida: dist\StickiesNotes-Setup.exe
;
; NOTA: este archivo va en UTF-8 CON BOM. Inno Setup 6 asume ANSI si no
; encuentra el BOM, y los acentos del asistente saldrian corruptos.

#define MyAppName "stickies-notes"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "César Bermúdez Rodríguez"
#define MyAppURL "https://github.com/osstsawi/stickies-notes"
#define MyAppExeName "StickiesNotes.exe"

[Setup]
; AppId identifica el producto entre versiones: NO cambiarlo o Windows tratara
; cada version como un programa distinto y se acumularan en Agregar o quitar.
AppId={{D5B99CC5-8FBA-4961-8AFD-98229C8DFDF5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}

; Debe coincidir con single_instance.MUTEX_NAME: asi Inno detecta por si mismo
; que la app esta corriendo y lo avisa, en vez de depender solo del taskkill.
AppMutex=StickiesNotes_SingleInstance

; Instalacion por usuario: sin UAC, sin pedir admin. Con PrivilegesRequired=lowest
; el {autopf} resuelve a %LOCALAPPDATA%\Programs, igual que hace VS Code.
PrivilegesRequired=lowest
DefaultDirName={autopf}\StickiesNotes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

LicenseFile=..\LICENSE
SetupIconFile=..\build\icon.ico
OutputDir=..\dist
OutputBaseFilename=StickiesNotes-Setup
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar {#MyAppName} automáticamente con Windows"; GroupDescription: "Opciones adicionales:"
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Opciones adicionales:"; Flags: unchecked

[Files]
; El build --onedir completo: el .exe mas sus dependencias ya empaquetadas.
Source: "..\dist\StickiesNotes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Autoinicio por clave Run del usuario. uninsdeletevalue lo limpia al desinstalar.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "StickiesNotes"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName} ahora"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Sin esto, los archivos en uso no se pueden borrar y queda basura instalada.
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#MyAppExeName}"; \
    Flags: runhidden; RunOnceId: "KillStickiesNotes"

[Messages]
spanish.FinishedLabel=La instalación de [name] terminó.%n%nPulsa Ctrl+Alt+N sobre cualquier ventana para crear una nota anclada a ella, y Ctrl+Alt+Q para salir. Las notas se archivan solas en Documentos\StickiesNotes cuando cierras la ventana.

[Code]
{ Cierra la app antes de instalar: si esta corriendo, sus archivos estan
  bloqueados y la actualizacion fallaria a medias. }
procedure KillRunningApp;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im {#MyAppExeName}',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillRunningApp;
  Result := '';
end;

{ Aviso explicito al desinstalar: las notas archivadas NO se tocan. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { UninstallSilent: sin esta guarda, una desinstalacion desatendida se
    quedaria colgada esperando un OK que nadie va a pulsar. }
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('stickies-notes se desinstaló.' + #13#10#13#10 +
           'Tus notas archivadas siguen intactas en Documentos\StickiesNotes.',
           mbInformation, MB_OK);
end;
