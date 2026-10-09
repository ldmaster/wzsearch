"""Mouse-wheel scrolling that behaves the same on macOS, Windows and Linux.

Tk's default Treeview binding scrolls by the raw wheel delta. On macOS a wheel
*notch* reports a larger delta than a trackpad event, so scaling by the delta
makes the mouse jump several rows while the trackpad feels fine. Here a macOS
event always moves a single row (both devices), and Windows/Linux notches move
a fixed few lines.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # tkinter is imported lazily so the pure helper stays testable
    import tkinter as tk

#: Rows per wheel notch on platforms that report notches (Windows: 120/notch).
LINES_PER_NOTCH = 3
#: Hard cap for a single event, however large the delta is.
MAX_ROWS_PER_EVENT = 9


def rows_for_delta(delta: int) -> int:
    """Map a raw wheel ``delta`` to a small signed number of rows."""
    if delta == 0:
        return 0
    direction = -1 if delta > 0 else 1
    if abs(delta) >= 120:  # Windows/mouse wheel: 120 per notch
        notches = max(1, abs(delta) // 120)
        return direction * min(notches * LINES_PER_NOTCH, MAX_ROWS_PER_EVENT)
    # macOS trackpad and mouse: one row per event keeps the motion even
    return direction


def bind_wheel(widget: tk.Misc, scroll_by: Callable[[int], None]) -> None:
    """Route wheel/trackpad scrolling on ``widget`` through ``scroll_by``."""

    def on_wheel(event: tk.Event) -> str:
        rows = rows_for_delta(int(getattr(event, "delta", 0) or 0))
        if rows:
            scroll_by(rows)
        return "break"

    def on_up(_event: tk.Event) -> str:
        scroll_by(-1)
        return "break"

    def on_down(_event: tk.Event) -> str:
        scroll_by(1)
        return "break"

    widget.bind("<MouseWheel>", on_wheel, add="+")
    widget.bind("<Button-4>", on_up, add="+")
    widget.bind("<Button-5>", on_down, add="+")
