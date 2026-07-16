"""Configuracion: directorio de archivo de notas y hotkeys globales."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENV_ARCHIVE_DIR = "STICKIES_NOTES_DIR"


def default_archive_dir() -> Path:
    """Devuelve el directorio de notas por defecto segun el sistema operativo.

    Devuelve: ~/Documents/StickiesNotes en Windows, ~/StickiesNotes en Linux.
    """
    if sys.platform == "win32":
        return Path.home() / "Documents" / "StickiesNotes"
    return Path.home() / "StickiesNotes"


def resolve_archive_dir() -> Path:
    """Resuelve el directorio de archivo: variable de entorno o default del SO."""
    override = os.environ.get(ENV_ARCHIVE_DIR)
    if override:
        return Path(override).expanduser()
    return default_archive_dir()


@dataclass
class Config:
    """Parametros de ejecucion de la aplicacion."""

    archive_dir: Path = field(default_factory=resolve_archive_dir)
    hotkey_new: str = "ctrl+alt+n"
    hotkey_quit: str = "ctrl+alt+q"

    def ensure_dirs(self) -> None:
        """Crea el directorio de archivo si no existe."""
        self.archive_dir.mkdir(parents=True, exist_ok=True)
