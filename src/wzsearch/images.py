"""Image loading and generated avatars (Pillow), used only by the GUI.

Pillow is an optional dependency of the graphical app; when it is missing every
function here returns ``None`` and the GUI falls back to no previews.
"""

from __future__ import annotations

import zlib
from io import BytesIO
from pathlib import Path
from typing import Any

from .avatars import avatar_path
from .loader import read_media_bytes

try:
    from PIL import Image, ImageDraw, ImageFont

    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - GUI still starts without previews
    Image = None
    ImageDraw = None
    ImageFont = None
    PILLOW_AVAILABLE = False

_PALETTE = (
    "#4a7ebb",
    "#c0392b",
    "#1a7f37",
    "#8e44ad",
    "#d35400",
    "#16a085",
    "#2c3e50",
    "#b8860b",
)


def avatar_color(label: str) -> str:
    """Pick a stable colour for a sender (same label -> same colour)."""
    return _PALETTE[zlib.crc32(label.encode("utf-8")) % len(_PALETTE)]


def initials_for(label: str) -> str:
    """Return up to two initials for a sender label or phone number."""
    parts = [part for part in label.replace("+", " ").replace("-", " ").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _font(box: int) -> Any:
    try:
        return ImageFont.load_default(size=int(box * 0.45))
    except TypeError:  # older Pillow: no size argument
        return ImageFont.load_default()


def initials_avatar(label: str, box: int) -> Any:
    """Draw a coloured circle with the sender's initials."""
    if not PILLOW_AVAILABLE:
        return None
    image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, box - 1, box - 1), fill=avatar_color(label))
    font = _font(box)
    text = initials_for(label)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((box - (right - left)) / 2 - left, (box - (bottom - top)) / 2 - top),
        text,
        font=font,
        fill="white",
    )
    return image


def open_image(data: bytes) -> Any:
    """Decode image bytes into a Pillow image, or ``None`` on failure."""
    if not PILLOW_AVAILABLE:
        return None
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception:  # Pillow raises many formats; treat all as unreadable
        return None
    return image


def thumbnail(image: Any, box: int) -> Any:
    """Return a copy of ``image`` scaled to fit ``box`` by ``box``."""
    copy = image.copy()
    copy.thumbnail((box, box))
    return copy


def load_photo(source: Path, filename: str, box: int) -> Any:
    """Load a thumbnail of a photo stored inside the export, if present."""
    if not filename:
        return None
    data = read_media_bytes(source, filename)
    if data is None:
        return None
    image = open_image(data)
    return thumbnail(image, box) if image is not None else None


def load_image_file(path: Path, box: int) -> Any:
    """Load a thumbnail from a file on disk (used for user-chosen avatars)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    image = open_image(data)
    return thumbnail(image, box) if image is not None else None


def sender_avatar(sender: str, box: int) -> Any:
    """Return the user's photo for ``sender``, or generated initials."""
    chosen = avatar_path(sender)
    if chosen is not None:
        image = load_image_file(chosen, box)
        if image is not None:
            return image
    return initials_avatar(sender, box)


def to_photoimage(image: Any) -> Any:
    """Convert a Pillow image to a Tk image (requires a Tk root and Pillow)."""
    if not PILLOW_AVAILABLE or image is None:
        return None
    from PIL import ImageTk

    return ImageTk.PhotoImage(image)
