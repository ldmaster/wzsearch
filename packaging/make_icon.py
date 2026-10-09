"""Generate the app icon (a magnifier over a photo) as .png, .ico and .icns.

Run with Pillow available: ``python packaging/make_icon.py``. The generated
files are committed so the builds do not need to regenerate them.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
_OUT = Path(__file__).parent

_TEAL = "#128C7E"
_TEAL_DARK = "#075E54"
_CARD = "#FFFFFF"
_SKY = "#BFE3DC"
_SUN = "#F5C542"
_HILL = "#2E7D6F"
_LENS = (191, 227, 220, 120)


def render(size: int = SIZE) -> Image.Image:
    """Draw the icon at ``size`` pixels."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def px(value: float) -> int:
        return int(value * size)

    # rounded square with a subtle vertical gradient
    top_teal = Image.new("RGB", (size, size), (32, 158, 143))
    bottom_teal = Image.new("RGB", (size, size), (9, 92, 83))
    background = Image.composite(bottom_teal, top_teal, Image.linear_gradient("L").resize((size, size)))
    rounded = Image.new("L", (size, size), 0)
    ImageDraw.Draw(rounded).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=px(0.22), fill=255
    )
    image.paste(background, (0, 0), rounded)

    # photo card
    left, top, right, bottom = px(0.13), px(0.17), px(0.65), px(0.63)
    draw.rounded_rectangle((left, top, right, bottom), radius=px(0.05), fill=_CARD)

    # sky + sun
    inset = px(0.045)
    draw.rounded_rectangle(
        (left + inset, top + inset, right - inset, px(0.41)),
        radius=px(0.03),
        fill=_SKY,
    )
    draw.ellipse((px(0.23), px(0.25), px(0.37), px(0.39)), fill=_SUN)

    # hills, inside the card
    draw.polygon(
        [
            (left + inset, px(0.56)),
            (px(0.33), px(0.39)),
            (px(0.52), px(0.56)),
        ],
        fill=_HILL,
    )
    draw.polygon(
        [
            (px(0.37), px(0.56)),
            (px(0.54), px(0.43)),
            (right - inset, px(0.56)),
        ],
        fill=_TEAL_DARK,
    )

    # magnifier: glass lens, white ring and handle (kept inside the canvas)
    center_x, center_y, radius = px(0.62), px(0.60), px(0.185)
    box = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).ellipse(box, fill=_LENS)
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)
    draw.ellipse(box, outline=_CARD, width=px(0.032))
    draw.line(
        (center_x + radius * 0.70, center_y + radius * 0.70,
         center_x + radius * 1.32, center_y + radius * 1.32),
        fill=_CARD,
        width=px(0.05),
    )
    return image


def write_png_and_ico(image: Image.Image) -> None:
    """Write ``icon.png`` and a multi-size ``icon.ico``."""
    image.save(_OUT / "icon.png")
    image.save(
        _OUT / "icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def write_icns(image: Image.Image) -> bool:
    """Write ``icon.icns`` using ``iconutil`` (macOS only)."""
    if sys.platform != "darwin":
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            image.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            image.resize((size * 2, size * 2), Image.LANCZOS).save(
                iconset / f"icon_{size}x{size}@2x.png"
            )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(_OUT / "icon.icns")],
            check=True,
        )
    return True


def main() -> None:
    """Write every icon file next to this script."""
    image = render()
    write_png_and_ico(image)
    made_icns = write_icns(image)
    print("icon.png, icon.ico escritos")
    print("icon.icns escrito" if made_icns else "icon.icns ignorado (não é macOS)")


if __name__ == "__main__":
    main()
