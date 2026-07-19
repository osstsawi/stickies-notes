"""Backend Wayland/KDE: consulta ventanas a traves de un script de KWin.

En Wayland ningun cliente puede enumerar ventanas ajenas: esa informacion la
tiene solo el compositor. KWin permite cargar scripts JavaScript con acceso al
workspace; este backend inyecta uno que, en cada evento relevante (activacion,
movimiento, cambio de titulo, cierre...), envia una foto del estado de todas
las ventanas por DBus a esta app, que sirve las consultas desde esa foto local
sin tocar el bus en el camino caliente (el track de 30 fps).

Los handles de este backend son los `internalId` (UUID) de KWin como string,
no ids X11: conviven sin chocar con los ids numericos que las notas registran
en note_hwnds (las notas son ventanas XWayland override-redirect, que KWin no
gestiona y por tanto nunca aparecen en la foto ni como ventana activa).

Coordenadas: KWin reporta la geometria en coordenadas logicas globales, que
con escala 1.0 coinciden con las que usa Tk via XWayland. Con escala != 1.0
la nota aterrizaria descuadrada; pendiente si algun equipo lo necesita.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

from jeepney import (
    DBusAddress,
    HeaderFields,
    MessageType,
    new_method_call,
    new_method_return,
)
from jeepney.bus_messages import message_bus
from jeepney.io.blocking import open_dbus_connection

from stickies_notes.backend import WindowBackend

BUS_NAME = "org.stickies.Notes"
PLUGIN_NAME = "stickies-notes-bridge"
SCRIPT_FILE = "stickies-notes-kwin.js"

#: Espera maxima a la primera foto tras cargar el script. Si no llega, KWin no
#: ejecuto el puente y el llamador debe caer al backend X11.
FIRST_SNAPSHOT_TIMEOUT_S = 5.0

# El puente que corre DENTRO de KWin. Manda la foto completa en cada evento:
# es pequena (unos KB) y ahorra tener que reconciliar deltas en los dos lados.
KWIN_SCRIPT = """\
// Las notas son ventanas gestionadas en Wayland (necesitan foco de teclado del
// compositor), pero para la app deben ser invisibles: si aparecieran en la
// foto, una nota podria anclarse a otra nota o taparse a si misma.
const PIN = String.fromCodePoint(0x1F4CC);
function isNote(w) {
    return String(w.caption || "").startsWith(PIN);
}

function snapshot(excluded) {
    const aw = workspace.activeWindow;
    const list = [];
    const stack = workspace.stackingOrder;  // de abajo hacia arriba
    for (let i = 0; i < stack.length; ++i) {
        const w = stack[i];
        if (excluded !== undefined && w === excluded) {
            continue;
        }
        if (isNote(w)) {
            continue;
        }
        list.push({
            id: String(w.internalId),
            title: String(w.caption || ""),
            cls: String(w.resourceClass || ""),
            x: Math.round(w.frameGeometry.x),
            y: Math.round(w.frameGeometry.y),
            w: Math.round(w.frameGeometry.width),
            h: Math.round(w.frameGeometry.height),
            min: !!w.minimized,
            normal: !!w.normalWindow,
        });
    }
    callDBus("org.stickies.Notes", "/", "org.stickies.Notes", "Update",
             JSON.stringify({
                 active: aw && aw !== excluded && !isNote(aw)
                     ? String(aw.internalId) : "",
                 windows: list,
             }));
}

// push NO recibe parametros a proposito: los signals de KWin pasan la ventana
// como primer argumento y, si push la aceptara, acabaria excluida de la foto.
function push() {
    snapshot(undefined);
}

function hook(w) {
    if (isNote(w)) {
        return;
    }
    w.frameGeometryChanged.connect(push);
    w.captionChanged.connect(push);
    w.minimizedChanged.connect(push);
}

workspace.windowList().forEach(hook);
workspace.windowAdded.connect(function (w) { hook(w); push(); });
// En windowRemoved la ventana que muere TODAVIA figura en stackingOrder: hay
// que excluirla a mano o la foto final la mantiene viva para siempre y las
// notas nunca detectan el cierre (y no se archivan).
workspace.windowRemoved.connect(function (w) { snapshot(w); });
// Nota: workspace.stackingOrderChanged no existe en KWin 6.7; los cambios de
// apilamiento relevantes llegan igual via windowActivated.
workspace.windowActivated.connect(push);
push();
"""


class KWinBackend(WindowBackend):
    """Backend que lee la foto de ventanas empujada por el script de KWin."""

    wants_managed_notes = True

    def __init__(self) -> None:
        """Levanta el servicio DBus, inyecta el script y espera la primera foto.

        Lanza: RuntimeError si KWin no responde o el puente no llega a mandar
               nada (el llamador cae entonces al backend X11).
        """
        self._lock = threading.Lock()
        self._active: Optional[str] = None
        self._windows: dict = {}
        self._first_snapshot = threading.Event()
        self._closed = False

        # DOS conexiones a proposito. En la de recibir, receive() es la UNICA
        # operacion de lectura: jeepney descarta los mensajes "no relacionados"
        # que llegan durante un send_and_get_reply, y el push inicial del
        # script aterriza exactamente ahi si se comparte la conexion con las
        # llamadas de scripting.
        self._conn_recv = open_dbus_connection(bus="SESSION")
        reply = self._conn_recv.send_and_get_reply(message_bus.RequestName(BUS_NAME))
        if reply.body[0] != 1:  # 1 = somos el dueno primario del nombre
            self._conn_recv.close()
            raise RuntimeError(f"el nombre DBus {BUS_NAME} ya tiene dueno")

        # El hilo receptor arranca ANTES de cargar el script: el push inicial
        # puede llegar en cuanto KWin lo ejecute.
        self._thread = threading.Thread(
            target=self._serve, daemon=True, name="stickies-kwin"
        )
        self._thread.start()

        self._conn_ctl = open_dbus_connection(bus="SESSION")
        try:
            self._load_kwin_script()
        except Exception:
            self.close()
            raise

        if not self._first_snapshot.wait(FIRST_SNAPSHOT_TIMEOUT_S):
            self.close()
            raise RuntimeError("KWin no envio el estado inicial de ventanas")

    # ------------------------------------------------------------- Puente KWin

    def _scripting_call(self, method: str, signature: str = "", body: tuple = (),
                        path: str = "/Scripting", interface: str = "org.kde.kwin.Scripting"):
        addr = DBusAddress(path, bus_name="org.kde.KWin", interface=interface)
        reply = self._conn_ctl.send_and_get_reply(
            new_method_call(addr, method, signature, body)
        )
        if reply.header.message_type == MessageType.error:
            raise RuntimeError(f"KWin {method}: {reply.body}")
        return reply

    def _load_kwin_script(self) -> None:
        """Escribe el puente a disco, lo carga en KWin y lo arranca."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        script_path = Path(runtime_dir) / SCRIPT_FILE
        script_path.write_text(KWIN_SCRIPT, encoding="utf-8")

        # Un puente huerfano de una corrida anterior seguiria empujando al
        # nombre viejo; fuera antes de cargar el nuevo.
        self._scripting_call("unloadScript", "s", (PLUGIN_NAME,))
        reply = self._scripting_call("loadScript", "ss", (str(script_path), PLUGIN_NAME))
        script_id = reply.body[0]
        self._scripting_call(
            "run",
            path=f"/Scripting/Script{script_id}",
            interface="org.kde.kwin.Script",
        )

    def _serve(self) -> None:
        """Recibe las fotos del script de KWin (metodo Update, un JSON)."""
        while True:
            try:
                msg = self._conn_recv.receive()
            except OSError:  # conexion cerrada en close()
                return
            header = msg.header
            if header.message_type != MessageType.method_call:
                continue
            if header.fields.get(HeaderFields.member) != "Update":
                continue
            try:
                snapshot = json.loads(msg.body[0])
            except (ValueError, IndexError):
                continue
            windows = {}
            for i, win in enumerate(snapshot.get("windows", ())):
                win["stack"] = i
                windows[win["id"]] = win
            with self._lock:
                self._active = snapshot.get("active") or None
                self._windows = windows
            self._first_snapshot.set()
            # KWin llama sin esperar respuesta, pero contestar es barato y
            # evita warnings de metodos sin reply en el log del compositor.
            try:
                self._conn_recv.send(new_method_return(msg, "", ()))
            except OSError:
                return

    def close(self) -> None:
        """Descarga el puente de KWin y suelta la conexion DBus."""
        if self._closed:
            return
        self._closed = True
        try:
            self._scripting_call("unloadScript", "s", (PLUGIN_NAME,))
        except Exception:
            pass
        for conn in (getattr(self, "_conn_ctl", None), self._conn_recv):
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------- Consultas

    def _get(self, handle) -> Optional[dict]:
        with self._lock:
            return self._windows.get(handle)

    def get_active_window(self) -> Optional[str]:
        """Devuelve el internalId de la ventana activa segun KWin."""
        with self._lock:
            return self._active

    def is_window(self, handle) -> bool:
        """La ventana existe mientras siga en la ultima foto del compositor."""
        return self._get(handle) is not None

    def get_window_title(self, handle) -> str:
        win = self._get(handle)
        return win["title"] if win else ""

    def get_window_rect(self, handle) -> Optional[Tuple[int, int, int, int]]:
        win = self._get(handle)
        if not win:
            return None
        return (win["x"], win["y"], win["x"] + win["w"], win["y"] + win["h"])

    def is_window_minimized(self, handle) -> bool:
        win = self._get(handle)
        return bool(win and win["min"])

    def is_window_visible(self, handle) -> bool:
        return self._get(handle) is not None

    def get_window_parent(self, handle) -> Optional[int]:
        # Las notas registran aqui sus ids X11; en KWin no aplica el concepto.
        return None

    def get_window_class(self, handle) -> str:
        win = self._get(handle)
        return win["cls"] if win else ""

    def is_shell_window(self, handle) -> bool:
        """Paneles, escritorio y popups de Plasma no son ventanas normales."""
        win = self._get(handle)
        return bool(win) and not win["normal"]
