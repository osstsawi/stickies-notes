<#
.SYNOPSIS
    Instala stickies-notes en Windows con autoinicio sin consola.

.DESCRIPTION
    Copia el codigo a %LOCALAPPDATA%\StickiesNotes, crea un venv con las
    dependencias de Windows (pywin32 + keyboard) y registra un .vbs en la
    carpeta Startup que lanza la app con pythonw.exe (sin ventana de consola).

.PARAMETER NoAutostart
    Instala sin registrar el arranque automatico.

.PARAMETER Uninstall
    Desinstala la app. NO borra las notas ya archivadas.

.EXAMPLE
    .\install_windows.ps1
    .\install_windows.ps1 -NoAutostart
    .\install_windows.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$NoAutostart,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$AppName    = "StickiesNotes"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$SrcDir     = Join-Path $InstallDir "src"
$VenvDir    = Join-Path $InstallDir "venv"
$StartupDir = [Environment]::GetFolderPath("Startup")
$VbsPath    = Join-Path $StartupDir "$AppName.vbs"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

if ($Uninstall) {
    Write-Step "Desinstalando $AppName..."
    if (Test-Path $VbsPath) {
        Remove-Item $VbsPath -Force
        Write-Host "    Autoinicio eliminado."
    }
    if (Test-Path $VenvDir) {
        Remove-Item $VenvDir -Recurse -Force
        Write-Host "    Entorno virtual eliminado."
    }
    if (Test-Path $SrcDir) {
        Remove-Item $SrcDir -Recurse -Force
        Write-Host "    Codigo eliminado."
    }
    Write-Host ""
    Write-Host "Listo. Tus notas archivadas NO se tocaron." -ForegroundColor Green
    exit 0
}

Write-Step "Verificando Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "No se encontro 'python' en el PATH. Instalalo desde https://www.python.org/downloads/ marcando 'Add python.exe to PATH'."
}
Write-Host "    $(python --version)"

Write-Step "Copiando codigo a $SrcDir..."
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDir = Join-Path $repoRoot "src"
if (-not (Test-Path $sourceDir)) {
    Write-Error "No se encontro la carpeta 'src' en $repoRoot. Corre este script desde el repo clonado."
}
if (Test-Path $SrcDir) { Remove-Item $SrcDir -Recurse -Force }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item $sourceDir -Destination $SrcDir -Recurse -Force

Write-Step "Creando entorno virtual..."
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$venvPythonw = Join-Path $VenvDir "Scripts\pythonw.exe"

Write-Step "Instalando dependencias (pywin32, keyboard, pystray, pillow)..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install --quiet pywin32 keyboard pystray pillow

if (-not $NoAutostart) {
    Write-Step "Registrando autoinicio sin consola..."
    # WshShell.Run con estilo 0 = ventana oculta; pythonw.exe ya evita la consola.
    $vbs = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$SrcDir"
WshShell.Run """$venvPythonw"" -m stickies_notes", 0, False
"@
    Set-Content -Path $VbsPath -Value $vbs -Encoding ASCII
    Write-Host "    $VbsPath"
} else {
    Write-Step "Autoinicio omitido (-NoAutostart)."
}

Write-Host ""
Write-Host "Instalacion completa." -ForegroundColor Green
Write-Host ""
Write-Host "  Arrancar ahora:  cd '$SrcDir'; & '$venvPythonw' -m stickies_notes"
Write-Host "  Nueva nota:      Ctrl+Alt+N"
Write-Host "  Salir:           Ctrl+Alt+Q"
Write-Host "  Notas en:        $env:USERPROFILE\Documents\StickiesNotes"
Write-Host ""
