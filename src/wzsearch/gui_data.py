"""Data window: back up, restore, erase — and clean up duplicate records."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Literal

from .gui_results import StatusSink
from .store import Store

_GROUP_COLUMNS: tuple[tuple[str, str, int, Literal["w", "e"]], ...] = (
    ("quando", "Quando", 150, "w"),
    ("remetente", "Remetente", 140, "w"),
    ("arquivo", "Arquivo", 190, "w"),
    ("legenda", "Legenda", 190, "w"),
    ("copias", "Cópias", 60, "e"),
    ("origem", "De onde vieram", 260, "w"),
)


class DataView(ttk.Frame):
    """Whole-data operations: backup, restore, erase and duplicate cleanup."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        data_path: Path,
        store: Store,
        on_status: StatusSink,
        on_backup: Callable[[], None],
        on_restore: Callable[[], None],
        on_wipe: Callable[[], None],
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=12)
        self._store = store
        self._on_status = on_status
        self._on_changed = on_changed
        ttk.Label(self, text="Dados do wzsearch", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            self,
            text=(
                "Um único backup (.zip) leva as fotos registradas, os nomes de remetentes "
                "e os avatares. Nada sai da sua máquina."
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

        self._build_duplicates()

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

    # -- duplicates --------------------------------------------------------
    def _build_duplicates(self) -> None:
        """Section that finds and resolves records of the same message."""
        box = ttk.LabelFrame(self, text="Duplicatas", padding=8)
        box.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(
            box,
            text=(
                "Procura registros com o **mesmo conteúdo de mensagem** (data/hora, "
                "remetente, arquivo e legenda) que vieram de importações diferentes — "
                "ou seja, a mesma foto gravada mais de uma vez. Ao resolver, fica uma de "
                "cada: as cópias vão para a lixeira (dá para restaurar) e a que fica "
                "herda a foto e a pontuação que você já tinha ajustado."
            ),
            foreground="#666",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        self.duplicates_label = ttk.Label(
            box, text="procurando…", font=("TkDefaultFont", 10, "bold")
        )
        self.duplicates_label.pack(anchor="w")

        table = ttk.Frame(box)
        table.pack(fill="both", expand=True, pady=(6, 6))
        self.duplicates = ttk.Treeview(
            table, show="headings", height=6, columns=[key for key, *_ in _GROUP_COLUMNS]
        )
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.duplicates.yview)
        self.duplicates.configure(yscrollcommand=scroll.set)
        for column, title, width, anchor in _GROUP_COLUMNS:
            self.duplicates.heading(column, text=title)
            self.duplicates.column(column, width=width, anchor=anchor, stretch=False)
        scroll.pack(side="right", fill="y")
        self.duplicates.pack(side="left", fill="both", expand=True)

        self.resolve_button = ttk.Button(
            box, text="Resolver duplicatas (manter uma de cada)", command=self._resolve
        )
        self.resolve_button.pack(anchor="w")
        self.reload()

    def reload(self) -> None:
        """Look for duplicates again and show what was found."""
        found = self._store.find_duplicates()
        self.duplicates.delete(*self.duplicates.get_children())
        for index, group in enumerate(found.groups):
            primeiro = group[0]
            origens = sorted({str(row.get("source", "") or "") for row in group} - {""})
            self.duplicates.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    str(primeiro.get("timestamp", "") or ""),
                    str(primeiro.get("remetente", "") or ""),
                    str(primeiro.get("foto_arquivo", "") or "—"),
                    str(primeiro.get("legenda", "") or "")[:60] or "—",
                    len(group),
                    ", ".join(origens) or "(importação antiga)",
                ),
            )
        if found.empty:
            self.duplicates_label.configure(text="nenhuma duplicata encontrada")
            self.resolve_button.configure(state="disabled")
            return
        self.duplicates_label.configure(
            text=(
                f"{len(found.groups)} mensagem(ns) gravada(s) mais de uma vez · "
                f"{found.copies} linha(s) a mais"
            )
        )
        self.resolve_button.configure(state="normal")

    def _resolve(self) -> None:
        """Keep one record per group, sending the copies to the trash."""
        found = self._store.find_duplicates()
        if found.empty:
            self.reload()
            return
        confirmado = messagebox.askyesno(
            "Resolver duplicatas",
            f"{found.copies} linha(s) repetida(s) serão movidas para a lixeira "
            f"(uma de cada mensagem fica).\n\n"
            "A linha que fica herda a foto e a pontuação já ajustada. "
            "Dá para restaurar depois em ⚙ Ajustes → Lixeira.",
        )
        if not confirmado:
            return
        resultado = self._store.resolve_duplicates(found)
        self._on_changed()
        self.reload()
        detalhe = (
            f" · {resultado.completed} completada(s) com foto/pontuação"
            if resultado.completed
            else ""
        )
        self._on_status(f"{resultado.removed} linha(s) repetida(s) na lixeira{detalhe}.")
