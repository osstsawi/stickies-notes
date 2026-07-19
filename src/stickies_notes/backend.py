"""Abstraccion del sistema operativo para consultar ventanas.

Cada backend expone la misma interfaz sobre un identificador opaco de ventana
(HWND en Windows, window id de X11 en Linux). Los imports especificos de cada
SO son diferidos para que el modulo se pueda importar en cualquier plataforma.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Optional, Tuple

# DPI de referencia de Windows: 96 = escala 100%.
BASE_DPI = 96


def enable_dpi_awareness() -> None:
    """Declara el proceso "per-monitor DPI aware" en Windows. No-op fuera de el.

    Hay que llamarla ANTES de crear la ventana raiz de Tk.

    Por que importa: a un proceso que no lo declara, Windows le MIENTE. Le
    entrega coordenadas virtualizadas a la escala del monitor principal, asi que
    en cuanto una ventana pasa a un monitor con otra escala, lo que devuelve
    GetWindowRect deja de coincidir con las coordenadas reales de pantalla y la
    nota aterriza descuadrada. Declarandose per-monitor v2, las coordenadas son
    fisicas y reales en todos los monitores.

    A cambio, Windows ya no reescala la ventana por nosotros: el tamano y las
    fuentes de la nota se escalan a mano con get_window_dpi() (ver note.py).
    """
    if sys.platform != "win32":
        return

    import ctypes

    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (Windows 10 1703+).
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass

    # PROCESS_PER_MONITOR_DPI_AWARE (Windows 8.1+).
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass

    # Ultimo recurso: system-aware (Vista+). Mejor que nada.
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


class WindowBackend(ABC):
    """Interfaz comun para consultar ventanas del sistema operativo."""

    @abstractmethod
    def get_active_window(self) -> Optional[int]:
        """Devuelve el handle de la ventana activa, o None si no hay ninguna."""

    @abstractmethod
    def is_window(self, handle: int) -> bool:
        """Indica si el handle sigue correspondiendo a una ventana viva.

        Recibe: handle de ventana.
        Devuelve: True si la ventana existe, False si ya se cerro.
        """

    @abstractmethod
    def get_window_title(self, handle: int) -> str:
        """Devuelve el titulo de la ventana, o cadena vacia si no se puede leer."""

    @abstractmethod
    def get_window_rect(self, handle: int) -> Optional[Tuple[int, int, int, int]]:
        """Devuelve (left, top, right, bottom) en coordenadas absolutas de pantalla.

        Recibe: handle de ventana.
        Devuelve: la tupla del rectangulo, o None si la ventana ya no existe.
        """

    @abstractmethod
    def is_window_minimized(self, handle: int) -> bool:
        """Indica si la ventana esta minimizada."""

    @abstractmethod
    def is_window_visible(self, handle: int) -> bool:
        """Indica si la ventana esta mapeada/visible (no oculta)."""

    @abstractmethod
    def get_window_parent(self, handle: int) -> Optional[int]:
        """Devuelve el handle del padre de la ventana, o None si no tiene."""

    @abstractmethod
    def get_window_class(self, handle: int) -> str:
        """Devuelve el nombre de clase de la ventana, o "" si no se puede leer."""

    def get_window_dpi(self, handle: int) -> int:
        """Devuelve el DPI del monitor donde vive la ventana (96 = 100%)."""
        return BASE_DPI

    def is_shell_window(self, handle: int) -> bool:
        """Indica si el handle es parte del escritorio/barra de tareas del SO.

        Sirve para no anclar notas a la barra de tareas ni al escritorio, que es
        lo que pasa a estar en primer plano al abrir el menu de la bandeja.
        """
        return self.get_window_class(handle) in self.SHELL_CLASSES

    #: Clases de ventana que pertenecen al escritorio o la barra de tareas.
    SHELL_CLASSES: frozenset = frozenset()


class WinBackend(WindowBackend):
    """Backend de Windows basado en win32gui (pywin32)."""

    SHELL_CLASSES = frozenset(
        {
            "Shell_TrayWnd",  # barra de tareas
            "Shell_SecondaryTrayWnd",  # barra de tareas de monitores extra
            "Progman",  # escritorio
            "WorkerW",  # escritorio (con fondo animado)
            "NotifyIconOverflowWindow",  # bandeja desplegada
            "TopLevelWindowForOverflowXamlIsland",  # bandeja desplegada (Win11)
            "Windows.UI.Core.CoreWindow",  # menu inicio / centro de notificaciones
            "XamlExplorerHostIslandWindow",  # Alt+Tab / vista de tareas (Win11)
            "ForegroundStaging",  # ventana transitoria del cambio de foco
        }
    )

    def __init__(self) -> None:
        """Importa win32gui de forma diferida para no romper en Linux."""
        import ctypes

        import win32gui  # import diferido: solo existe en Windows

        self._win32gui = win32gui
        self._user32 = ctypes.windll.user32

    def get_active_window(self) -> Optional[int]:
        """Devuelve el HWND en primer plano, o None si no hay ventana activa."""
        handle = self._win32gui.GetForegroundWindow()
        return handle or None

    def is_window(self, handle: int) -> bool:
        """Indica si el HWND sigue siendo una ventana valida."""
        return bool(self._win32gui.IsWindow(handle))

    def get_window_title(self, handle: int) -> str:
        """Devuelve el texto de la barra de titulo del HWND."""
        try:
            return self._win32gui.GetWindowText(handle) or ""
        except Exception:
            return ""

    def get_window_rect(self, handle: int) -> Optional[Tuple[int, int, int, int]]:
        """Devuelve el rectangulo del HWND, o None si la ventana desaparecio."""
        try:
            return self._win32gui.GetWindowRect(handle)
        except Exception:
            return None

    def is_window_minimized(self, handle: int) -> bool:
        """Indica si el HWND esta minimizado (iconificado)."""
        try:
            return bool(self._win32gui.IsIconic(handle))
        except Exception:
            return False

    def is_window_visible(self, handle: int) -> bool:
        """Indica si el HWND tiene el flag de visible."""
        try:
            return bool(self._win32gui.IsWindowVisible(handle))
        except Exception:
            return False

    def get_window_parent(self, handle: int) -> Optional[int]:
        """Devuelve el HWND padre, o None si la ventana es de nivel superior."""
        try:
            return self._win32gui.GetParent(handle) or None
        except Exception:
            return None

    def get_window_class(self, handle: int) -> str:
        """Devuelve el nombre de clase del HWND (ej. "Shell_TrayWnd")."""
        try:
            return self._win32gui.GetClassName(handle) or ""
        except Exception:
            return ""

    def get_window_dpi(self, handle: int) -> int:
        """Devuelve el DPI del monitor donde esta el HWND (96 = escala 100%).

        GetDpiForWindow existe desde Windows 10 1607; en versiones anteriores
        se cae al DPI base, que es exactamente el comportamiento de antes.
        """
        try:
            dpi = int(self._user32.GetDpiForWindow(handle))
            return dpi or BASE_DPI
        except (AttributeError, OSError, ValueError):
            return BASE_DPI


class X11Backend(WindowBackend):
    """Backend de Linux/X11 basado en python-xlib."""

    def __init__(self) -> None:
        """Abre la conexion con el servidor X y cachea los atomos que se usan."""
        from Xlib import X, display, error  # import diferido: solo en Linux

        self._X = X
        self._error = error
        self._display = display.Display()
        self._root = self._display.screen().root
        self._net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        self._net_wm_name = self._display.intern_atom("_NET_WM_NAME")
        self._utf8_string = self._display.intern_atom("UTF8_STRING")
        self._wm_state = self._display.intern_atom("WM_STATE")
        self._net_wm_state = self._display.intern_atom("_NET_WM_STATE")
        self._net_wm_state_hidden = self._display.intern_atom("_NET_WM_STATE_HIDDEN")

    def _window_obj(self, handle: int):
        """Devuelve el objeto ventana de Xlib para un id, o None si falla."""
        try:
            return self._display.create_resource_object("window", handle)
        except Exception:
            return None

    def get_active_window(self) -> Optional[int]:
        """Lee _NET_ACTIVE_WINDOW del root para saber que ventana tiene el foco."""
        try:
            prop = self._root.get_full_property(
                self._net_active_window, self._X.AnyPropertyType
            )
        except self._error.XError:
            return None
        if not prop or not prop.value:
            return None
        handle = int(prop.value[0])
        return handle or None

    def is_window(self, handle: int) -> bool:
        """Comprueba la existencia pidiendo los atributos y capturando XError."""
        window = self._window_obj(handle)
        if window is None:
            return False
        try:
            window.get_attributes()
            return True
        except self._error.XError:
            return False
        except Exception:
            return False

    def get_window_title(self, handle: int) -> str:
        """Lee _NET_WM_NAME (UTF8) con fallback a get_wm_name()."""
        window = self._window_obj(handle)
        if window is None:
            return ""
        try:
            prop = window.get_full_property(self._net_wm_name, self._utf8_string)
            if prop and prop.value:
                value = prop.value
                if isinstance(value, bytes):
                    return value.decode("utf-8", "replace")
                return str(value)
            name = window.get_wm_name()
            if isinstance(name, bytes):
                return name.decode("utf-8", "replace")
            return name or ""
        except self._error.XError:
            return ""
        except Exception:
            return ""

    def get_window_rect(self, handle: int) -> Optional[Tuple[int, int, int, int]]:
        """Traduce la geometria de la ventana a coordenadas absolutas de pantalla."""
        window = self._window_obj(handle)
        if window is None:
            return None
        try:
            geom = window.get_geometry()
            coords = self._root.translate_coords(window, 0, 0)
            left = coords.x
            top = coords.y
            return (left, top, left + geom.width, top + geom.height)
        except self._error.XError:
            return None
        except Exception:
            return None

    def is_window_minimized(self, handle: int) -> bool:
        """Detecta iconificacion por WM_STATE == IconicState o _NET_WM_STATE_HIDDEN."""
        window = self._window_obj(handle)
        if window is None:
            return False
        try:
            prop = window.get_full_property(self._wm_state, self._X.AnyPropertyType)
            if prop and prop.value and int(prop.value[0]) == 3:  # IconicState
                return True
            prop = window.get_full_property(self._net_wm_state, self._X.AnyPropertyType)
            if prop and prop.value and self._net_wm_state_hidden in list(prop.value):
                return True
            return False
        except self._error.XError:
            return False
        except Exception:
            return False

    def is_window_visible(self, handle: int) -> bool:
        """Indica si la ventana esta mapeada y es visible (IsViewable)."""
        window = self._window_obj(handle)
        if window is None:
            return False
        try:
            return window.get_attributes().map_state == self._X.IsViewable
        except self._error.XError:
            return False
        except Exception:
            return False

    def get_window_parent(self, handle: int) -> Optional[int]:
        """Devuelve el id del padre segun el arbol de ventanas de X."""
        window = self._window_obj(handle)
        if window is None:
            return None
        try:
            parent = window.query_tree().parent
            if parent and parent.id != self._root.id:
                return int(parent.id)
            return None
        except self._error.XError:
            return None
        except Exception:
            return None

    def get_window_class(self, handle: int) -> str:
        """Devuelve la clase de WM_CLASS (el segundo campo, el de la app)."""
        window = self._window_obj(handle)
        if window is None:
            return ""
        try:
            wm_class = window.get_wm_class()
            if wm_class and len(wm_class) > 1:
                return str(wm_class[1])
            return ""
        except self._error.XError:
            return ""
        except Exception:
            return ""


def get_backend() -> WindowBackend:
    """Instancia el backend que corresponde al sistema y la sesion actuales.

    Devuelve: WinBackend en Windows; en Linux, KWinBackend si la sesion es
              KDE sobre Wayland (con caida a X11Backend si el puente falla),
              y X11Backend en el resto.
    Lanza: RuntimeError si la plataforma no esta soportada.
    """
    if sys.platform == "win32":
        return WinBackend()
    if sys.platform.startswith("linux"):
        import os

        # En Wayland el backend X11 solo ve ventanas XWayland: la ventana
        # activa nativa le es invisible y la nota nunca aparece. En KDE la
        # informacion se obtiene del compositor via script de KWin.
        if os.environ.get("WAYLAND_DISPLAY") and "KDE" in os.environ.get(
            "XDG_CURRENT_DESKTOP", ""
        ):
            try:
                from stickies_notes.kwin import KWinBackend

                backend = KWinBackend()
                print("[stickies-notes] Backend: KWin (Wayland/KDE)")
                return backend
            except Exception as exc:
                print(
                    f"[stickies-notes] Puente KWin no disponible ({exc}); "
                    "usando X11 (solo vera ventanas XWayland)."
                )
        return X11Backend()
    raise RuntimeError(f"Plataforma no soportada: {sys.platform}")
