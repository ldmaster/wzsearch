"""The Help window: a list of topics on the left, the selected one on the right."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from functools import partial
from tkinter import ttk

from .help_text import INTRO, TOPICS

_LIST_WIDTH = 22
_WRAP = 520


class HelpWindow:
    """Two-pane help window with formatted topics."""

    def __init__(
        self, master: tk.Misc, *, on_open_tab: Callable[[str], None] | None = None
    ) -> None:
        self._on_open_tab = on_open_tab
        self.window = tk.Toplevel(master)
        self.window.title("Como usar o wzsearch")
        self.window.geometry("860x620")
        self.window.minsize(720, 460)
        self._build()

    def _build(self) -> None:
        ttk.Label(
            self.window,
            text="Ajuda do wzsearch",
            font=("TkDefaultFont", 14, "bold"),
            padding=(14, 12, 14, 0),
        ).pack(anchor="w")
        ttk.Label(
            self.window,
            text=INTRO,
            foreground="#666",
            wraplength=780,
            justify="left",
            padding=(14, 4, 14, 8),
        ).pack(anchor="w")

        body = ttk.Frame(self.window, padding=(14, 0, 14, 12))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        self.listbox = tk.Listbox(
            left, exportselection=False, width=_LIST_WIDTH, activestyle="none"
        )
        self.listbox.pack(fill="y", expand=True)
        for topic in TOPICS:
            self.listbox.insert("end", topic.title)
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self._show_selected())

        right = ttk.Frame(body, padding=(14, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        canvas = tk.Canvas(right, highlightthickness=0)
        scroll = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._content = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=self._content, anchor="nw")
        self._content.bind(
            "<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        self.listbox.selection_set(0)
        self._show_selected()

    def _show_selected(self) -> None:
        selection = self.listbox.curselection()  # type: ignore[no-untyped-call]
        if not selection:
            return
        topic = TOPICS[selection[0]]
        for child in self._content.winfo_children():
            child.destroy()

        ttk.Label(self._content, text=topic.title, font=("TkDefaultFont", 13, "bold")).pack(
            anchor="w", pady=(0, 2)
        )
        ttk.Label(
            self._content, text=topic.summary, foreground="#444", wraplength=_WRAP, justify="left"
        ).pack(anchor="w", pady=(0, 8))

        for bullet in topic.bullets:
            row = ttk.Frame(self._content)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text="•", foreground="#128c7e", font=("TkDefaultFont", 12, "bold")).pack(
                side="left", anchor="n"
            )
            ttk.Label(row, text=bullet, wraplength=_WRAP - 18, justify="left").pack(
                side="left", fill="x", expand=True, padx=(6, 0)
            )

        if topic.tip:
            box = tk.Frame(self._content, background="#e8f5f2", padx=10, pady=8)
            box.pack(fill="x", pady=(10, 0))
            tk.Label(
                box,
                text=f"Dica: {topic.tip}",
                background="#e8f5f2",
                foreground="#0b5c50",
                wraplength=_WRAP,
                justify="left",
            ).pack(anchor="w")

        open_tab = self._on_open_tab
        if topic.tab is not None and open_tab is not None:
            ttk.Button(
                self._content,
                text=f"Abrir a aba {topic.tab}",
                command=partial(open_tab, topic.tab),
            ).pack(anchor="w", pady=(12, 0))
