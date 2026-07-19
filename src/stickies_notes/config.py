"""Configuracion: directorio de archivo de notas y hotkeys globales."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENV_ARCHIVE_DIR = "STICKIES_NOTES_DIR"

ARCHIVE_DIR_NAME = "StickiesNotes"


def default_archive_dir() -> Path:
    """Devuelve el directorio de notas por defecto: en el perfil del usuario.

    Es ~/StickiesNotes en los dos sistemas (%USERPROFILE%\\StickiesNotes en
    Windows).

    Deliberadamente NO se usa la carpeta Documentos: en Windows suele estar
    redirigida a OneDrive y ademas esta traducida ("Documentos"), asi que
    Path.home()/"Documents" crea una carpeta fantasma distinta de la que el
    usuario ve en el Explorador, y las notas acaban en un sitio que nadie
    encuentra (o sincronizadas a la nube sin haberlo pedido).
    """
    return Path.home() / ARCHIVE_DIR_NAME


def resolve_archive_dir() -> Path:
    """Resuelve el directorio de archivo: variable de entorno o default."""
    override = os.environ.get(ENV_ARCHIVE_DIR)
    if override:
        return Path(override).expanduser()
    return default_archive_dir()


def open_folder(path: Path) -> None:
    """Abre una carpeta en el explorador de archivos del sistema.

    Recibe: la ruta a abrir; se crea si no existe (abrir una carpeta que no
            existe daria un error feo al usuario).
    """
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - API estandar de Windows
    else:
        subprocess.Popen(
            ["xdg-open", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@dataclass
class Config:
    """Parametros de ejecucion de la aplicacion."""

    archive_dir: Path = field(default_factory=resolve_archive_dir)
    hotkey_new: str = "ctrl+alt+n"
    hotkey_quit: str = "ctrl+alt+q"

    @property
    def draft_dir(self) -> Path:
        """Carpeta oculta donde cada nota abierta autoguarda su borrador.

        Si la app muere con notas abiertas (crash, kill, apagon), lo escrito
        sobrevive aqui y se recupera al siguiente arranque.
        """
        return self.archive_dir / ".borradores"

    def ensure_dirs(self) -> None:
        """Crea el directorio de archivo si no existe."""
        self.archive_dir.mkdir(parents=True, exist_ok=True)
