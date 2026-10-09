"""Optional drag-and-drop (tkinterdnd2) used by the import areas."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

try:  # optional: real drag-and-drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover - the button still works without it
    DND_FILES = None
    TkinterDnD = None

__all__ = ["DND_FILES", "TkinterDnD", "dnd_available", "register_drop"]


def dnd_available() -> bool:
    """Whether real drag-and-drop is available."""
    return DND_FILES is not None


def register_drop(widget: tk.Widget, callback: Callable[[str], None]) -> None:
    """Enable drop on ``widget`` when tkinterdnd2 is available."""
    register = getattr(widget, "drop_target_register", None)
    bind = getattr(widget, "dnd_bind", None)
    if DND_FILES is None or register is None or bind is None:
        return
    register(DND_FILES)
    bind("<<Drop>>", lambda event: callback(str(event.data)))
