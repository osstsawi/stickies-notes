#!/usr/bin/env bash
#
# Instala stickies-notes en Linux (X11) con autoinicio via systemd --user.
#
# Uso:
#   ./install_linux.sh                 # instala con autoinicio
#   ./install_linux.sh --no-autostart  # instala sin autoinicio
#   ./install_linux.sh --uninstall     # desinstala (no borra las notas)
#
set -euo pipefail

APP_NAME="stickies-notes"
INSTALL_DIR="${HOME}/.local/share/${APP_NAME}"
SRC_DIR="${INSTALL_DIR}/src"
VENV_DIR="${INSTALL_DIR}/venv"
SERVICE_NAME="${APP_NAME}.service"
SERVICE_PATH="${HOME}/.config/systemd/user/${SERVICE_NAME}"
DESKTOP_PATH="${HOME}/.config/autostart/${APP_NAME}.desktop"

KDE_APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_NEW="${KDE_APPS_DIR}/stickies-notes-new.desktop"
DESKTOP_QUIT="${KDE_APPS_DIR}/stickies-notes-quit.desktop"
DESKTOP_APP="${KDE_APPS_DIR}/stickies-notes.desktop"

# Codigos de tecla Qt: Ctrl=0x04000000 + Alt=0x08000000 + letra ASCII.
QTKEY_CTRL_ALT_N=201326670  # 0x0C00004E
QTKEY_CTRL_ALT_Q=201326673  # 0x0C000051

NO_AUTOSTART=0
UNINSTALL=0

for arg in "$@"; do
    case "$arg" in
        --no-autostart) NO_AUTOSTART=1 ;;
        --uninstall)    UNINSTALL=1 ;;
        *) echo "Opcion desconocida: $arg" >&2; exit 1 ;;
    esac
done

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
have_user_systemd() { command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; }
kde_wayland() { [[ "${XDG_SESSION_TYPE:-}" == "wayland" && "${XDG_CURRENT_DESKTOP:-}" == *KDE* ]]; }

# Registra en kglobalaccel (KDE) un atajo que lanza un .desktop. Es la via que
# funciona en Wayland: el compositor captura la combinacion y ejecuta
# `python -m stickies_notes new|quit`, que llega a la instancia viva por su
# socket de control. En X11 no hace falta (pynput captura directo).
kglobal_bind() {  # $1=archivo.desktop  $2=descripcion  $3=keycode Qt
    local action="['$1','_launch','stickies-notes','$2']"
    gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.doRegister "$action" >/dev/null
    gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.setShortcut "$action" "[$3]" 4 >/dev/null
}

kglobal_unbind() {  # $1=archivo.desktop
    gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.unregister "$1" "_launch" >/dev/null 2>&1 || true
}

if [[ "$UNINSTALL" -eq 1 ]]; then
    step "Desinstalando ${APP_NAME}..."
    if have_user_systemd && [[ -f "$SERVICE_PATH" ]]; then
        systemctl --user disable --now "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SERVICE_PATH"
        systemctl --user daemon-reload 2>/dev/null || true
        echo "    Servicio systemd eliminado."
    fi
    [[ -f "$DESKTOP_PATH" ]] && rm -f "$DESKTOP_PATH" && echo "    Autostart XDG eliminado."
    if [[ -f "$DESKTOP_NEW" || -f "$DESKTOP_QUIT" ]]; then
        command -v gdbus >/dev/null 2>&1 && { kglobal_unbind "stickies-notes-new.desktop"; kglobal_unbind "stickies-notes-quit.desktop"; }
        rm -f "$DESKTOP_NEW" "$DESKTOP_QUIT"
        echo "    Atajos KDE eliminados."
    fi
    [[ -f "$DESKTOP_APP" ]] && rm -f "$DESKTOP_APP" && echo "    Entrada del menu eliminada."
    [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR" && echo "    Codigo y venv eliminados."
    echo
    echo -e "\033[32mListo. Tus notas archivadas NO se tocaron.\033[0m"
    exit 0
fi

step "Verificando requisitos..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "Falta python3. Instalalo con:  sudo apt install python3" >&2
    exit 1
fi
if ! python3 -c "import venv" >/dev/null 2>&1; then
    echo "Falta el modulo venv. Instalalo con:  sudo apt install python3-venv" >&2
    exit 1
fi
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Falta tkinter. Instalalo con:  sudo apt install python3-tk" >&2
    exit 1
fi
echo "    $(python3 --version)"

if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    echo
    echo -e "\033[33mAviso: estas en Wayland.\033[0m"
    echo "  stickies-notes consulta las ventanas via X11. En Wayland puro no puede"
    echo "  leer la ventana activa ni su posicion. Usa una sesion X11 (Xorg), o"
    echo "  acepta que solo funcionara con aplicaciones corriendo bajo XWayland."
    echo
fi

step "Copiando codigo a ${SRC_DIR}..."
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -d "${REPO_ROOT}/src" ]]; then
    echo "No se encontro la carpeta 'src' en ${REPO_ROOT}." >&2
    exit 1
fi
rm -rf "$SRC_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "${REPO_ROOT}/src" "$SRC_DIR"
# El icono de bandeja: tray.py lo busca en <raiz>/build/icon.ico relativo al
# codigo; sin esta copia cae al cuadrado amarillo liso de respaldo. El .png lo
# usa la entrada del menu de aplicaciones.
mkdir -p "${INSTALL_DIR}/build"
cp "${REPO_ROOT}/build/icon.ico" "${INSTALL_DIR}/build/icon.ico"
cp "${REPO_ROOT}/build/icon.png" "${INSTALL_DIR}/build/icon.png"

step "Creando entrada en el menu de aplicaciones..."
mkdir -p "$KDE_APPS_DIR"
# El Exec pasa por systemd cuando existe la unidad: asi la app lanzada desde el
# menu queda administrada y sus mensajes caen al journal (lanzada directa, su
# stdout se pierde y no hay forma de diagnosticarla).
cat > "$DESKTOP_APP" <<EOF
[Desktop Entry]
Type=Application
Name=Stickies Notes
Comment=Notas adhesivas ancladas a ventanas
Exec=sh -c "systemctl --user start stickies-notes.service 2>/dev/null || exec '${VENV_DIR}/bin/python' -m stickies_notes"
Path=${SRC_DIR}
Icon=${INSTALL_DIR}/build/icon.png
Categories=Utility;
Terminal=false
StartupNotify=false
EOF
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true

step "Creando entorno virtual..."
[[ -d "$VENV_DIR" ]] || python3 -m venv --system-site-packages "$VENV_DIR"

step "Instalando dependencias (python-xlib, pynput, pystray, pillow, jeepney)..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip --quiet
"${VENV_DIR}/bin/python" -m pip install --quiet python-xlib pynput pystray pillow jeepney

if [[ "$NO_AUTOSTART" -eq 0 ]]; then
    if have_user_systemd; then
        step "Registrando autoinicio (systemd --user)..."
        mkdir -p "$(dirname "$SERVICE_PATH")"
        cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=stickies-notes — notas adhesivas ancladas a ventanas
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory=${SRC_DIR}
# Sin esto Python bufferiza stdout (no es TTY) y los mensajes de diagnostico
# nunca llegan al journal.
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python -m stickies_notes
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable "$SERVICE_NAME"
        # restart y no `enable --now`: en una reinstalacion el servicio ya esta
        # activo y hay que recargar el codigo recien copiado.
        systemctl --user restart "$SERVICE_NAME"
        echo "    Servicio ${SERVICE_NAME} activo."
    else
        step "Sin systemd de usuario: usando autostart XDG..."
        mkdir -p "$(dirname "$DESKTOP_PATH")"
        cat > "$DESKTOP_PATH" <<EOF
[Desktop Entry]
Type=Application
Name=stickies-notes
Comment=Notas adhesivas ancladas a ventanas
Exec=${VENV_DIR}/bin/python -m stickies_notes
Path=${SRC_DIR}
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
        echo "    ${DESKTOP_PATH}"
    fi
else
    step "Autoinicio omitido (--no-autostart)."
fi

if kde_wayland; then
    if command -v gdbus >/dev/null 2>&1; then
        step "Registrando atajos globales en KDE (Wayland via kglobalaccel)..."
        mkdir -p "$KDE_APPS_DIR"
        cat > "$DESKTOP_NEW" <<EOF
[Desktop Entry]
Type=Application
Name=stickies-notes: nueva nota
Exec=${VENV_DIR}/bin/python -m stickies_notes new
Path=${SRC_DIR}
NoDisplay=true
Terminal=false
EOF
        cat > "$DESKTOP_QUIT" <<EOF
[Desktop Entry]
Type=Application
Name=stickies-notes: archivar todo y salir
Exec=${VENV_DIR}/bin/python -m stickies_notes quit
Path=${SRC_DIR}
NoDisplay=true
Terminal=false
EOF
        kglobal_bind "stickies-notes-new.desktop"  "Nueva nota"              "$QTKEY_CTRL_ALT_N"
        kglobal_bind "stickies-notes-quit.desktop" "Archivar todo y salir"   "$QTKEY_CTRL_ALT_Q"
        echo "    Ctrl+Alt+N y Ctrl+Alt+Q registrados en el compositor."
    else
        echo "    Sesion KDE Wayland sin gdbus: asigna Ctrl+Alt+N a"
        echo "    '${VENV_DIR}/bin/python -m stickies_notes new' en Preferencias > Atajos."
    fi
fi

echo
echo -e "\033[32mInstalacion completa.\033[0m"
echo
echo "  Arrancar ahora:  cd '${SRC_DIR}' && '${VENV_DIR}/bin/python' -m stickies_notes"
echo "  Nueva nota:      Ctrl+Alt+N"
echo "  Salir:           Ctrl+Alt+Q"
echo "  Notas en:        ${HOME}/StickiesNotes"
echo
