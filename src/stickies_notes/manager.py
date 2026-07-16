"""Manager: registra las hotkeys globales y corre el loop de Tkinter."""

from __future__ import annotations

import sys
import tkinter as tk

from stickies_notes.backend import get_backend
from stickies_notes.config import Config
from stickies_notes.note import NOTE_TITLE_PREFIX, WindowNote


class NoteManager:
    """Coordina hotkeys globales, backend del SO y las notas abiertas."""

    def __init__(self) -> None:
        """Prepara el root Tkinter oculto, el backend y la configuracion."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.backend = get_backend()
        self.config = Config()
        self.config.ensure_dirs()
        self._listener = None

    def _create_or_focus(self) -> None:
        """Crea una nota para la ventana activa, o enfoca la que ya tenga.

        Corre en el hilo de Tkinter (encolado desde el hilo de la hotkey).
        """
        handle = self.backend.get_active_window()
        if not handle:
            return

        title = self.backend.get_window_title(handle)
        if title.startswith(NOTE_TITLE_PREFIX):
            # La ventana activa es una nota: no se ancla una nota sobre otra.
            return

        existing = WindowNote.open_notes.get(handle)
        if existing:
            existing.focus()
            return

        note = WindowNote(self.root, self.backend, self.config, handle)
        note.focus()

    def _quit(self) -> None:
        """Archiva todas las notas abiertas y termina el loop de Tkinter."""
        for note in list(WindowNote.open_notes.values()):
            note._archive_and_close(manual=True)
        self.root.after(100, self.root.quit)

    # Los callbacks de hotkey llegan en OTRO hilo: no se puede tocar Tkinter
    # desde ahi, asi que el trabajo real se encola en el hilo del mainloop.

    def _dispatch_create(self) -> None:
        """Encola la creacion de nota en el hilo de Tkinter."""
        self.root.after_idle(self._create_or_focus)

    def _dispatch_quit(self) -> None:
        """Encola la salida de la aplicacion en el hilo de Tkinter."""
        self.root.after_idle(self._quit)

    def _setup_hotkeys(self) -> None:
        """Registra las hotkeys globales con la libreria propia de cada SO."""
        if sys.platform == "win32":
            import keyboard  # import diferido: solo se usa en Windows

            keyboard.add_hotkey(self.config.hotkey_new, self._dispatch_create)
            keyboard.add_hotkey(self.config.hotkey_quit, self._dispatch_quit)
            return

        from pynput import keyboard as pk  # import diferido: solo en Linux

        self._listener = pk.GlobalHotKeys(
            {
                _to_pynput(self.config.hotkey_new): self._dispatch_create,
                _to_pynput(self.config.hotkey_quit): self._dispatch_quit,
            }
        )
        self._listener.start()

    def run(self) -> None:
        """Arranca la aplicacion: hotkeys + mainloop, y limpia al salir."""
        self._setup_hotkeys()
        print(
            f"[stickies-notes] Activo. {self.config.hotkey_new} = nueva nota, "
            f"{self.config.hotkey_quit} = salir. "
            f"Notas en: {self.config.archive_dir}"
        )
        try:
            self.root.mainloop()
        finally:
            if self._listener is not None:
                self._listener.stop()


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
    """Instancia el manager y lo ejecuta."""
    NoteManager().run()


if __name__ == "__main__":
    main()
