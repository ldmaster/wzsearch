"""Small hover hints (tooltips) for metrics, filters and table headings.

ttk has no tooltip of its own, so this is a tiny one: a borderless window with
the explanation, shown a moment after the pointer rests over a widget and closed
as soon as it moves away. The light background is on purpose — a hint has to be
readable in the light and in the dark appearance alike.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Mapping
from tkinter import ttk

#: How long the pointer has to rest before the hint appears.
DELAY_MS = 450

_WRAP = 380
_BACKGROUND = "#ffffe1"
_FOREGROUND = "#222222"


class Hint:
    """One hint window, reused for every widget that shares it."""

    def __init__(self, master: tk.Misc) -> None:
        self._master = master
        self._window: tk.Toplevel | None = None
        self._job: str | None = None

    def schedule(self, text: str, x_root: int, y_root: int) -> None:
        """Show ``text`` next to the pointer after a short rest."""
        self.cancel()
        if not text:
            return
        self._job = self._master.after(DELAY_MS, lambda: self._show(text, x_root, y_root))

    def cancel(self) -> None:
        """Drop a pending hint (the pointer moved on)."""
        if self._job is not None:
            self._master.after_cancel(self._job)
            self._job = None

    def hide(self) -> None:
        """Close the hint window and forget any pending one."""
        self.cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None

    def _show(self, text: str, x_root: int, y_root: int) -> None:
        self._job = None
        if self._window is not None:
            self._window.destroy()
        window = tk.Toplevel(self._master)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        label = tk.Label(
            window,
            text=text,
            background=_BACKGROUND,
            foreground=_FOREGROUND,
            justify="left",
            wraplength=_WRAP,
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=6,
        )
        label.pack()
        window.update_idletasks()
        window.geometry(f"+{x_root + 14}+{y_root + 18}")
        self._window = window


def add_hint(widget: tk.Misc, text: str) -> None:
    """Attach a hint to a single widget (a label, a button, a checkbox…)."""
    hint = Hint(widget)

    def on_enter(_event: tk.Event) -> None:
        hint.schedule(text, widget.winfo_pointerx(), widget.winfo_pointery())

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", lambda _event: hint.hide(), add="+")
    widget.bind("<ButtonPress>", lambda _event: hint.hide(), add="+")


def add_hints(widgets: Mapping[tk.Misc, str]) -> None:
    """Attach a hint to each ``widget -> text`` pair."""
    for widget, text in widgets.items():
        if text:
            add_hint(widget, text)


def _displayed_keys(tree: ttk.Treeview) -> list[str]:
    """Keys of the columns the table is showing, in display order."""
    shown = tree.cget("displaycolumns")
    if isinstance(shown, str):
        if shown in {"", "#all"}:
            return [str(key) for key in tree.cget("columns")]
        return [str(key) for key in tree.tk.splitlist(shown)]
    if isinstance(shown, tuple):
        return [str(key) for key in shown]
    return [str(key) for key in tree.cget("columns")]


def add_tree_hints(tree: ttk.Treeview, hints: Mapping[str, str]) -> None:
    """Show a hint when the pointer rests over one of the table headings."""
    hint = Hint(tree)
    current = ""

    def on_motion(event: tk.Event) -> None:
        nonlocal current
        text = ""
        if tree.identify_region(event.x, event.y) == "heading":
            column_id = tree.identify_column(event.x)
            if column_id.startswith("#") and column_id[1:].isdigit():
                keys = _displayed_keys(tree)
                index = int(column_id[1:]) - 1
                if 0 <= index < len(keys):
                    text = hints.get(keys[index], "")
        if text == current:
            return
        current = text
        hint.hide()
        if text:
            hint.schedule(text, tree.winfo_pointerx(), tree.winfo_pointery())

    tree.bind("<Motion>", on_motion, add="+")
    tree.bind("<Leave>", lambda _event: hint.hide(), add="+")
