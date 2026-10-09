"""Mouse-wheel scrolling that behaves the same on macOS, Windows and Linux.

Tk's default Treeview binding scrolls by the raw wheel delta. On macOS the
trackpad reports per-event deltas that make the list jump several rows at a
time; here every event moves a small, bounded number of rows instead, which
keeps the motion even (arrow keys already move row by row).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # tkinter is imported lazily so the pure helper stays testable
    import tkinter as tk

#: Never jump more than this many rows for a single wheel event.
MAX_ROWS_PER_EVENT = 3


def rows_for_delta(delta: int) -> int:
    """Map a raw wheel ``delta`` to a small signed number of rows."""
    if delta == 0:
        return 0
    direction = -1 if delta > 0 else 1
    if abs(delta) >= 120:  # Windows/mouse wheel: multiples of 120 per notch
        magnitude = max(1, min(abs(delta) // 120, MAX_ROWS_PER_EVENT))
    else:  # macOS trackpad: small deltas per event
        magnitude = max(1, min(abs(delta), MAX_ROWS_PER_EVENT))
    return direction * magnitude


def bind_wheel(widget: tk.Misc, scroll_by: Callable[[int], None]) -> None:
    """Route wheel/trackpad scrolling on ``widget`` through ``scroll_by``."""

    def on_wheel(event: tk.Event) -> str:
        rows = rows_for_delta(int(getattr(event, "delta", 0) or 0))
        if rows:
            scroll_by(rows)
        return "break"

    def on_up(_event: tk.Event) -> str:
        scroll_by(-MAX_ROWS_PER_EVENT)
        return "break"

    def on_down(_event: tk.Event) -> str:
        scroll_by(MAX_ROWS_PER_EVENT)
        return "break"

    widget.bind("<MouseWheel>", on_wheel, add="+")
    widget.bind("<Button-4>", on_up, add="+")
    widget.bind("<Button-5>", on_down, add="+")
