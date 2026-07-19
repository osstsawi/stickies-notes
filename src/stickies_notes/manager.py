"""Manager: registra las hotkeys globales y corre el loop de Tkinter."""

from __future__ import annotations

import sys
import time
import tkinter as tk
from typing import Optional

from stickies_notes import single_instance
from stickies_notes.backend import enable_dpi_awareness, get_backend
from stickies_notes.config import Config
from stickies_notes.note import NOTE_TITLE_PREFIX, WindowNote
from stickies_notes.tray import TrayIcon

# Ventana muerta tras disparar una hotkey. La libreria `keyboard` puede reenviar
# el atajo mientras las teclas siguen pulsadas (autorepeticion de Windows), y sin
# esto una sola pulsacion acaba creando dos notas.
HOTKEY_DEBOUNCE_S = 0.4

# Cada cuanto se recuerda cual era la ventana "de verdad" del usuario.
FOREGROUND_POLL_MS = 200


class NoteManager:
    """Coordina hotkeys globales, icono de bandeja, backend y notas abiertas."""

    def __init__(self) -> None:
        """Prepara el root Tkinter oculto, el backend y la configuracion."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.backend = get_backend()
        self.config = Config()
        self.config.ensure_dirs()
        self._listener = None
        self._ipc = None
        self._tray: Optional[TrayIcon] = None
        self._last_create = 0.0
        self._last_quit = 0.0
        self._last_user_window: Optional[int] = None

    # ------------------------------------------------------------- Foreground

    def _watch_foreground(self) -> None:
        """Recuerda la ultima ventana real que uso el usuario.

        La necesita el menu de la bandeja: al desplegarlo, la ventana en primer
        plano pasa a ser la barra de tareas, asi que preguntar por la activa en
        ese momento anclaria la nota a la barra.
        """
        try:
            handle = self.backend.get_active_window()
            if (
                handle
                and handle not in WindowNote.note_hwnds
                and not self.backend.is_shell_window(handle)
            ):
                self._last_user_window = handle
        except Exception:
            pass
        self.root.after(FOREGROUND_POLL_MS, self._watch_foreground)

    # ----------------------------------------------------------------- Acciones

    def _create_or_focus(self, use_last_user_window: bool = False) -> None:
        """Crea una nota para la ventana objetivo, o enfoca la que ya tenga.

        Recibe: use_last_user_window=True para anclar a la ultima ventana del
                usuario en vez de a la activa (lo usa el menu de la bandeja).

        Corre en el hilo de Tkinter (encolado desde el hilo de la hotkey).
        """
        if use_last_user_window:
            handle = self._last_user_window
        else:
            handle = self.backend.get_active_window()

        if not handle or not self.backend.is_window(handle):
            return

        # No anclar una nota sobre otra nota. Se comprueba por handle y no solo
        # por el titulo porque las notas son ventanas overrideredirect, que el
        # sistema puede reportar sin titulo: cuando eso pasa, la guarda del
        # prefijo no las reconoce y la nota acaba anclada a si misma.
        if handle in WindowNote.note_hwnds:
            return
        if self.backend.is_shell_window(handle):
            return
        if self.backend.get_window_title(handle).startswith(NOTE_TITLE_PREFIX):
            return

        existing = WindowNote.open_notes.get(handle)
        if existing:
            existing.focus()
            return

        WindowNote(self.root, self.backend, self.config, handle).focus()

    def _quit(self) -> None:
        """Archiva todas las notas abiertas y termina el loop de Tkinter."""
        for note in list(WindowNote.open_notes.values()):
            note._archive_and_close(manual=True)
        if self._tray is not None:
            self._tray.stop()
        self.root.after(100, self.root.quit)

    # Los callbacks de hotkey y los del icono de bandeja llegan en OTRO hilo: no
    # se puede tocar Tkinter desde ahi, asi que el trabajo real se encola en el
    # hilo del mainloop.

    def dispatch_create(self, use_last_user_window: bool = False) -> None:
        """Encola la creacion de nota en el hilo de Tkinter, con antirrebote."""
        now = time.monotonic()
        if now - self._last_create < HOTKEY_DEBOUNCE_S:
            return
        self._last_create = now
        self.root.after_idle(lambda: self._create_or_focus(use_last_user_window))

    def dispatch_quit(self) -> None:
        """Encola la salida de la aplicacion en el hilo de Tkinter."""
        now = time.monotonic()
        if now - self._last_quit < HOTKEY_DEBOUNCE_S:
            return
        self._last_quit = now
        self.root.after_idle(self._quit)

    # ------------------------------------------------------------------ Arranque

    def _setup_hotkeys(self) -> None:
        """Registra las hotkeys globales con la libreria propia de cada SO."""
        if sys.platform == "win32":
            import keyboard  # import diferido: solo se usa en Windows

            keyboard.add_hotkey(self.config.hotkey_new, self.dispatch_create)
            keyboard.add_hotkey(self.config.hotkey_quit, self.dispatch_quit)
            return

        from pynput import keyboard as pk  # import diferido: solo en Linux

        self._listener = pk.GlobalHotKeys(
            {
                _to_pynput(self.config.hotkey_new): self.dispatch_create,
                _to_pynput(self.config.hotkey_quit): self.dispatch_quit,
            }
        )
        self._listener.start()

        # pynput escucha por X11: en Wayland el compositor no le entrega el
        # teclado y las hotkeys mueren en silencio. El socket de control cubre
        # ese caso — el atajo se registra en el escritorio (el instalador lo
        # hace en KDE) y dispara `python -m stickies_notes new|quit`.
        from stickies_notes import ipc

        try:
            self._ipc = ipc.ControlServer(self.dispatch_create, self.dispatch_quit)
        except OSError as exc:
            print(f"[stickies-notes] Canal de control no disponible: {exc}")

    def run(self) -> None:
        """Arranca la aplicacion: hotkeys, bandeja y mainloop; limpia al salir."""
        self._setup_hotkeys()
        self._tray = TrayIcon(self)
        if not self._tray.start():
            self._tray = None
        self._watch_foreground()
        print(
            f"[stickies-notes] Activo. {self.config.hotkey_new} = nueva nota, "
            f"{self.config.hotkey_quit} = salir. "
            f"Notas en: {self.config.archive_dir}"
        )
        try:
            self.root.mainloop()
        finally:
            if self._tray is not None:
                self._tray.stop()
            if self._listener is not None:
                self._listener.stop()
            if self._ipc is not None:
                self._ipc.close()


def _to_pynput(hotkey: str) -> str:
    """Traduce una hotkey estilo `keyboard` al formato de pynput.

    Recibe: por ejemplo "ctrl+alt+n".
    Devuelve: por ejemplo "<ctrl>+<alt>+n".
    """
    modifiers = {"ctrl", "alt", "shift", "cmd", "super"}
    parts = []
    for raw in hotkey.split("+"):
        key = raw.strip().lower()
        parts.append(f"<{key}>" if key in modifiers else key)
    return "+".join(parts)


def main() -> None:
    """Punto de entrada: DPI, instancia unica y arranque del manager."""
    # Antes de crear cualquier ventana de Tk, o Windows fija la escala del
    # proceso y ya no hay vuelta atras.
    enable_dpi_awareness()

    lock = single_instance.acquire()
    if lock is None:
        single_instance.notify_already_running()
        return

    NoteManager().run()
    # `lock` se mantiene referenciado hasta aqui a proposito: si se liberase
    # antes, otra instancia podria colarse mientras esta sigue viva.
    del lock


if __name__ == "__main__":
    main()
