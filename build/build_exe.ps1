<#
.SYNOPSIS
    Compila stickies-notes: .exe portable, build --onedir e instalador nativo.

.DESCRIPTION
    Produce hasta tres cosas en dist\:
      StickiesNotes.exe          portable, un solo archivo, no instala nada
      StickiesNotes\             build --onedir (insumo del instalador)
      StickiesNotes-Setup.exe    instalador nativo de Windows (Inno Setup)

    Ninguna requiere Python en la maquina destino: PyInstaller lo empaqueta.

.PARAMETER SkipInstaller
    No compila el instalador aunque Inno Setup este disponible.

.PARAMETER SkipPortable
    No compila el .exe portable (util si solo quieres el instalador).

.NOTES
    ANTIVIRUS / SMARTSCREEN
      El binario instala un hook global de teclado (libreria `keyboard`) y sale
      sin firmar, combinacion que dispara falsos positivos en Defender y en el
      filtro SmartScreen. Para uso propio se puede permitir a mano; para
      distribuirlo a terceros hay que firmarlo con un certificado de code
      signing.

    POR QUE EL INSTALADOR USA --onedir
      El modo --onefile se descomprime en %TEMP% en cada arranque: cuesta
      tiempo y falla si %TEMP% lleva caracteres no ASCII (usuarios con tildes).
      Ya instalado no hay razon para pagarlo. El portable sigue en --onefile
      porque ahi el archivo unico es justamente la gracia.

.EXAMPLE
    .\build\build_exe.ps1
    .\build\build_exe.ps1 -SkipInstaller
#>
[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [switch]$SkipPortable
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir  = Join-Path $RepoRoot ".venv-build"
$Spec     = Join-Path $RepoRoot "build\StickiesNotes.spec"
$Iss      = Join-Path $RepoRoot "installers\StickiesNotes.iss"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Find-Iscc {
    <#
        Localiza el compilador de Inno Setup. Devuelve la ruta o $null.
        En los runners de GitHub viene en el PATH; en un equipo normal suele
        estar bajo Program Files.
    #>
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
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

Write-Step "Instalando pyinstaller, pywin32, keyboard, pystray, pillow..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install --quiet pyinstaller pywin32 keyboard pystray pillow

Push-Location $RepoRoot
try {
    if (-not $SkipPortable) {
        Write-Step "Compilando portable (--onefile)..."
        $env:STICKIES_ONEDIR = $null
        & $venvPython -m PyInstaller --noconfirm $Spec
    }

    Write-Step "Compilando build --onedir..."
    $env:STICKIES_ONEDIR = "1"
    try {
        & $venvPython -m PyInstaller --noconfirm $Spec
    } finally {
        $env:STICKIES_ONEDIR = $null
    }

    if (-not $SkipInstaller) {
        $iscc = Find-Iscc
        if ($iscc) {
            Write-Step "Compilando instalador con Inno Setup..."
            Write-Host "    $iscc"
            & $iscc $Iss
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Inno Setup fallo con codigo $LASTEXITCODE."
            }
        } else {
            Write-Host ""
            Write-Host "Inno Setup no encontrado: se omite el instalador." -ForegroundColor Yellow
            Write-Host "  Instalalo desde https://jrsoftware.org/isdl.php y vuelve a correr este script."
            Write-Host ""
        }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Compilacion terminada." -ForegroundColor Green
Write-Host ""
foreach ($artifact in @(
    @{ Path = "dist\StickiesNotes-Setup.exe"; Desc = "Instalador nativo" },
    @{ Path = "dist\StickiesNotes.exe";       Desc = "Portable (un archivo)" },
    @{ Path = "dist\StickiesNotes";           Desc = "Build --onedir" }
)) {
    $full = Join-Path $RepoRoot $artifact.Path
    if (Test-Path $full) {
        $item = Get-Item $full
        if ($item.PSIsContainer) {
            $size = (Get-ChildItem $full -Recurse | Measure-Object -Property Length -Sum).Sum
        } else {
            $size = $item.Length
        }
        Write-Host ("  {0,-24} {1,8:N1} MB  {2}" -f $artifact.Desc, ($size / 1MB), $artifact.Path)
    }
}
Write-Host ""
