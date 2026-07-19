#!/usr/bin/env python3
"""Genera build/icon.ico: una nota adhesiva amarilla con la esquina doblada.

El .ico va versionado en el repo, asi que este script solo hace falta si se
quiere retocar el icono. Requiere Pillow (no es dependencia de la app):

    pip install pillow
    python build/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Amarillo post-it con volumen: mas claro arriba, mas calido abajo.
PAPER_TOP = (255, 233, 133)
PAPER_BOTTOM = (247, 201, 72)
FOLD_TOP = (224, 169, 62)
FOLD_BOTTOM = (201, 143, 43)
COLOR_INK = (122, 106, 51)
SHADOW_ALPHA = 80

# Se dibuja grande y se reduce: sale con antialiasing gratis.
CANVAS = 1024
SIZES = [16, 32, 48, 64, 128, 256]

# Inclinacion de la nota: es lo que la hace leer "pegada a mano" y no como un
# cuadrado amarillo generico en la bandeja.
TILT_DEG = -7


def _gradient(width: int, height: int, top_color, bottom_color) -> Image.Image:
    """Devuelve un degradado vertical RGBA de top_color a bottom_color."""
    column = Image.new("RGBA", (1, height))
    last = height - 1
    for y in range(height):
        t = y / last
        column.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(top_color, bottom_color)),
        )
    return column.resize((width, height))


def draw_note(size: int) -> Image.Image:
    """Dibuja la nota adhesiva en un lienzo cuadrado RGBA.

    Recibe: el lado del lienzo en pixeles.
    Devuelve: la imagen RGBA con la nota inclinada y su sombra.
    """
    # Margen amplio: la rotacion final necesita sitio para no recortar esquinas.
    m = size * 0.16
    left, top = m, m
    right, bottom = size - m, size - m
    fold = size * 0.30
    radius = size * 0.05

    # Silueta de la nota: rectangulo redondeado menos la esquina doblada.
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([left, top, right, bottom], radius=radius, fill=255)
    md.polygon(
        [(right - fold, bottom), (right, bottom - fold), (right, bottom)],
        fill=0,
    )

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Sombra suave y desplazada, a partir de la propia silueta.
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, SHADOW_ALPHA), (round(size * 0.015), round(size * 0.03)), mask)
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size * 0.02)))

    # Papel con degradado, recortado a la silueta.
    img.paste(_gradient(size, size, (*PAPER_TOP, 255), (*PAPER_BOTTOM, 255)), (0, 0), mask)

    d = ImageDraw.Draw(img)

    # Renglones escritos: gruesos, para que sobrevivan a los 22 px de la bandeja.
    line_x0 = left + size * 0.11
    line_h = size * 0.055
    for width_factor, y_factor in ((0.56, 0.24), (0.64, 0.42), (0.40, 0.60)):
        y = top + (bottom - top) * y_factor
        d.rounded_rectangle(
            [line_x0, y, line_x0 + (right - left) * width_factor, y + line_h],
            radius=line_h / 2,
            fill=COLOR_INK,
        )

    # La esquina doblada, con su propio degradado y una linea de pliegue.
    fold_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(fold_mask).polygon(
        [(right - fold, bottom), (right, bottom - fold), (right - fold, bottom - fold)],
        fill=255,
    )
    img.paste(_gradient(size, size, (*FOLD_TOP, 255), (*FOLD_BOTTOM, 255)), (0, 0), fold_mask)
    d.line(
        [(right - fold, bottom), (right, bottom - fold)],
        fill=(*FOLD_BOTTOM, 255),
        width=max(1, round(size * 0.006)),
    )

    return img.rotate(TILT_DEG, resample=Image.BICUBIC, center=(size / 2, size / 2))


def main() -> None:
    """Genera el .ico multi-resolucion y el .png junto a este script."""
    master = draw_note(CANVAS)
    out_dir = Path(__file__).parent
    # La imagen base debe ser la MAYOR: Pillow genera el resto reduciendola y
    # descarta cualquier size mas grande que ella (con una base de 16x16 el .ico
    # sale con un unico frame de 16x16).
    base = master.resize((max(SIZES), max(SIZES)), Image.LANCZOS)
    base.save(out_dir / "icon.ico", format="ICO", sizes=[(s, s) for s in SIZES])
    # El .png lo usa la entrada del menu de aplicaciones en Linux, que no
    # entiende .ico.
    base.save(out_dir / "icon.png", format="PNG")
    print(f"Iconos generados en {out_dir}: icon.ico "
          f"({', '.join(f'{s}x{s}' for s in SIZES)}) + icon.png")


if __name__ == "__main__":
    main()
