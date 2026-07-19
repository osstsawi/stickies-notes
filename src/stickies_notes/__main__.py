"""Punto de entrada del paquete: `python -m stickies_notes [new|quit]`.

Sin argumentos arranca la aplicacion. Con `new` o `quit` reenvia la orden a la
instancia en marcha por el socket de control (lo usan los atajos globales del
escritorio en Wayland) — solo carga stdlib, sin tocar Tkinter, para que el
disparo sea instantaneo.
"""

import sys


def _start_app() -> bool:
    """Arranca la aplicacion en segundo plano.

    Prefiere el servicio systemd (que es como la administra el instalador);
    si no existe, lanza el proceso suelto y desligado de esta terminal.
    Devuelve: True si el arranque se pudo iniciar.
    """
    import shutil
    import subprocess

    if shutil.which("systemctl"):
        result = subprocess.run(
            ["systemctl", "--user", "start", "stickies-notes.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True
    try:
        subprocess.Popen(
            [sys.executable, "-m", "stickies_notes"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def _send_with_retry(command: str, timeout_s: float = 10.0) -> bool:
    """Reintenta enviar la orden mientras la app recien lanzada arranca."""
    import time

    from stickies_notes import ipc

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(0.25)
        if ipc.send(command):
            return True
    return False


def _cli() -> None:
    args = sys.argv[1:]
    if args:
        command = args[0]
        from stickies_notes import ipc

        if command not in ipc.COMMANDS:
            print(
                f"Uso: python -m stickies_notes [{'|'.join(ipc.COMMANDS)}]",
                file=sys.stderr,
            )
            sys.exit(2)
        if not ipc.send(command):
            # Sin instancia viva, `new` la arranca y reintenta: asi el atajo
            # global sigue funcionando despues de salir con Ctrl+Alt+Q.
            if command == "new" and _start_app() and _send_with_retry(command):
                return
            print(
                "[stickies-notes] No hay ninguna instancia en marcha.",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    from stickies_notes.manager import main

    main()


if __name__ == "__main__":
    _cli()
