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

## Instalación en Windows — descargar y usar

**No necesitas Python.** Descarga el instalador de la
[última versión](https://github.com/osstsawi/stickies-notes/releases/latest),
ejecútalo y listo:

| Descarga | Qué es |
|---|---|
| **`StickiesNotes-Setup.exe`** | Instalador normal: asistente, acceso directo, autoinicio opcional y desinstalador en *Agregar o quitar programas*. **Empieza por aquí.** |
| `StickiesNotes.exe` | Portable: un solo archivo, no instala nada, lo ejecutas y ya. Para llevar en un USB. |

El instalador no pide permisos de administrador: instala solo para tu usuario en
`%LOCALAPPDATA%\Programs\StickiesNotes`.

> **SmartScreen / antivirus.** Al abrirlo puede que Windows lo bloquee con un
> aviso de editor desconocido, y que Defender lo marque. Es esperable: la app
> instala un hook global de teclado (así detecta `Ctrl+Alt+N` desde cualquier
> ventana) y el binario no está firmado, porque firmarlo cuesta un certificado de
> pago. Para permitirlo: *Más información* → *Ejecutar de todas formas*. Si no te
> fías del binario —lo cual es razonable—, compílalo tú mismo con
> `.\build\build_exe.ps1`, o revisa el
> [workflow](.github/workflows/build.yml) que lo construye desde este código.

### Compilar el instalador tú mismo

Necesitas Python 3.9+ y [Inno Setup 6](https://jrsoftware.org/isdl.php):

```powershell
git clone https://github.com/osstsawi/stickies-notes.git
cd stickies-notes
.\build\build_exe.ps1
```

Deja en `dist\` el instalador, el portable y el build `--onedir`. Es el mismo
script que corre el CI, así que produce exactamente lo que se publica.

### Instalar desde el código (con Python)

Si prefieres correrlo desde las fuentes, `.\installers\install_windows.ps1` copia
el código a `%LOCALAPPDATA%\StickiesNotes`, crea un venv con sus dependencias y
deja la app arrancando con Windows sin ventana de consola. Opciones:
`-NoAutostart`, `-Uninstall`.

## Instalación en Linux (X11)

En Linux no hay binario precompilado: se instala desde el código. Necesitas
**Python 3.9+** con `tkinter`; el instalador añade `python-xlib` y `pynput` en su
propio venv.

> **Wayland:** la app consulta las ventanas por X11. En una sesión Wayland pura no
> puede leer la ventana activa ni su posición; funciona solo con aplicaciones bajo
> XWayland. Para uso real, usa una sesión Xorg. El instalador te avisa si detecta
> Wayland.

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

## Cómo se empaqueta

`build\build_exe.ps1` produce las tres salidas de Windows con PyInstaller +
Inno Setup, y es lo que corre el CI en cada push:

| Salida | Modo | Para qué |
|---|---|---|
| `dist\StickiesNotes-Setup.exe` | Inno Setup | El instalador que se publica |
| `dist\StickiesNotes.exe` | `--onefile` | El portable de un solo archivo |
| `dist\StickiesNotes\` | `--onedir` | Lo que el instalador empaqueta dentro |

El instalador usa el build `--onedir` a propósito: `--onefile` se descomprime en
`%TEMP%` en **cada** arranque, lo que cuesta tiempo y falla si la ruta de `%TEMP%`
lleva caracteres no ASCII (usuarios con tildes en el nombre). Una vez instalado no
hay razón para pagar ese precio. El portable sí sigue en `--onefile`, porque ahí
el archivo único es justamente la gracia — si te da problemas por tildes, usa el
instalador o apunta `TMP`/`TEMP` a una ruta ASCII.

El icono (`build\icon.ico`) va versionado; se regenera con
`python build\make_icon.py` (requiere Pillow, que no es dependencia de la app).

## Desinstalación

Si usaste el instalador: **Configuración → Aplicaciones → stickies-notes →
Desinstalar**, como cualquier programa de Windows.

Desde el código:

```powershell
.\installers\install_windows.ps1 -Uninstall   # Windows
```

```bash
./installers/install_linux.sh --uninstall     # Linux
```

Ninguna de las tres vías toca tus notas archivadas.

## Licencia

MIT — ver [LICENSE](LICENSE).
