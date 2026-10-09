"""Results and trash tabs: stored rows in a table, with preview and avatars."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Literal, Protocol

from . import avatars, images
from .analytics import filter_rows
from .store import Store

_PREVIEW_BOX = 260
_PREVIEW_PAD = 12
_PREVIEW_SIDE = _PREVIEW_BOX + _PREVIEW_PAD * 2
_AVATAR_BOX = 44
_VIEWER_BOX = 900
_ALL_SENDERS = "(todos)"
_CELL_TEXT = 80
_PREVIEW_DELAY_MS = 60

#: Row fields shown in the side panel (never the media blob).
_DETAIL_KEYS = (
    "id",
    "remetente",
    "telefone_remetente",
    "data",
    "hora",
    "timestamp",
    "chat",
    "message_id",
    "legenda",
    "contexto",
    "contexto_provavel",
    "foto_arquivo",
    "foto_existe",
    "midia_pendente",
    "status",
)

#: (column key, heading, width, anchor) — everything the table can show.
_DISPLAY_COLUMNS: tuple[tuple[str, str, int, Literal["w", "center"]], ...] = (
    ("incluido", "Incluído", 70, "center"),
    ("remetente", "Remetente", 170, "w"),
    ("telefone_remetente", "Telefone", 130, "w"),
    ("data", "Data", 90, "w"),
    ("hora", "Hora", 70, "w"),
    ("contexto", "Contexto", 280, "w"),
    ("legenda", "Legenda", 220, "w"),
    ("contexto_provavel", "Contexto provável", 200, "w"),
    ("foto_arquivo", "Arquivo", 200, "w"),
    ("foto_existe", "Tem arquivo", 90, "center"),
    ("midia_pendente", "Pendente", 80, "center"),
)

#: A smaller set for when scrolling speed matters more than seeing everything.
_FAST_COLUMNS = ("incluido", "remetente", "data", "legenda", "foto_arquivo")

_ALL_COLUMN_KEYS = tuple(key for key, _, _, _ in _DISPLAY_COLUMNS)


class StatusSink(Protocol):
    """Callable that shows a status message (``ok=False`` for errors)."""

    def __call__(self, message: str, *, ok: bool = True) -> None:
        """Show ``message``; ``ok=False`` marks it as an error."""


def _cell(row: Mapping[str, Any], column: str) -> str:
    if column == "incluido":
        return "☑" if row.get("incluir") else "☐"
    text = str(row.get(column, "") or "")
    if not text:
        return "—"
    return text if len(text) <= _CELL_TEXT else text[:_CELL_TEXT] + "…"


class ResultsView(ttk.Frame):
    """Table of stored rows: preview, avatars, include toggle, delete and save."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        store: Store,
        on_status: StatusSink,
        on_changed: Callable[[], None],
        on_save: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=8)
        self._store = store
        self._on_status = on_status
        self._on_changed = on_changed
        self._on_save = on_save
        self._rows: list[Mapping[str, Any]] = []
        self._by_iid: dict[str, Mapping[str, Any]] = {}
        self._db_backed = False
        self._visible_columns: list[str] = list(_ALL_COLUMN_KEYS)
        self._column_vars: dict[str, tk.BooleanVar] = {}
        self._image: Any = None
        self._avatar: Any = None
        self._viewer: Any = None
        self._preview_id: int | None = None
        self._preview_job: str | None = None
        self._preview_cache: dict[int, Any] = {}
        self._avatar_cache: dict[str, Any] = {}
        self._build()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Incluir/Excluir da análise (Espaço)", command=self._toggle).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Excluir (lixeira)", command=self._delete).pack(
            side="left", padx=4
        )
        ttk.Button(toolbar, text="Salvar CSV…", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Colunas…", command=self._choose_columns).pack(side="left", padx=4)
        self.count_label = ttk.Label(toolbar, text="sem dados")
        self.count_label.pack(side="left", padx=10)

        filters = ttk.Frame(self)
        filters.pack(fill="x", pady=(4, 0))
        ttk.Label(filters, text="Remetente:").pack(side="left")
        self.sender_var = tk.StringVar(value=_ALL_SENDERS)
        self.sender_box = ttk.Combobox(
            filters, textvariable=self.sender_var, width=18, state="readonly"
        )
        self.sender_box.pack(side="left", padx=(2, 8))
        self.sender_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_filters())
        ttk.Label(filters, text="De:").pack(side="left")
        self.start_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.start_var, width=11).pack(side="left")
        ttk.Label(filters, text="até:").pack(side="left", padx=(4, 2))
        self.end_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.end_var, width=11).pack(side="left")
        self.pending_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filters, text="só pendentes", variable=self.pending_var, command=self._apply_filters
        ).pack(side="left", padx=8)
        ttk.Button(filters, text="Filtrar", command=self._apply_filters).pack(side="left")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))
        table = ttk.Frame(panes)
        self.tree = ttk.Treeview(table, show="headings", selectmode="extended")
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.configure(
            columns=list(_ALL_COLUMN_KEYS), displaycolumns=list(self._visible_columns)
        )
        for column, title, width, anchor in _DISPLAY_COLUMNS:
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor=anchor, stretch=False)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._show_preview())
        self.tree.bind("<Double-1>", lambda _event: self._open_viewer())
        self.tree.bind("<space>", self._on_space)
        panes.add(table, weight=3)
        panes.add(self._build_side(panes), weight=1)

    def _build_side(self, master: tk.Misc) -> ttk.Frame:
        side = ttk.Frame(master, padding=8)
        self.avatar_label = tk.Label(side)
        self.avatar_label.pack(anchor="w")
        self.sender_label = ttk.Label(side, text="—", font=("TkDefaultFont", 11, "bold"))
        self.sender_label.pack(anchor="w", pady=(4, 6))
        self.photo_canvas = tk.Canvas(
            side,
            width=_PREVIEW_SIDE,
            height=_PREVIEW_SIDE,
            background="#f2f2f2",
            highlightthickness=0,
        )
        self.photo_canvas.pack()
        buttons = ttk.Frame(side)
        buttons.pack(fill="x", pady=6)
        ttk.Button(buttons, text="Definir foto do contato…", command=self._choose_avatar).pack(
            fill="x"
        )
        ttk.Button(buttons, text="Remover foto", command=self._clear_avatar).pack(
            fill="x", pady=(4, 0)
        )
        self.details = tk.Text(side, height=8, wrap="word")
        self.details.pack(fill="both", expand=True)
        self.details.configure(state="disabled")
        return side

    # -- columns ----------------------------------------------------------
    def _choose_columns(self) -> None:
        """Open a small dialog to pick which columns the table shows."""
        self._column_vars = {
            key: tk.BooleanVar(value=key in self._visible_columns) for key in _ALL_COLUMN_KEYS
        }
        window = tk.Toplevel(self)
        window.title("Colunas da tabela")
        window.transient(self.winfo_toplevel())
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Marque as colunas que quer ver:").pack(anchor="w", pady=(0, 6))
        for key, heading, *_ in _DISPLAY_COLUMNS:
            ttk.Checkbutton(
                frame,
                text=heading,
                variable=self._column_vars[key],
                command=self._apply_column_choice,
            ).pack(anchor="w")
        presets = ttk.Frame(frame)
        presets.pack(fill="x", pady=(10, 0))
        ttk.Button(
            presets, text="Todas", command=partial(self._preset_columns, _ALL_COLUMN_KEYS)
        ).pack(side="left")
        ttk.Button(
            presets,
            text="Enxuto (mais rápido)",
            command=partial(self._preset_columns, _FAST_COLUMNS),
        ).pack(side="left", padx=4)
        ttk.Button(presets, text="Fechar", command=window.destroy).pack(side="right")

    def _apply_column_choice(self) -> None:
        chosen = [key for key in _ALL_COLUMN_KEYS if self._column_vars[key].get()]
        if not chosen:
            self._on_status("Deixe pelo menos uma coluna marcada.", ok=False)
            self._column_vars[_ALL_COLUMN_KEYS[0]].set(True)
            chosen = [_ALL_COLUMN_KEYS[0]]
        self._visible_columns = chosen
        self._apply_columns()

    def _preset_columns(self, keys: Sequence[str]) -> None:
        for key, variable in self._column_vars.items():
            variable.set(key in keys)
        self._apply_column_choice()

    def _apply_columns(self) -> None:
        self.tree.configure(displaycolumns=list(self._visible_columns))

    # -- data -------------------------------------------------------------
    def show(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Load rows into the table (stored rows carry ``id``)."""
        self._rows = list(rows)
        self._db_backed = bool(self._rows) and "id" in self._rows[0]
        senders = sorted(
            {str(row.get("remetente", "")) for row in self._rows if row.get("remetente")}
        )
        self.sender_box.configure(values=[_ALL_SENDERS, *senders])
        self._apply_filters()

    def exportable(self) -> list[Mapping[str, Any]]:
        """Rows currently visible (used by Salvar CSV)."""
        return self._visible_rows()

    def reset_caches(self) -> None:
        """Drop decoded previews and avatars (after data was replaced/erased)."""
        self._preview_cache.clear()
        self._avatar_cache.clear()
        self._preview_id = None

    def _visible_rows(self) -> list[Mapping[str, Any]]:
        sender = self.sender_var.get()
        return filter_rows(
            self._rows,
            sender=None if sender == _ALL_SENDERS else sender,
            start=self.start_var.get().strip() or None,
            end=self.end_var.get().strip() or None,
            only_pending=bool(self.pending_var.get()),
        )

    def _apply_filters(self) -> None:
        visible = self._visible_rows()
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for index, row in enumerate(visible):
            iid = str(row["id"]) if self._db_backed else str(index)
            self._by_iid[iid] = row
            self.tree.insert(
                "", "end", iid=iid, values=[_cell(row, key) for key in _ALL_COLUMN_KEYS]
            )
        self.count_label.configure(text=f"{len(visible)} de {len(self._rows)} linha(s)")

    # -- selection helpers ------------------------------------------------
    def _selected_ids(self) -> list[int]:
        if not self._db_backed:
            return []
        return [int(iid) for iid in self.tree.selection() if iid.isdigit()]

    def _selected_row(self) -> Mapping[str, Any] | None:
        selection = self.tree.selection()
        return self._by_iid.get(selection[0]) if selection else None

    def _sender(self, row: Mapping[str, Any]) -> str:
        return str(row.get("remetente", "") or "")

    # -- actions ----------------------------------------------------------
    def _on_space(self, _event: tk.Event) -> str:
        self._toggle()
        return "break"

    def _toggle(self) -> None:
        if not self._db_backed:
            self._on_status("A análise só existe para a lista de fotos (aba Fotos).", ok=False)
            return
        ids = self._selected_ids()
        if not ids:
            self._on_status("Selecione uma ou mais linhas.", ok=False)
            return
        rows = [row for row in self._rows if row.get("id") in ids]
        included = all(bool(row.get("incluir")) for row in rows)
        self._store.set_included(ids, not included)
        self._on_changed()
        state = "fora" if included else "dentro"
        self._on_status(f"{len(ids)} linha(s) agora {state} da análise.")

    def _delete(self) -> None:
        if not self._db_backed:
            self._on_status("A lixeira só existe para a lista de fotos (aba Fotos).", ok=False)
            return
        ids = self._selected_ids()
        if not ids:
            self._on_status("Selecione uma ou mais linhas para excluir.", ok=False)
            return
        self._store.delete(ids)
        self._on_changed()
        self._on_status(f"{len(ids)} linha(s) movida(s) para a lixeira.")

    def _show_preview(self) -> None:
        """Schedule the preview (debounced so fast navigation stays smooth)."""
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(_PREVIEW_DELAY_MS, self._render_preview)

    def _render_preview(self) -> None:
        self._preview_job = None
        row = self._selected_row()
        if row is None:
            return
        row_id = int(row["id"]) if self._db_backed and row.get("id") is not None else None
        sender = self._sender(row)
        self.sender_label.configure(text=sender or "(sem remetente)")
        self._render(self.avatar_label, self._avatar_image(sender), "")

        if row_id != self._preview_id:
            photo = self._cached_photo(row_id)
            missing = (
                "(mídia pendente — sem arquivo)"
                if not row.get("foto_arquivo")
                else "(imagem indisponível)"
            )
            self._draw_photo(photo, missing)
            self._preview_id = row_id

        lines = "\n".join(f"{key}: {row.get(key, '')}" for key in _DETAIL_KEYS if key in row)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", lines)
        self.details.configure(state="disabled")

    def _cached_photo(self, row_id: int | None) -> Any:
        if row_id is None or not self._db_backed:
            return None
        if row_id not in self._preview_cache:
            image = images.image_from_bytes(self._store.media(row_id), _PREVIEW_BOX)
            self._preview_cache[row_id] = images.to_photoimage(image)
            if len(self._preview_cache) > 40:
                self._preview_cache.clear()
        return self._preview_cache[row_id]

    def _draw_photo(self, photo: Any, fallback: str) -> None:
        canvas = self.photo_canvas
        canvas.delete("all")
        if photo is None:
            canvas.create_text(
                _PREVIEW_SIDE / 2,
                _PREVIEW_SIDE / 2,
                text=fallback,
                fill="#666",
                width=_PREVIEW_BOX,
            )
            self._image = None
            return
        canvas.create_image(_PREVIEW_SIDE / 2, _PREVIEW_SIDE / 2, image=photo)
        self._image = photo

    def _avatar_image(self, sender: str) -> Any:
        if sender not in self._avatar_cache:
            self._avatar_cache[sender] = images.sender_avatar(sender, _AVATAR_BOX)
        return self._avatar_cache[sender]

    def _render(self, widget: tk.Label, image: Any, fallback: str) -> Any:
        if image is None:
            widget.configure(image="", text=fallback)
            return None
        photo = images.to_photoimage(image)
        widget.configure(image=photo, text="")
        return photo

    def _open_viewer(self) -> None:
        row = self._selected_row()
        if row is None or not self._db_backed or row.get("id") is None:
            return
        image = images.image_from_bytes(self._store.media(int(row["id"])), _VIEWER_BOX)
        if image is None:
            self._on_status("Esta linha não tem foto para abrir.", ok=False)
            return
        window = tk.Toplevel(self)
        window.title(f"{row.get('remetente', '')} — {row.get('foto_arquivo', '')}")
        self._viewer = images.to_photoimage(image)
        tk.Label(window, image=self._viewer).pack()

    def _choose_avatar(self) -> None:
        row = self._selected_row()
        if row is None:
            self._on_status("Selecione uma linha para definir a foto do contato.", ok=False)
            return
        chosen = filedialog.askopenfilename(
            title="Escolha a foto do contato",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.gif"), ("Todos", "*.*")],
        )
        if chosen:
            sender = self._sender(row)
            avatars.set_avatar(sender, Path(chosen))
            self._avatar_cache.pop(sender, None)
            self._show_preview()
            self._on_status(f"Foto de {sender} atualizada.")

    def _clear_avatar(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        sender = self._sender(row)
        avatars.remove_avatar(sender)
        self._avatar_cache.pop(sender, None)
        self._show_preview()
        self._on_status(f"Foto de {sender} removida.")


class TrashView(ttk.Frame):
    """Deleted rows, with restore and permanent removal."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        store: Store,
        on_status: StatusSink,
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=8)
        self._store = store
        self._on_status = on_status
        self._on_changed = on_changed
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Restaurar selecionados", command=self._restore).pack(side="left")
        ttk.Button(toolbar, text="Excluir definitivamente (tudo)", command=self._purge).pack(
            side="left", padx=4
        )
        self.count_label = ttk.Label(toolbar, text="lixeira vazia")
        self.count_label.pack(side="left", padx=10)
        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, pady=(8, 0))
        scroll = ttk.Scrollbar(table, orient="vertical")
        self.tree = ttk.Treeview(
            table,
            show="headings",
            selectmode="extended",
            yscrollcommand=scroll.set,
            columns=("remetente", "data", "hora", "legenda", "arquivo"),
        )
        scroll.configure(command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        for column, title, width in (
            ("remetente", "Remetente", 160),
            ("data", "Data", 90),
            ("hora", "Hora", 70),
            ("legenda", "Legenda", 240),
            ("arquivo", "Arquivo", 220),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)

    def show(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Load deleted rows into the table."""
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    row.get("remetente", ""),
                    row.get("data", ""),
                    row.get("hora", ""),
                    row.get("legenda", ""),
                    row.get("foto_arquivo", ""),
                ),
            )
        self.count_label.configure(
            text=f"{len(rows)} item(ns) na lixeira" if rows else "lixeira vazia"
        )

    def _restore(self) -> None:
        ids = [int(iid) for iid in self.tree.selection()]
        if not ids:
            self._on_status("Selecione o que restaurar.", ok=False)
            return
        self._store.restore(ids)
        self._on_changed()
        self._on_status(f"{len(ids)} item(ns) restaurado(s).")

    def _purge(self) -> None:
        if not messagebox.askyesno("wzsearch", "Apagar definitivamente tudo da lixeira?"):
            return
        removed = self._store.purge()
        self._on_changed()
        self._on_status(f"{removed} item(ns) apagado(s) de vez.")
