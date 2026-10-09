"""Senders tab: map ingested labels (often phone numbers) to friendly names."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from tkinter import ttk
from typing import Any, Literal

from . import senders
from .gui_results import StatusSink

_COLUMNS: tuple[tuple[str, str, int, Literal["w", "e"]], ...] = (
    ("remetente", "Remetente (como veio)", 260, "w"),
    ("nome", "Nome", 220, "w"),
    ("fotos", "Fotos", 70, "e"),
)


class SendersView(ttk.Frame):
    """List of ingested senders, with a field to set a friendly name."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_status: StatusSink,
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=8)
        self._on_status = on_status
        self._on_changed = on_changed
        self._senders: dict[str, str] = {}
        self.name_var = tk.StringVar()
        self._build()

    def _build(self) -> None:
        self.count_label = ttk.Label(self, font=("TkDefaultFont", 11, "bold"))
        self.count_label.pack(anchor="w", pady=(0, 4))
        hint = (
            "Dê um nome para quem aparece como número (ex.: +55 11 9…). "
            "O nome passa a valer na aba Resultados e nas Análises."
        )
        ttk.Label(self, text=hint, foreground="#666", wraplength=760, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        table = ttk.Frame(self)
        table.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(table, orient="vertical")
        self.tree = ttk.Treeview(
            table, show="headings", selectmode="browse", yscrollcommand=scroll.set
        )
        scroll.configure(command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(columns=[column for column, _, _, _ in _COLUMNS])
        for column, title, width, anchor in _COLUMNS:
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor=anchor, stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._load_selected())

        editor = ttk.Frame(self)
        editor.pack(fill="x", pady=(8, 0))
        ttk.Label(editor, text="Nome para o remetente selecionado:").pack(side="left")
        ttk.Entry(editor, textvariable=self.name_var, width=30).pack(side="left", padx=6)
        ttk.Button(editor, text="Salvar nome", command=self._save).pack(side="left")
        ttk.Button(editor, text="Remover nome", command=self._remove).pack(side="left", padx=4)

    def show(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """List the distinct senders found in ``rows`` with their photo counts."""
        counts = Counter(str(row.get("remetente", "") or "(sem remetente)") for row in rows)
        names = senders.load_names()
        named = sum(1 for sender in counts if names.get(sender))
        self.count_label.configure(text=f"{len(counts)} remetente(s) no total · {named} com nome")
        self.tree.delete(*self.tree.get_children())
        self._senders = {}
        for index, (sender, count) in enumerate(counts.most_common()):
            iid = str(index)
            self._senders[iid] = sender
            self.tree.insert("", "end", iid=iid, values=(sender, names.get(sender, ""), count))
        self.name_var.set("")

    def _selected_sender(self) -> str | None:
        selection = self.tree.selection()
        return self._senders.get(selection[0]) if selection else None

    def _load_selected(self) -> None:
        sender = self._selected_sender()
        if sender is not None:
            self.name_var.set(senders.load_names().get(sender, ""))

    def _save(self) -> None:
        sender = self._selected_sender()
        if sender is None:
            self._on_status("Selecione um remetente na lista.", ok=False)
            return
        name = self.name_var.get().strip()
        if not name:
            self._on_status("Digite o nome antes de salvar.", ok=False)
            return
        senders.set_name(sender, name)
        self._on_changed()
        self._on_status(f"“{sender}” agora aparece como “{name}”.")

    def _remove(self) -> None:
        sender = self._selected_sender()
        if sender is None:
            self._on_status("Selecione um remetente na lista.", ok=False)
            return
        senders.remove_name(sender)
        self._on_changed()
        self._on_status(f"Nome de “{sender}” removido.")
