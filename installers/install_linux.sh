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

if [[ "$UNINSTALL" -eq 1 ]]; then
    step "Desinstalando ${APP_NAME}..."
    if have_user_systemd && [[ -f "$SERVICE_PATH" ]]; then
        systemctl --user disable --now "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SERVICE_PATH"
        systemctl --user daemon-reload 2>/dev/null || true
        echo "    Servicio systemd eliminado."
    fi
    [[ -f "$DESKTOP_PATH" ]] && rm -f "$DESKTOP_PATH" && echo "    Autostart XDG eliminado."
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

step "Creando entorno virtual..."
[[ -d "$VENV_DIR" ]] || python3 -m venv --system-site-packages "$VENV_DIR"

step "Instalando dependencias (python-xlib, pynput, pystray, pillow)..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip --quiet
"${VENV_DIR}/bin/python" -m pip install --quiet python-xlib pynput pystray pillow

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
ExecStart=${VENV_DIR}/bin/python -m stickies_notes
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now "$SERVICE_NAME"
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

echo
echo -e "\033[32mInstalacion completa.\033[0m"
echo
echo "  Arrancar ahora:  cd '${SRC_DIR}' && '${VENV_DIR}/bin/python' -m stickies_notes"
echo "  Nueva nota:      Ctrl+Alt+N"
echo "  Salir:           Ctrl+Alt+Q"
echo "  Notas en:        ${HOME}/StickiesNotes"
echo
