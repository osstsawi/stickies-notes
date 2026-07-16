"""Garantiza que solo corra una instancia de la aplicacion.

Sin esto es facil acabar con dos copias vivas —la que arranca con Windows mas
una lanzada a mano—, y cada una responde a la misma hotkey creando su propia
nota: el usuario pulsa Ctrl+Alt+N una vez y le salen dos notas.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

#: Nombre del mutex de Windows. El instalador lo declara como AppMutex en su
#: .iss para detectar la app en marcha, asi que los dos deben coincidir.
MUTEX_NAME = "StickiesNotes_SingleInstance"

LOCK_FILE_NAME = "stickies-notes.lock"


class InstanceLock:
    """Token que mantiene la exclusion mientras siga referenciado y vivo."""

    def __init__(self, handle: Any) -> None:
        """Recibe: el handle del mutex (Windows) o el archivo bloqueado (Linux)."""
        self._handle = handle


def acquire() -> Optional[InstanceLock]:
    """Intenta ser la unica instancia.

    Devuelve: un InstanceLock si lo consigue (hay que conservarlo vivo mientras
              corra la app), o None si ya hay otra instancia en marcha.
    """
    if sys.platform == "win32":
        return _acquire_windows()
    return _acquire_posix()


def _acquire_windows() -> Optional[InstanceLock]:
    """Reserva un mutex con nombre; si ya existia, es que hay otra instancia."""
    try:
        import win32api
        import win32event
        import winerror
    except ImportError:
        return InstanceLock(None)  # sin pywin32 no se bloquea nada

    handle = win32event.CreateMutex(None, False, MUTEX_NAME)
    # GetLastError debe leerse INMEDIATAMENTE despues de CreateMutex.
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return InstanceLock(handle)


def _acquire_posix() -> Optional[InstanceLock]:
    """Bloquea un archivo con flock; el bloqueo muere con el proceso."""
    try:
        import fcntl
    except ImportError:  # pragma: no cover - plataformas sin fcntl
        return InstanceLock(None)

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    lock_path = Path(runtime_dir) / LOCK_FILE_NAME
    try:
        handle = open(lock_path, "w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return InstanceLock(handle)


def notify_already_running() -> None:
    """Avisa de que la app ya esta corriendo.

    En Windows con un cuadro de dialogo: la app no tiene consola, asi que salir
    en silencio dejaria al usuario dandole al icono sin que pase nada.
    """
    message = (
        "stickies-notes ya está en ejecución.\n\n"
        "Búscalo en la bandeja del sistema, junto al reloj."
    )
    if sys.platform == "win32":
        try:
            import win32api
            import win32con

            win32api.MessageBox(
                0, message, "stickies-notes", win32con.MB_OK | win32con.MB_ICONINFORMATION
            )
            return
        except ImportError:
            pass
    print(f"[stickies-notes] {message}")
