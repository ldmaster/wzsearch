"""Ajustes → Atualizações: installed version, the toggle and a manual check."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from . import __version__, settings


class UpdatesView(ttk.Frame):
    """Small panel with the update settings and the manual check."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_check: Callable[[], None],
        on_toggle: Callable[[bool], None],
    ) -> None:
        super().__init__(master, padding=12)
        ttk.Label(self, text="Atualizações", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(self, text=f"Versão instalada: {__version__}").pack(anchor="w", pady=(4, 10))

        self.check_var = tk.BooleanVar(value=settings.load().check_updates)
        ttk.Checkbutton(
            self,
            text="Verificar atualizações ao abrir",
            variable=self.check_var,
            command=lambda: on_toggle(bool(self.check_var.get())),
        ).pack(anchor="w")
        ttk.Button(self, text="Verificar agora", command=on_check).pack(anchor="w", pady=(10, 4))

        self.result = ttk.Label(self, text="", wraplength=560, justify="left")
        self.result.pack(anchor="w", pady=(8, 0))

        box = ttk.LabelFrame(self, text="Privacidade", padding=8)
        box.pack(fill="x", pady=(16, 0))
        ttk.Label(
            box,
            text=(
                "Esta é a única conexão que o wzsearch faz: ele pergunta ao GitHub qual é a "
                "última versão. Nada sobre as suas conversas (mensagens, fotos, nomes) sai "
                "da sua máquina — desmarque a opção acima para não fazer nem essa consulta."
            ),
            foreground="#666",
            wraplength=560,
            justify="left",
        ).pack(anchor="w")

    def show_result(self, message: str, *, ok: bool = True) -> None:
        """Report the outcome of a check in the panel."""
        self.result.configure(text=message, foreground="#1a7f37" if ok else "#c0392b")
