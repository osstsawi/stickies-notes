"""La nota adhesiva: ventana flotante Tkinter anclada a una ventana del SO."""

from __future__ import annotations

import datetime as dt
import re
import tkinter as tk
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from stickies_notes.backend import WindowBackend
    from stickies_notes.config import Config

COLOR_HEADER = "#f5d547"
COLOR_PAPER = "#fff8c4"
COLOR_TEXT = "#33312a"

NOTE_WIDTH = 280
NOTE_HEIGHT = 220
TRACK_INTERVAL_MS = 300

# Prefijo del titulo de la propia nota: sirve para no anclar una nota sobre otra.
NOTE_TITLE_PREFIX = "\U0001f4cc"

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def sanitize_filename(name: str) -> str:
    """Convierte un titulo de ventana en un fragmento de nombre de archivo valido.

    Recibe: el titulo crudo de la ventana.
    Devuelve: el titulo sin caracteres prohibidos, recortado a 80 chars;
              "sin_titulo" si queda vacio.
    """
    cleaned = _INVALID_CHARS.sub("_", name or "").strip()
    cleaned = cleaned.strip("._ ")
    cleaned = cleaned[:80].strip()
    return cleaned or "sin_titulo"


class WindowNote:
    """Nota adhesiva anclada al handle de una ventana concreta.

    La nota flota siempre encima, sigue a la ventana anclada y se archiva a un
    archivo Markdown cuando esa ventana se cierra o cuando el usuario la cierra.
    """

    # Registro global: un handle de ventana -> una nota como maximo.
    open_notes: Dict[int, "WindowNote"] = {}

    def __init__(
        self,
        root: tk.Tk,
        backend: "WindowBackend",
        config: "Config",
        handle: int,
    ) -> None:
        """Construye la nota y la posiciona junto a la ventana anclada.

        Recibe: el root Tkinter oculto, el backend del SO, la config y el
                handle de la ventana a la que se ancla.
        """
        self.root = root
        self.backend = backend
        self.config = config
        self.handle = handle
        self.window_title = backend.get_window_title(handle) or "sin_titulo"
        self.created_at = dt.datetime.now()
        self._alive = True
        # Offset manual respecto a la esquina de la ventana anclada; se fija
        # solo si el usuario arrastra la nota a mano.
        self._manual_offset: Optional[tuple[int, int]] = None
        self._drag_origin: Optional[tuple[int, int]] = None

        self._build_ui()
        self._position_near_window()
        WindowNote.open_notes[handle] = self
        self._track()

    def _build_ui(self) -> None:
        """Crea el Toplevel sin bordes con su header arrastrable y el cuerpo."""
        self.top = tk.Toplevel(self.root)
        self.top.title(f"{NOTE_TITLE_PREFIX} {self.window_title}")
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        try:
            self.top.attributes("-alpha", 0.96)
        except tk.TclError:
            # Algunos gestores de ventanas de Linux no soportan -alpha.
            pass
        self.top.geometry(f"{NOTE_WIDTH}x{NOTE_HEIGHT}")

        self.header = tk.Frame(self.top, bg=COLOR_HEADER, height=24)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        label_text = self.window_title
        if len(label_text) > 30:
            label_text = label_text[:29] + "…"
        self.title_label = tk.Label(
            self.header,
            text=f"{NOTE_TITLE_PREFIX} {label_text}",
            bg=COLOR_HEADER,
            fg=COLOR_TEXT,
            anchor="w",
            font=("Segoe UI", 8, "bold"),
        )
        self.title_label.pack(side="left", padx=6)

        self.close_button = tk.Label(
            self.header,
            text="✕",
            bg=COLOR_HEADER,
            fg=COLOR_TEXT,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.close_button.pack(side="right", padx=6)
        self.close_button.bind("<Button-1>", lambda _e: self._archive_and_close(True))

        self.text = tk.Text(
            self.top,
            bg=COLOR_PAPER,
            fg=COLOR_TEXT,
            relief="flat",
            wrap="word",
            undo=True,
            font=("Segoe UI", 10),
            padx=6,
            pady=4,
        )
        self.text.pack(fill="both", expand=True)

        for widget in (self.header, self.title_label):
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_move)

    def _on_drag_start(self, event: tk.Event) -> None:
        """Guarda el punto donde el usuario agarro la nota para arrastrarla."""
        self._drag_origin = (event.x_root, event.y_root)
        self._drag_geom = (self.top.winfo_x(), self.top.winfo_y())

    def _on_drag_move(self, event: tk.Event) -> None:
        """Mueve la nota y fija el offset manual respecto a la ventana anclada."""
        if self._drag_origin is None:
            return
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        new_x = self._drag_geom[0] + dx
        new_y = self._drag_geom[1] + dy
        self.top.geometry(f"+{new_x}+{new_y}")

        rect = self.backend.get_window_rect(self.handle)
        if rect:
            left, top, _right, _bottom = rect
            self._manual_offset = (new_x - left, new_y - top)

    def _position_near_window(self) -> None:
        """Coloca la nota junto a la ventana anclada.

        Por defecto en la esquina superior derecha de la ventana; si el usuario
        ya la arrastro, respeta el offset manual que fijo.
        """
        rect = self.backend.get_window_rect(self.handle)
        if not rect:
            return
        left, top, right, _bottom = rect
        if self._manual_offset is not None:
            x = left + self._manual_offset[0]
            y = top + self._manual_offset[1]
        else:
            x = right - NOTE_WIDTH - 10
            y = top + 30
        self.top.geometry(f"+{int(x)}+{int(y)}")

    def _track(self) -> None:
        """Sigue a la ventana anclada; la archiva cuando esa ventana desaparece."""
        if not self._alive:
            return
        if not self.backend.is_window(self.handle):
            self._archive_and_close(manual=False)
            return
        self._position_near_window()
        self.top.after(TRACK_INTERVAL_MS, self._track)

    def focus(self) -> None:
        """Trae la nota al frente y pone el cursor en el area de texto."""
        if not self._alive:
            return
        self.top.lift()
        self.top.attributes("-topmost", True)
        self.text.focus_force()

    def _save_to_file(self, content: str, manual: bool) -> None:
        """Escribe la nota como Markdown con su cabecera de metadatos.

        Recibe: el contenido de la nota y si el archivado fue manual.
        """
        self.config.ensure_dirs()
        archived_at = dt.datetime.now()
        stamp = archived_at.strftime("%Y-%m-%d_%H%M%S")
        filename = f"{stamp}__{sanitize_filename(self.window_title)}.md"
        path = self.config.archive_dir / filename
        reason = "cierre manual de la nota" if manual else "la ventana anclada se cerro"

        header = (
            f"# {self.window_title}\n\n"
            f"- **Creada:** {self.created_at:%Y-%m-%d %H:%M:%S}\n"
            f"- **Archivada:** {archived_at:%Y-%m-%d %H:%M:%S}\n"
            f"- **Motivo:** {reason}\n\n"
            "---\n\n"
        )
        path.write_text(header + content.rstrip() + "\n", encoding="utf-8")

    def _archive_and_close(self, manual: bool) -> None:
        """Archiva la nota (si tiene contenido) y destruye su ventana.

        Es idempotente: llamarla dos veces no duplica el archivo ni falla.
        Recibe: manual=True si la cerro el usuario, False si murio la ventana.
        """
        if not self._alive:
            return
        self._alive = False

        try:
            content = self.text.get("1.0", "end").strip()
        except tk.TclError:
            content = ""

        if content:
            try:
                self._save_to_file(content, manual)
            except OSError as exc:
                print(f"[stickies-notes] No se pudo archivar la nota: {exc}")

        WindowNote.open_notes.pop(self.handle, None)
        try:
            self.top.destroy()
        except tk.TclError:
            pass
