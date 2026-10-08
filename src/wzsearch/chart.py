"""Tiny chart widgets drawn on a Tk canvas (no external dependency)."""

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


class Heatmap(ttk.Frame):
    """Grid shaded by value — used for weekday x hour activity."""

    def __init__(self, master: tk.Misc, *, cell: int = 16, color: str = "#4a7ebb") -> None:
        super().__init__(master)
        self._cell = cell
        self._color = color
        self._rows = 0
        self._cols = 0
        self._data: list[list[int]] = []
        self._row_labels: tuple[str, ...] = ()
        self._canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self._canvas.pack(anchor="w")

    def set_data(self, data: Sequence[Sequence[int]], *, row_labels: Sequence[str]) -> None:
        """Draw the grid from ``data`` (rows x columns) with row labels."""
        self._data = [list(row) for row in data]
        self._rows = len(self._data)
        self._cols = len(self._data[0]) if self._rows else 0
        self._row_labels = tuple(row_labels)
        self._canvas.configure(
            width=self._cell * self._cols + 44, height=self._cell * self._rows + 22
        )
        self._draw()

    def _draw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")
        if not self._data or not self._cols:
            return
        top = max((max(row) for row in self._data), default=0)
        cell = self._cell
        for row_index, row in enumerate(self._data):
            label = self._row_labels[row_index] if row_index < len(self._row_labels) else ""
            canvas.create_text(
                34,
                row_index * cell + cell / 2,
                text=label,
                anchor="e",
                fill="#555",
                font=_LABEL_FONT,
            )
            for col_index, value in enumerate(row):
                ratio = value / top if top else 0.0
                canvas.create_rectangle(
                    40 + col_index * cell,
                    row_index * cell,
                    40 + (col_index + 1) * cell - 1,
                    (row_index + 1) * cell - 1,
                    fill=_blend(self._color, ratio),
                    outline="white",
                )
        for hour in range(0, self._cols, 3):
            canvas.create_text(
                40 + hour * cell,
                self._rows * cell + 10,
                text=f"{hour:02d}",
                fill="#666",
                font=_LABEL_FONT,
            )


def _blend(color: str, ratio: float) -> str:
    """Blend ``color`` toward white as ``ratio`` goes from 1 to 0."""
    ratio = max(0.0, min(1.0, ratio))
    base = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
    red, green, blue = (int(255 - (255 - channel) * ratio) for channel in base)
    return f"#{red:02x}{green:02x}{blue:02x}"
