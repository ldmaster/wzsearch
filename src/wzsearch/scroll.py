"""Mouse-wheel scrolling that behaves the same on macOS, Windows and Linux.

Tk's default Treeview binding scrolls by the raw wheel delta. On macOS a wheel
*notch* reports a larger delta than a trackpad event, so scaling by the delta
makes the mouse jump several rows while the trackpad feels fine. Here a macOS
event always moves a single row (both devices), and Windows/Linux notches move
a fixed few lines.

Tk 9 on macOS (what the frozen app ships) reports trackpads — and "smooth"
mice — through a different event, ``<TouchpadScroll>``, whose delta is **pixels**
packed as ``deltaX << 16 | deltaY``. A canvas has no class binding for it, so a
page of charts and labels stays stuck unless the event is bound here too.
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
#: Pixels a ``<TouchpadScroll>`` delta needs to make one row (Tk 9 sends pixels).
PIXELS_PER_ROW = 24


def rows_for_delta(delta: float | None) -> int:
    """Map a raw wheel ``delta`` to a small signed number of rows.

    Any non-zero delta moves at least one row, so no event is ever thrown away;
    only a genuinely zero/absent delta means "nothing to do".
    """
    if not delta:
        return 0
    direction = -1 if delta > 0 else 1
    magnitude = abs(float(delta))
    if magnitude < 120:  # macOS trackpad (fractions) and mouse (small integers)
        return direction
    notches = max(1, int(magnitude // 120))
    return direction * min(notches * LINES_PER_NOTCH, MAX_ROWS_PER_EVENT)


def unpack_touchpad_delta(delta: int) -> tuple[int, int]:
    """Split a ``<TouchpadScroll>`` delta into ``(delta_x, delta_y)`` pixels.

    Mirrors Tk's own ``tk::PreciseScrollDeltas``: the horizontal amount sits in
    the high 16 bits, the vertical one in the low 16 bits (signed).
    """
    delta_x = delta >> 16
    low = delta & 0xFFFF
    delta_y = low if low < 0x8000 else low - 0x10000
    return delta_x, delta_y


def touchpad_rows(delta: int | None) -> int:
    """Rows to scroll for a ``<TouchpadScroll>`` event (negative scrolls back)."""
    if not delta:
        return 0
    _delta_x, delta_y = unpack_touchpad_delta(int(delta))
    if not delta_y:
        return 0
    direction = -1 if delta_y > 0 else 1
    steps = max(1, min(abs(delta_y) // PIXELS_PER_ROW or 1, MAX_ROWS_PER_EVENT))
    return direction * steps


def bind_wheel(widget: tk.Misc, scroll_by: Callable[[int], None]) -> None:
    """Route wheel/trackpad scrolling on ``widget`` through ``scroll_by``."""

    def on_wheel(event: tk.Event) -> str | None:
        rows = rows_for_delta(getattr(event, "delta", None))
        if not rows:
            # Nothing to do: do not swallow the event (an OS may report delta 0,
            # and eating it would leave the page stuck).
            return None
        scroll_by(rows)
        return "break"

    def on_touchpad(event: tk.Event) -> str | None:
        rows = touchpad_rows(getattr(event, "delta", None))
        if not rows:
            return None
        scroll_by(rows)
        return "break"

    def on_up(_event: tk.Event) -> str:
        scroll_by(-1)
        return "break"

    def on_down(_event: tk.Event) -> str:
        scroll_by(1)
        return "break"

    widget.bind("<MouseWheel>", on_wheel, add="+")
    widget.bind("<TouchpadScroll>", on_touchpad, add="+")
    widget.bind("<Button-4>", on_up, add="+")
    widget.bind("<Button-5>", on_down, add="+")


def bind_wheel_tree(widget: tk.Misc, scroll_by: Callable[[int], None]) -> None:
    """Bind wheel scrolling on ``widget`` and every descendant.

    Handy for a scrollable page: the wheel event goes to the widget under the
    pointer (a label, a chart canvas…), so each one has to forward it.
    """
    bind_wheel(widget, scroll_by)
    for child in widget.winfo_children():
        bind_wheel_tree(child, scroll_by)
