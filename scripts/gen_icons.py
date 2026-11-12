#!/usr/bin/env python3
"""Generate the installable-app icons (icon-192.png, icon-512.png, icon-512-maskable.png).

They mirror favicon.svg (dark rounded square, blue "B") at the sizes a web
app manifest needs. Committed; run by hand when the mark changes.

    python3 scripts/gen_icons.py

Requires Pillow. The "B" uses Liberation Sans Bold when present, else
Pillow's built-in font.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
BG = (4, 7, 15)          # favicon.svg background
FG = (47, 100, 255)      # favicon.svg "B"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def draw(size, out, maskable=False):
    """Draw one icon. A maskable icon is full-bleed (the OS crops it to its own
    shape) with the letter kept inside the central 80% safe zone."""
    img = Image.new("RGBA", (size, size), BG if maskable else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not maskable:
        radius = round(size * 7 / 32)                   # same corner ratio as favicon.svg
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
    try:
        font = ImageFont.truetype(FONT_BOLD, round(size * (0.5 if maskable else 0.66)))
    except OSError:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), "B", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), "B", font=font, fill=FG)
    img.save(out, "PNG", optimize=True)
    print(f"Saved {out} ({size}x{size})")


def main():
    for size in (192, 512):
        draw(size, REPO / f"icon-{size}.png")
    draw(512, REPO / "icon-512-maskable.png", maskable=True)


if __name__ == "__main__":
    main()
