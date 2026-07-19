"""Punto de entrada del paquete: `python -m stickies_notes [new|quit]`.

Sin argumentos arranca la aplicacion. Con `new` o `quit` reenvia la orden a la
instancia en marcha por el socket de control (lo usan los atajos globales del
escritorio en Wayland) — solo carga stdlib, sin tocar Tkinter, para que el
disparo sea instantaneo.
"""

import sys


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
