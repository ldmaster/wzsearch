"""Data tab: back up, restore or erase everything wzsearch stores."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk


class DataView(ttk.Frame):
    """Buttons for the whole-data operations (backup, restore, erase)."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        data_path: Path,
        on_backup: Callable[[], None],
        on_restore: Callable[[], None],
        on_wipe: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=12)
        ttk.Label(self, text="Dados do wzsearch", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            self,
            text=(
                "Um único backup (.zip) leva as fotos registradas, os nomes de remetentes "
                "e os avatares. O conteúdo das conversas não sai da sua máquina — a única "
                "conexão é a checagem de atualização, que dá para desligar em "
                "⚙ Ajustes → Atualizações…"
            ),
            foreground="#666",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        ttk.Button(self, text="Fazer backup de todos os dados…", command=on_backup).pack(
            anchor="w", pady=2
        )
        ttk.Button(self, text="Restaurar backup…", command=on_restore).pack(anchor="w", pady=2)
        erase = ttk.Button(self, text="Apagar todos os dados", command=on_wipe)
        erase.pack(anchor="w", pady=(12, 2))
        ttk.Label(
            self,
            text=(
                "Apagar remove as fotos registradas, os nomes e os avatares. Não dá para desfazer."
            ),
            foreground="#c0392b",
            wraplength=640,
            justify="left",
        ).pack(anchor="w")

        box = ttk.LabelFrame(self, text="Onde ficam os dados", padding=8)
        box.pack(fill="x", pady=(16, 0))
        ttk.Label(box, text=str(data_path), wraplength=640, justify="left").pack(anchor="w")
        ttk.Label(
            box,
            text="(pasta oculta do sistema; use WZSEARCH_HOME para mudar de lugar)",
            foreground="#666",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))
