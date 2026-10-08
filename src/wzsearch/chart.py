"""A small bar-chart widget drawn on a Tk canvas (no external dependency)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from tkinter import ttk

_LABEL_FONT = ("TkDefaultFont", 8)
_AXIS_PAD = 18


class BarChart(ttk.Frame):
    """Simple vertical bar chart with values on top and labels below."""

    def __init__(self, master: tk.Misc, *, height: int = 150, color: str = "#4a7ebb") -> None:
        super().__init__(master)
        self._height = height
        self._color = color
        self._data: list[tuple[str, int]] = []
        self._canvas = tk.Canvas(self, height=height, background="white", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _event: self._redraw())

    def set_data(self, items: Sequence[tuple[str, int]], *, max_bars: int = 48) -> None:
        """Plot ``items`` as ``(label, count)`` bars."""
        self._data = list(items)[:max_bars]
        self._redraw()

    def _redraw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")
        width = canvas.winfo_width() or 320
        height = canvas.winfo_height() or self._height
        if not self._data:
            canvas.create_text(width / 2, height / 2, text="sem dados", fill="#999")
            return

        top = max(count for _, count in self._data) or 1
        slot = max(6.0, (width - _AXIS_PAD * 2) / len(self._data))
        bar_width = max(2.0, slot * 0.7)
        baseline = height - 16
        for index, (label, count) in enumerate(self._data):
            left = _AXIS_PAD + index * slot
            bar_height = (count / top) * (baseline - 14)
            canvas.create_rectangle(
                left,
                baseline - bar_height,
                left + bar_width,
                baseline,
                fill=self._color,
                outline="",
            )
            if count:
                canvas.create_text(
                    left + bar_width / 2,
                    baseline - bar_height - 7,
                    text=str(count),
                    fill="#333",
                    font=_LABEL_FONT,
                )
            if slot >= 18:
                canvas.create_text(
                    left + bar_width / 2,
                    baseline + 8,
                    text=self._short(label),
                    fill="#666",
                    font=_LABEL_FONT,
                )

    @staticmethod
    def _short(label: str) -> str:
        return label if len(label) <= 6 else label[-5:]
