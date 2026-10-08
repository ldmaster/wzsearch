"""Results tab: the generated rows in a table, with photo preview and avatars."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any, Protocol

from . import avatars, images
from .analytics import filter_rows
from .pipeline import columns_for

_MAX_COLUMN_WIDTH = 200
_PREVIEW_BOX = 260
_AVATAR_BOX = 44
_VIEWER_BOX = 900
_ALL_SENDERS = "(todos)"


class StatusSink(Protocol):
    """Callable that shows a status message (``ok=False`` for errors)."""

    def __call__(self, message: str, *, ok: bool = True) -> None:
        """Show ``message``; ``ok=False`` marks it as an error."""


class ResultsView(ttk.Frame):
    """Table of rows plus a side panel with the photo and sender avatar."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_save: Callable[[], None],
        on_status: StatusSink,
    ) -> None:
        super().__init__(master, padding=8)
        self._on_save = on_save
        self._on_status = on_status
        self._rows: list[dict[str, object]] = []
        self._mode = "photos"
        self._source: Path | None = None
        self._photo_img: Any = None
        self._avatar_img: Any = None
        self._viewer_img: Any = None
        self._build()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Salvar CSV…", command=self._on_save).pack(side="left")
        self.count_label = ttk.Label(toolbar, text="sem dados")
        self.count_label.pack(side="left", padx=10)

        ttk.Label(toolbar, text="Remetente:").pack(side="left", padx=(10, 2))
        self.sender_var = tk.StringVar(value=_ALL_SENDERS)
        self.sender_box = ttk.Combobox(
            toolbar, textvariable=self.sender_var, width=18, state="readonly"
        )
        self.sender_box.pack(side="left")
        self.sender_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_filters())

        ttk.Label(toolbar, text="De:").pack(side="left", padx=(10, 2))
        self.start_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.start_var, width=11).pack(side="left")
        ttk.Label(toolbar, text="até:").pack(side="left", padx=(4, 2))
        self.end_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.end_var, width=11).pack(side="left")
        self.pending_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar, text="só pendentes", variable=self.pending_var, command=self._apply_filters
        ).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Filtrar", command=self._apply_filters).pack(side="left")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        table_frame = ttk.Frame(panes)
        self.tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.pack(side="top", fill="both", expand=True)
        yscroll.place(relx=1.0, rely=0, relheight=0.95, anchor="ne")
        xscroll.pack(side="bottom", fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._show_preview())
        self.tree.bind("<Double-1>", lambda _event: self._open_viewer())
        panes.add(table_frame, weight=3)

        panes.add(self._build_side(panes), weight=1)

    def _build_side(self, master: tk.Misc) -> ttk.Frame:
        side = ttk.Frame(master, padding=8)
        self.avatar_label = tk.Label(side, width=_AVATAR_BOX, height=_AVATAR_BOX)
        self.avatar_label.pack(anchor="w")
        self.sender_label = ttk.Label(side, text="—", font=("TkDefaultFont", 11, "bold"))
        self.sender_label.pack(anchor="w", pady=(4, 6))
        self.photo_label = tk.Label(
            side, text="(sem foto)", background="#f2f2f2", width=34, height=10
        )
        self.photo_label.pack(fill="x")
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

    # -- data -------------------------------------------------------------
    def show(self, rows: Sequence[dict[str, object]], *, mode: str, source: Path | None) -> None:
        """Load new rows into the table."""
        self._rows = list(rows)
        self._mode = mode
        self._source = source
        columns = list(columns_for(mode))
        self.tree.configure(columns=columns)
        for column in columns:
            self.tree.heading(column, text=column)
            width = 90 if column in {"data", "hora", "message_id"} else _MAX_COLUMN_WIDTH
            self.tree.column(column, width=width, stretch=False, anchor="w")
        senders = sorted(
            {str(row.get("remetente", "")) for row in self._rows if row.get("remetente")}
        )
        self.sender_box.configure(values=[_ALL_SENDERS, *senders])
        self.sender_var.set(_ALL_SENDERS)
        self.start_var.set("")
        self.end_var.set("")
        self.pending_var.set(False)
        self._apply_filters()

    def _visible_rows(self) -> list[Mapping[str, object]]:
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
        columns = list(columns_for(self._mode))
        for index, row in enumerate(visible):
            self.tree.insert(
                "", "end", iid=str(index), values=[str(row.get(c, "")) for c in columns]
            )
        self.count_label.configure(text=f"{len(visible)} de {len(self._rows)} linha(s)")

    # -- interaction ------------------------------------------------------
    def _selected_row(self) -> Mapping[str, object] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        visible = self._visible_rows()
        index = int(selection[0])
        return visible[index] if 0 <= index < len(visible) else None

    def _sender(self, row: Mapping[str, object]) -> str:
        return str(row.get("remetente", "") or "")

    def _show_preview(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        sender = self._sender(row)
        self.sender_label.configure(text=sender or "(sem remetente)")
        self._avatar_img = self._render(
            self.avatar_label, images.sender_avatar(sender, _AVATAR_BOX)
        )
        filename = str(row.get("foto_arquivo", "") or "")
        image = None
        if filename and self._source is not None:
            image = images.load_photo(self._source, filename, _PREVIEW_BOX)
        self._photo_img = self._render(self.photo_label, image)
        if image is None:
            self.photo_label.configure(
                text="(sem foto)" + ("" if filename else " — mídia pendente")
            )
        lines = "\n".join(f"{key}: {value}" for key, value in row.items())
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", lines)
        self.details.configure(state="disabled")

    def _render(self, widget: tk.Label, image: Any) -> Any:
        if image is None:
            widget.configure(image="", text=widget.cget("text"))
            return None
        photo = images.to_photoimage(image)
        widget.configure(image=photo, text="")
        return photo

    def _open_viewer(self) -> None:
        row = self._selected_row()
        if row is None or self._source is None:
            return
        filename = str(row.get("foto_arquivo", "") or "")
        image = images.load_photo(self._source, filename, _VIEWER_BOX) if filename else None
        if image is None:
            self._on_status("Esta mensagem não tem foto para abrir.", ok=False)
            return
        window = tk.Toplevel(self)
        window.title(f"{row.get('remetente', '')} — {filename}")
        self._viewer_img = images.to_photoimage(image)
        tk.Label(window, image=self._viewer_img).pack()

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
            self._show_preview()
            self._on_status(f"Foto de {sender} atualizada.", ok=True)

    def _clear_avatar(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        sender = self._sender(row)
        avatars.remove_avatar(sender)
        self._show_preview()
        self._on_status(f"Foto de {sender} removida.", ok=True)
