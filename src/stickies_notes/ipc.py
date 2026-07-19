"""Canal de control local: dispara acciones de la instancia en marcha.

En Wayland el compositor no entrega el teclado a las escuchas X11 de pynput,
asi que los atajos globales se registran en el escritorio (kglobalaccel en KDE)
y estos ejecutan `python -m stickies_notes new|quit`, que reenvia la orden por
un socket Unix a la instancia viva. El mismo canal sirve para disparar la app
desde scripts o desde la linea de comandos en cualquier sesion.
"""

from __future__ import annotations

import os
import socket
import tempfile
import threading
from pathlib import Path
from typing import Callable

SOCKET_NAME = "stickies-notes.sock"

COMMANDS = ("new", "quit")


def _socket_path() -> Path:
    """Devuelve la ruta del socket de control, junto al lock de instancia."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(runtime_dir) / SOCKET_NAME


class ControlServer:
    """Socket Unix que recibe ordenes ('new', 'quit') de otros procesos."""

    def __init__(self, on_new: Callable[[], None], on_quit: Callable[[], None]) -> None:
        """Recibe: callbacks seguros para llamar desde otro hilo (los dispatch_*
        del manager encolan en el hilo de Tkinter, igual que pynput y la bandeja).
        """
        self._on_new = on_new
        self._on_quit = on_quit
        self._path = _socket_path()
        # El lock de instancia unica ya garantiza que un socket preexistente es
        # huerfano de un cierre sucio, no de otra copia viva.
        self._path.unlink(missing_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self._path))
        self._sock.listen(1)
        self._thread = threading.Thread(
            target=self._serve, daemon=True, name="stickies-ipc"
        )
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:  # el socket se cerro en close()
                return
            with conn:
                try:
                    command = conn.recv(64).decode("utf-8", "replace").strip()
                except OSError:
                    continue
                if command == "new":
                    self._on_new()
                elif command == "quit":
                    self._on_quit()

    def close(self) -> None:
        """Cierra el socket y borra su archivo del runtime dir."""
        try:
            self._sock.close()
        finally:
            self._path.unlink(missing_ok=True)


def send(command: str) -> bool:
    """Envia una orden a la instancia en marcha.

    Recibe: 'new' o 'quit'.
    Devuelve: True si habia una instancia escuchando y acepto la orden.
    """
    if command not in COMMANDS:
        raise ValueError(f"Orden desconocida: {command!r} (validas: {COMMANDS})")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        try:
            sock.connect(str(_socket_path()))
            sock.sendall(command.encode("utf-8"))
        except OSError:
            return False
    return True
