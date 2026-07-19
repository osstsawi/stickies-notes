"""La nota adhesiva: ventana flotante Tkinter anclada a una ventana del SO."""

from __future__ import annotations

import datetime as dt
import re
import tkinter as tk
from typing import TYPE_CHECKING, Dict, Optional, Set, Tuple

from stickies_notes.backend import BASE_DPI

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from stickies_notes.backend import WindowBackend
    from stickies_notes.config import Config

COLOR_HEADER = "#f5d547"
COLOR_PAPER = "#fff8c4"
COLOR_TEXT = "#33312a"

# Medidas en pixeles logicos (a 96 DPI). En pantallas con otra escala se
# multiplican por dpi/96: ver _apply_scale().
BASE_WIDTH = 280
BASE_HEIGHT = 220
BASE_HEADER_H = 24
BASE_FONT_TITLE = 11
BASE_FONT_CLOSE = 13
BASE_FONT_TEXT = 13
BASE_MARGIN = 10
BASE_TOP_OFFSET = 30

# El seguimiento va a ~30 fps. Con 300 ms la nota se arrastraba visiblemente por
# detras de la ventana al moverla; GetWindowRect es barato, asi que el sondeo
# rapido no se nota en CPU.
TRACK_INTERVAL_MS = 33

# Cada cuantos ticks del track se autoguarda el borrador (~2 s). Solo escribe
# si el contenido cambio desde la ultima vez.
AUTOSAVE_TICKS = 60

# Prefijo del titulo de la propia nota. Es la segunda linea de defensa para no
# anclar una nota sobre otra; la primera es WindowNote.note_hwnds, porque una
# ventana overrideredirect puede no exponer titulo al sistema.
NOTE_TITLE_PREFIX = "\U0001f4cc"

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

Rect = Tuple[int, int, int, int]


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


def rects_overlap(a: Optional[Rect], b: Optional[Rect]) -> bool:
    """Indica si dos rectangulos (left, top, right, bottom) se solapan.

    Recibe: dos rectangulos, o None si alguno no se pudo consultar.
    Devuelve: False si falta alguno (sin dato no se asume solape).
    """
    if not a or not b:
        return False
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


class WindowNote:
    """Nota adhesiva anclada al handle de una ventana concreta.

    La nota sigue a la ventana anclada, se esconde cuando esa ventana se
    minimiza o queda tapada, y se archiva a un archivo Markdown cuando la
    ventana se cierra.
    """

    # Registro global: un handle de ventana -> una nota como maximo.
    open_notes: Dict[int, "WindowNote"] = {}

    # Handles de las ventanas de las PROPIAS notas. Sirve para que una nota
    # nunca se ancle a otra nota (ver manager._create_or_focus).
    note_hwnds: Set[int] = set()

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
        self._visible = True
        # Offset manual respecto a la esquina de la ventana anclada; se fija
        # solo si el usuario arrastra la nota a mano.
        self._manual_offset: Optional[Tuple[int, int]] = None
        self._drag_origin: Optional[Tuple[int, int]] = None
        self._drag_geom: Tuple[int, int] = (0, 0)
        self._own_hwnds: Set[int] = set()
        self._dpi = 0
        self._scale = 1.0
        self._w = BASE_WIDTH
        self._h = BASE_HEIGHT
        self._pos: Optional[Tuple[int, int]] = None
        self._tick = 0
        self._draft_content = ""
        stamp = self.created_at.strftime("%Y-%m-%d_%H%M%S")
        self._draft_path = (
            config.draft_dir / f"{stamp}__{sanitize_filename(self.window_title)}.md"
        )

        self._build_ui()
        self._apply_scale(backend.get_window_dpi(handle))
        self._position_near_window()
        self._register_own_hwnds()
        WindowNote.open_notes[handle] = self
        self._track()

    # ------------------------------------------------------------------ UI

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

        self.header = tk.Frame(self.top, bg=COLOR_HEADER, height=BASE_HEADER_H)
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
        )
        self.title_label.pack(side="left", padx=6)

        self.close_button = tk.Label(
            self.header,
            text="✕",
            bg=COLOR_HEADER,
            fg=COLOR_TEXT,
            cursor="hand2",
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
            padx=6,
            pady=4,
        )
        self.text.pack(fill="both", expand=True)

        for widget in (self.header, self.title_label):
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_move)

    def _apply_scale(self, dpi: int) -> None:
        """Reescala la nota al DPI del monitor donde esta la ventana anclada.

        Recibe: el DPI del monitor (96 = escala 100%).

        Como el proceso es per-monitor DPI aware, Windows ya no reescala nada
        por nosotros: sin esto la nota se veria diminuta en un monitor al 150%.
        Las fuentes se piden en PIXELES (tamano negativo en Tk) para que no
        dependan del factor de escala global de Tk, que se fija una sola vez al
        arrancar y no sirve con monitores de escalas distintas.
        """
        if dpi == self._dpi:
            return
        self._dpi = dpi
        self._scale = dpi / BASE_DPI
        s = self._scale

        self._w = round(BASE_WIDTH * s)
        self._h = round(BASE_HEIGHT * s)

        self.header.configure(height=round(BASE_HEADER_H * s))
        self.title_label.configure(font=("Segoe UI", -round(BASE_FONT_TITLE * s), "bold"))
        self.close_button.configure(font=("Segoe UI", -round(BASE_FONT_CLOSE * s), "bold"))
        self.text.configure(font=("Segoe UI", -round(BASE_FONT_TEXT * s)))

        # Fuerza el redibujo con el tamano nuevo; la posicion la fija el track.
        self._pos = None

    def _register_own_hwnds(self) -> None:
        """Anota los handles de la ventana de esta nota en el registro global.

        Se guarda tambien el padre porque Tk envuelve sus toplevels y el handle
        que ve el sistema como ventana activa puede ser el del envoltorio.
        """
        hwnds: Set[int] = set()
        try:
            self.top.update_idletasks()
            wid = int(self.top.winfo_id())
            hwnds.add(wid)
            parent = self.backend.get_window_parent(wid)
            if parent:
                hwnds.add(parent)
        except Exception:
            pass
        self._own_hwnds = hwnds
        WindowNote.note_hwnds |= hwnds

    # -------------------------------------------------------------- Arrastre

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
        self._pos = (new_x, new_y)

        rect = self.backend.get_window_rect(self.handle)
        if rect:
            left, top, _right, _bottom = rect
            self._manual_offset = (new_x - left, new_y - top)

    # ------------------------------------------------------------ Seguimiento

    def _target_pos(self) -> Optional[Tuple[int, int]]:
        """Calcula donde deberia estar la nota segun la ventana anclada.

        Devuelve: (x, y) absolutos, o None si la ventana ya no se puede leer.
        """
        rect = self.backend.get_window_rect(self.handle)
        if not rect:
            return None
        left, top, right, _bottom = rect
        if self._manual_offset is not None:
            return (left + self._manual_offset[0], top + self._manual_offset[1])
        margin = round(BASE_MARGIN * self._scale)
        return (right - self._w - margin, top + round(BASE_TOP_OFFSET * self._scale))

    def _position_near_window(self) -> None:
        """Coloca la nota junto a la ventana anclada, si hace falta moverla.

        Solo llama a geometry() cuando la posicion cambia: hacerlo en cada
        tick a 30 fps provoca parpadeo y trabajo inutil.
        """
        target = self._target_pos()
        if target is None:
            return
        if target == self._pos:
            return
        self._pos = target
        self.top.geometry(f"{self._w}x{self._h}+{int(target[0])}+{int(target[1])}")

    def _note_rect(self) -> Optional[Rect]:
        """Devuelve el rectangulo que ocupa la nota, o None si aun no tiene sitio."""
        if self._pos is None:
            return None
        x, y = self._pos
        return (x, y, x + self._w, y + self._h)

    def _should_be_visible(self) -> bool:
        """Decide si la nota debe verse ahora mismo.

        La nota se esconde cuando su ventana esta minimizada u oculta, y cuando
        otra ventana en primer plano la tapa. El solape se comprueba de verdad
        (en vez de esconderla siempre que su ventana no tenga el foco) para no
        hacerla desaparecer cuando la ventana en primer plano esta en OTRO
        monitor y no la esta tapando en absoluto.
        """
        if not self.backend.is_window_visible(self.handle):
            return False
        if self.backend.is_window_minimized(self.handle):
            return False

        foreground = self.backend.get_active_window()
        if foreground is None:
            return True
        # La propia ventana anclada, o esta misma nota mientras se escribe.
        if foreground == self.handle or foreground in self._own_hwnds:
            return True
        return not rects_overlap(
            self.backend.get_window_rect(foreground), self._note_rect()
        )

    def _set_visible(self, visible: bool) -> None:
        """Muestra u oculta la nota, sin repetir la llamada si ya esta asi."""
        if visible == self._visible:
            return
        self._visible = visible
        try:
            if visible:
                self.top.deiconify()
                # Windows pierde estos atributos al volver de withdraw().
                self.top.overrideredirect(True)
                self.top.attributes("-topmost", True)
            else:
                self.top.withdraw()
        except tk.TclError:
            pass

    def _track(self) -> None:
        """Sigue a la ventana anclada: posicion, escala y visibilidad."""
        if not self._alive:
            return
        if not self.backend.is_window(self.handle):
            self._archive_and_close(manual=False)
            return

        self._apply_scale(self.backend.get_window_dpi(self.handle))
        self._position_near_window()
        self._set_visible(self._should_be_visible())
        self._tick += 1
        if self._tick % AUTOSAVE_TICKS == 0:
            self._autosave()
        self.top.after(TRACK_INTERVAL_MS, self._track)

    def focus(self) -> None:
        """Trae la nota al frente y pone el cursor en el area de texto."""
        if not self._alive:
            return
        self._set_visible(True)
        self.top.lift()
        self.top.attributes("-topmost", True)
        self.text.focus_force()

    # -------------------------------------------------------------- Archivado

    def _autosave(self) -> None:
        """Persiste el borrador a disco si el contenido cambio.

        Es la red de seguridad contra crashes, kills y apagones: lo escrito
        nunca vive solo en memoria mas de un par de segundos. El borrador se
        borra al archivar la nota de verdad.
        """
        try:
            content = self.text.get("1.0", "end").strip()
        except tk.TclError:
            return
        if content == self._draft_content:
            return
        self._draft_content = content
        try:
            if content:
                self._draft_path.parent.mkdir(parents=True, exist_ok=True)
                self._draft_path.write_text(content + "\n", encoding="utf-8")
            else:
                self._draft_path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"[stickies-notes] No se pudo autoguardar el borrador: {exc}")

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
            # El widget murio antes de poder leerlo: el borrador autoguardado
            # es la ultima copia buena del contenido.
            content = self._draft_content

        if content:
            try:
                self._save_to_file(content, manual)
            except OSError as exc:
                print(f"[stickies-notes] No se pudo archivar la nota: {exc}")

        try:
            self._draft_path.unlink(missing_ok=True)
        except OSError:
            pass

        WindowNote.open_notes.pop(self.handle, None)
        WindowNote.note_hwnds -= self._own_hwnds
        try:
            self.top.destroy()
        except tk.TclError:
            pass
