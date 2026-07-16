# stickies-notes

Notas adhesivas que se anclan a una **ventana individual** del sistema operativo
—no a una aplicación ni a un proceso—. La nota flota siempre encima, sigue a la
ventana cuando se mueve, y **se archiva sola a un archivo Markdown** cuando esa
ventana se cierra.

**El caso de uso:** mientras una herramienta trabaja en una ventana (por ejemplo
Claude en el navegador), vas anotando en la nota lo que quieres revisar después.
Al cerrar esa ventana, la nota queda guardada con su fecha y el título de la
ventana. Nada que recordar guardar.

## Cómo funciona

El anclaje es por **handle de ventana**: `HWND` en Windows, *window id* de X11 en
Linux. Eso significa que dos ventanas del mismo programa tienen notas separadas
—dos pestañas del navegador en ventanas distintas, dos terminales, dos Excel—.

Cada 300 ms la nota consulta si su ventana sigue viva. Cuando desaparece, la nota
se archiva y se destruye.

## Requisitos

- **Python 3.9+** con `tkinter`.
- **Windows 10/11:** `pywin32` y `keyboard`.
- **Linux con X11:** `python-xlib` y `pynput`.

> **Wayland:** la app consulta las ventanas por X11. En una sesión Wayland pura no
> puede leer la ventana activa ni su posición; funciona solo con aplicaciones bajo
> XWayland. Para uso real, usa una sesión Xorg.

## Instalación

### Windows

```powershell
git clone https://github.com/osstsawi/stickies-notes.git
cd stickies-notes
.\installers\install_windows.ps1
```

Copia el código a `%LOCALAPPDATA%\StickiesNotes`, crea el venv con sus
dependencias y deja la app arrancando con Windows **sin ventana de consola**.

Opciones: `-NoAutostart` para instalar sin autoinicio, `-Uninstall` para quitarla.

### Linux (X11)

```bash
git clone https://github.com/osstsawi/stickies-notes.git
cd stickies-notes
./installers/install_linux.sh
```

Copia el código a `~/.local/share/stickies-notes`, crea el venv y registra un
servicio **systemd `--user`** (con fallback a autostart XDG si no hay systemd de
usuario).

Opciones: `--no-autostart`, `--uninstall`.

Si falta algo del sistema, el instalador te dice qué instalar:

```bash
sudo apt install python3 python3-venv python3-tk
```

### Sin instalador

```bash
pip install -e .
python -m stickies_notes
```

## Hotkeys

| Atajo | Qué hace |
|---|---|
| `Ctrl+Alt+N` | Crea una nota anclada a la ventana activa, o enfoca la que ya tenga |
| `Ctrl+Alt+Q` | Archiva todas las notas abiertas y cierra la app |
| `✕` en la nota | Archiva esa nota manualmente |

La nota se arrastra desde su barra amarilla. Si la mueves a mano, recuerda esa
posición relativa y la mantiene mientras la ventana se desplaza.

## Dónde quedan las notas

| Sistema | Ruta por defecto |
|---|---|
| Windows | `~\Documents\StickiesNotes` |
| Linux | `~/StickiesNotes` |

Se cambia con la variable de entorno `STICKIES_NOTES_DIR`.

El nombre de archivo es `AAAA-MM-DD_HHMMSS__<título de la ventana>.md`, y dentro
lleva una cabecera con cuándo se creó, cuándo se archivó y por qué:

```markdown
# Presupuesto 2026 — Excel

- **Creada:** 2026-07-16 09:14:02
- **Archivada:** 2026-07-16 11:40:37
- **Motivo:** la ventana anclada se cerro

---

Revisar la fila 42, el total no cuadra con el resumen.
```

Las notas vacías no generan archivo.

## Compilar a `.exe`

```powershell
.\build\build_exe.ps1
```

Deja el binario en `dist\StickiesNotes.exe`, sin necesidad de Python instalado en
la máquina destino. Con el `.exe` el autoinicio no necesita el `.vbs`: basta un
acceso directo en `shell:startup`, porque se compila en modo `--windowed`.

Dos avisos que valen la pena:

- **Antivirus:** el hook global de teclado + un binario sin firmar disparan falsos
  positivos en Defender y SmartScreen. Para uso propio se permite a mano; para
  distribuirlo, hay que firmarlo.
- **Rutas con tildes:** el modo `--onefile` se descomprime en `%TEMP%` en cada
  arranque y puede fallar si tu usuario lleva acentos. Usa `--onedir` o apunta
  `TMP`/`TEMP` a una ruta ASCII.

## Desinstalación

```powershell
.\installers\install_windows.ps1 -Uninstall   # Windows
```

```bash
./installers/install_linux.sh --uninstall     # Linux
```

Ninguno de los dos toca tus notas archivadas.

## Licencia

MIT — ver [LICENSE](LICENSE).
