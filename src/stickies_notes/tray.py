"""Icono en la bandeja del sistema, junto al reloj.

Es la unica pista visible de que la app esta viva: sin esto arranca con Windows,
no muestra nada y es indistinguible de una app rota.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from stickies_notes.config import open_folder

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from stickies_notes.manager import NoteManager

ICON_NAME = "icon.ico"


def _icon_path() -> Optional[Path]:
    """Localiza el .ico tanto empaquetado como corriendo desde el codigo.

    Devuelve: la ruta al icono, o None si no aparece.
    """
    # Empaquetado con PyInstaller: los datos van al directorio temporal _MEIPASS.
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        packed = Path(bundle_dir) / ICON_NAME
        if packed.exists():
            return packed

    # Corriendo desde el repo: src/stickies_notes/tray.py -> <repo>/build/icon.ico
    local = Path(__file__).resolve().parents[2] / "build" / ICON_NAME
    if local.exists():
        return local
    return None


def _load_image():
    """Carga la imagen del icono para pystray.

    Devuelve: un PIL.Image; si el .ico no aparece, un cuadrado amarillo liso
              para no dejar la bandeja sin icono por un archivo que falta.
    """
    from PIL import Image

    path = _icon_path()
    if path:
        return Image.open(path)
    return Image.new("RGBA", (64, 64), (245, 213, 71, 255))


class TrayIcon:
    """Icono de bandeja con el menu de la aplicacion."""

    def __init__(self, manager: "NoteManager") -> None:
        """Recibe: el NoteManager al que delegar las acciones del menu."""
        self.manager = manager
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    def _on_new(self, _icon=None, _item=None) -> None:
        """Crea una nota en la ultima ventana real que uso el usuario.

        No se usa la ventana activa: al abrir este menu, la ventana en primer
        plano pasa a ser la barra de tareas, y la nota se anclaria a ella.
        """
        self.manager.dispatch_create(use_last_user_window=True)

    def _on_open_folder(self, _icon=None, _item=None) -> None:
        """Abre la carpeta donde se archivan las notas."""
        try:
            open_folder(self.manager.config.archive_dir)
        except OSError as exc:
            print(f"[stickies-notes] No se pudo abrir la carpeta: {exc}")

    def _on_quit(self, _icon=None, _item=None) -> None:
        """Archiva todo y cierra la aplicacion."""
        self.manager.dispatch_quit()

    def start(self) -> bool:
        """Arranca el icono de bandeja en un hilo aparte.

        Devuelve: True si quedo activo; False si falta pystray o el sistema no
                  tiene bandeja disponible (en Linux es habitual).
        """
        try:
            import pystray
        except ImportError:
            print("[stickies-notes] pystray no disponible: se sigue sin icono de bandeja.")
            return False

        try:
            image = _load_image()
            menu = pystray.Menu(
                pystray.MenuItem("Nueva nota (Ctrl+Alt+N)", self._on_new, default=True),
                pystray.MenuItem("Abrir carpeta de notas", self._on_open_folder),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir (Ctrl+Alt+Q)", self._on_quit),
            )
            self._icon = pystray.Icon("stickies-notes", image, "stickies-notes", menu)
            # daemon: si el mainloop de Tk muere, este hilo no debe colgar la salida.
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()
            return True
        except Exception as exc:  # pragma: no cover - depende del entorno grafico
            print(f"[stickies-notes] No se pudo crear el icono de bandeja: {exc}")
            self._icon = None
            return False

    def stop(self) -> None:
        """Retira el icono de la bandeja."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
