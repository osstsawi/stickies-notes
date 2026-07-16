#!/usr/bin/env python3
"""Genera build/icon.ico: una nota adhesiva amarilla con la esquina doblada.

El .ico va versionado en el repo, asi que este script solo hace falta si se
quiere retocar el icono. Requiere Pillow (no es dependencia de la app):

    pip install pillow
    python build/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

# Mismos colores que la nota real (note.py).
COLOR_HEADER = (245, 213, 71)
COLOR_PAPER = (255, 248, 196)
COLOR_LINE = (198, 168, 60)
COLOR_FOLD = (222, 190, 90)
COLOR_SHADOW = (0, 0, 0, 40)

# Se dibuja grande y se reduce: sale con antialiasing gratis.
CANVAS = 1024
SIZES = [16, 32, 48, 64, 128, 256]


def draw_note(size: int) -> Image.Image:
    """Dibuja la nota adhesiva en un lienzo cuadrado RGBA.

    Recibe: el lado del lienzo en pixeles.
    Devuelve: la imagen RGBA con la nota centrada.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    m = size * 0.09          # margen exterior
    left, top = m, m
    right, bottom = size - m, size - m
    fold = size * 0.28       # tamano de la esquina doblada
    radius = size * 0.045

    # Sombra suelta bajo la nota.
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [left + size * 0.02, top + size * 0.03, right + size * 0.02, bottom + size * 0.03],
        radius=radius,
        fill=COLOR_SHADOW,
    )
    img.alpha_composite(shadow)

    # Cuerpo color papel, con la esquina inferior derecha recortada.
    body = [
        (left, top),
        (right, top),
        (right, bottom - fold),
        (right - fold, bottom),
        (left, bottom),
    ]
    d.polygon(body, fill=COLOR_PAPER)
    d.rounded_rectangle([left, top, right, top + size * 0.2], radius=radius, fill=COLOR_HEADER)
    d.rectangle([left, top + size * 0.1, right, top + size * 0.2], fill=COLOR_HEADER)

    # Renglones escritos: sugieren texto sin depender de una fuente.
    line_x0 = left + size * 0.10
    line_h = max(1, int(size * 0.028))
    for i, width_factor in enumerate((0.62, 0.72, 0.48)):
        y = top + size * 0.31 + i * size * 0.13
        d.rounded_rectangle(
            [line_x0, y, line_x0 + (right - left) * width_factor, y + line_h],
            radius=line_h / 2,
            fill=COLOR_LINE,
        )

    # La esquina doblada, que es lo que lo hace leer como "sticky note".
    d.polygon(
        [(right - fold, bottom), (right, bottom - fold), (right - fold, bottom - fold)],
        fill=COLOR_FOLD,
    )
    return img


def main() -> None:
    """Genera el .ico multi-resolucion junto a este script."""
    master = draw_note(CANVAS)
    out = Path(__file__).parent / "icon.ico"
    # La imagen base debe ser la MAYOR: Pillow genera el resto reduciendola y
    # descarta cualquier size mas grande que ella (con una base de 16x16 el .ico
    # sale con un unico frame de 16x16).
    base = master.resize((max(SIZES), max(SIZES)), Image.LANCZOS)
    base.save(out, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Icono generado: {out} ({', '.join(f'{s}x{s}' for s in SIZES)})")


if __name__ == "__main__":
    main()
