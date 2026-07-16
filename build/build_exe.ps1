<#
.SYNOPSIS
    Compila stickies-notes a dist\StickiesNotes.exe con PyInstaller.

.DESCRIPTION
    Crea (o reutiliza) un venv de build, instala pyinstaller + las dependencias
    de Windows, y compila usando build\StickiesNotes.spec.

.NOTES
    ANTIVIRUS / SMARTSCREEN
      El .exe instala un hook global de teclado (libreria `keyboard`) y sale sin
      firmar, combinacion que dispara falsos positivos en Defender y en el
      filtro SmartScreen. Para uso propio se puede permitir manualmente; para
      distribuirlo a terceros hay que firmarlo con un certificado de code
      signing.

    AUTOINICIO CON EL .EXE
      Con el binario NO hace falta el truco del .vbs que usa install_windows.ps1:
      como se compila con --windowed no abre consola, asi que basta con dejar un
      acceso directo a StickiesNotes.exe en la carpeta `shell:startup`.

    RUTAS CON ACENTOS
      El modo --onefile descomprime a %TEMP% en cada arranque. Si el nombre de
      usuario o %TEMP% llevan tildes (ej. C:\Users\César\...), esa extraccion
      puede fallar por encoding. Solucion: compilar en --onedir, o fijar
      TMP/TEMP a una ruta ASCII antes de correr el .exe.

.EXAMPLE
    .\build_exe.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir  = Join-Path $RepoRoot ".venv-build"
$Spec     = Join-Path $RepoRoot "build\StickiesNotes.spec"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Verificando Python..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "No se encontro 'python' en el PATH."
}
Write-Host "    $(python --version)"

Write-Step "Preparando venv de build..."
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}
$venvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Step "Instalando pyinstaller, pywin32, keyboard..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install --quiet pyinstaller pywin32 keyboard

Write-Step "Compilando con $Spec..."
Push-Location $RepoRoot
try {
    & $venvPython -m PyInstaller --noconfirm $Spec
} finally {
    Pop-Location
}

$exe = Join-Path $RepoRoot "dist\StickiesNotes.exe"
if (-not (Test-Path $exe)) {
    Write-Error "La compilacion termino pero no se encontro $exe."
}

Write-Host ""
Write-Host "Binario listo: $exe" -ForegroundColor Green
Write-Host ""
Write-Host "  Autoinicio: copia un acceso directo del .exe a la carpeta 'shell:startup'."
Write-Host ""
