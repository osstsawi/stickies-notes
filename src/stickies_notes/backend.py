"""Abstraccion del sistema operativo para consultar ventanas.

Cada backend expone la misma interfaz sobre un identificador opaco de ventana
(HWND en Windows, window id de X11 en Linux). Los imports especificos de cada
SO son diferidos para que el modulo se pueda importar en cualquier plataforma.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Optional, Tuple


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


class WinBackend(WindowBackend):
    """Backend de Windows basado en win32gui (pywin32)."""

    def __init__(self) -> None:
        """Importa win32gui de forma diferida para no romper en Linux."""
        import win32gui  # import diferido: solo existe en Windows

        self._win32gui = win32gui

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


def get_backend() -> WindowBackend:
    """Instancia el backend que corresponde al sistema operativo actual.

    Devuelve: WinBackend en Windows, X11Backend en Linux.
    Lanza: RuntimeError si la plataforma no esta soportada.
    """
    if sys.platform == "win32":
        return WinBackend()
    if sys.platform.startswith("linux"):
        return X11Backend()
    raise RuntimeError(f"Plataforma no soportada: {sys.platform}")
