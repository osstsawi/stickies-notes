# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para stickies-notes (equivale a --onefile --windowed).

Compilar:  pyinstaller --noconfirm build/StickiesNotes.spec
Salida:    dist/StickiesNotes.exe
"""

from PyInstaller.utils.hooks import collect_submodules

# win32gui/win32con se importan de forma DIFERIDA dentro de WinBackend.__init__,
# asi que PyInstaller no los detecta por analisis estatico. Sin declararlos aqui
# el .exe compila pero revienta en runtime al crear el backend.
hiddenimports = ["win32gui", "win32con"]

# keyboard carga sus backends de plataforma dinamicamente: hay que meter todo
# el paquete o las hotkeys globales no se registran en el binario.
hiddenimports += collect_submodules("keyboard")


a = Analysis(
    ["../src/stickies_notes/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StickiesNotes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # equivale a --windowed: sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
