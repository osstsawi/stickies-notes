# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para stickies-notes. Genera dos formas del binario.

    pyinstaller --noconfirm build/StickiesNotes.spec
        -> dist/StickiesNotes.exe          (--onefile: portable, 1 solo archivo)

    STICKIES_ONEDIR=1 pyinstaller --noconfirm build/StickiesNotes.spec
        -> dist/StickiesNotes/StickiesNotes.exe   (--onedir: lo que empaqueta
                                                   el instalador de Inno Setup)

Por que el instalador usa --onedir: el modo --onefile se descomprime en %TEMP%
en CADA arranque, lo que cuesta tiempo y falla si la ruta de %TEMP% lleva
caracteres no ASCII (usuarios con tildes). Ya instalado no hay razon para pagar
ese precio: --onedir arranca directo desde su carpeta.
"""

import os

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ONEDIR = os.environ.get("STICKIES_ONEDIR") == "1"

VERSION = "1.1.0"
_v = tuple(int(p) for p in VERSION.split(".")) + (0,)

ICON = os.path.join(SPECPATH, "icon.ico")  # noqa: F821 - SPECPATH lo inyecta PyInstaller
SRC = os.path.join(SPECPATH, "..", "src")  # noqa: F821

# win32gui/win32con se importan de forma DIFERIDA dentro de WinBackend.__init__,
# asi que PyInstaller no los detecta por analisis estatico. Sin declararlos aqui
# el .exe compila pero revienta en runtime al crear el backend.
hiddenimports = ["win32gui", "win32con"]

# keyboard carga sus backends de plataforma dinamicamente: hay que meter todo
# el paquete o las hotkeys globales no se registran en el binario.
hiddenimports += collect_submodules("keyboard")

# Metadatos que Windows muestra en Propiedades del archivo. Sin esto el .exe
# aparece sin nombre ni version, que es medio camino a parecer sospechoso.
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_v, prodvers=_v, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040A04B0",  # es-ES / Unicode
                    [
                        StringStruct("CompanyName", "César Bermúdez Rodríguez"),
                        StringStruct("FileDescription", "stickies-notes — notas ancladas a ventanas"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "StickiesNotes"),
                        StringStruct("LegalCopyright", "© 2026 César Bermúdez Rodríguez. Licencia MIT."),
                        StringStruct("OriginalFilename", "StickiesNotes.exe"),
                        StringStruct("ProductName", "stickies-notes"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x040A, 1200])]),
    ],
)


a = Analysis(
    [os.path.join(SRC, "stickies_notes", "__main__.py")],
    pathex=[SRC],
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

if ONEDIR:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="StickiesNotes",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # equivale a --windowed: sin ventana de consola
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
        version=version_info,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="StickiesNotes",
    )
else:
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
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
        version=version_info,
    )
