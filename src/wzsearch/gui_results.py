"""Results and trash tabs: stored rows in a table, with preview and avatars."""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Literal, Protocol

from . import avatars, images, score
from .analytics import filter_rows, points_of
from .dnd import dnd_available, register_drop
from .hint import add_hints, add_tree_hints
from .sorting import Sortable, heading_label, sort_items
from .store import Store

_PREVIEW_BOX = 260
_PREVIEW_PAD = 12
_PREVIEW_SIDE = _PREVIEW_BOX + _PREVIEW_PAD * 2
_AVATAR_BOX = 44
_VIEWER_BOX = 900
_ALL_SENDERS = "(todos)"
_CELL_TEXT = 80
_PREVIEW_DELAY_MS = 60
_FILTER_DELAY_MS = 200

#: Colour of the rows worth two points or more (readable on light and dark).
_POINTED_COLOUR = "#1a7f37"

_EXPORT_TYPES = [("Export do WhatsApp", "*.zip *.txt"), ("Todos os arquivos", "*.*")]

#: Fields a text search looks at.
_SEARCH_FIELDS = ("remetente", "contexto", "legenda", "contexto_provavel", "foto_arquivo")


def _searchable(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(key, "") or "") for key in _SEARCH_FIELDS)


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
    "pontos",
    "pontos_origem",
    "pontos_motivo",
    "status",
)

#: (column key, heading, width, anchor) — everything the table can show.
_DISPLAY_COLUMNS: tuple[tuple[str, str, int, Literal["w", "center"]], ...] = (
    ("incluido", "Incluído", 70, "center"),
    ("pontos", "Pontos", 90, "center"),
    ("pontos_motivo", "Seu motivo", 200, "w"),
    ("remetente", "Remetente", 170, "w"),
    ("telefone_remetente", "Telefone", 130, "w"),
    ("data", "Data", 90, "w"),
    ("hora", "Hora", 70, "w"),
    ("contexto", "Contexto", 280, "w"),
    ("legenda", "Legenda", 220, "w"),
    ("contexto_provavel", "Contexto provável", 200, "w"),
    ("foto_arquivo", "Arquivo", 200, "w"),
    ("foto_existe", "Tem arquivo", 90, "center"),
    ("midia_pendente", "Sem arquivo", 90, "center"),
)

#: What each column means (shown when the pointer rests on the heading).
_COLUMN_HINTS = {
    "incluido": "☑ marca a linha para entrar nas Análises (clique na célula ou use a "
    "tecla Espaço). Desmarcada, a foto fica só na lista.",
    "pontos": "Pontuação do registro: 1 ponto por padrão, 2 quando a legenda sugere "
    "exercício. Clique na metade esquerda da célula para tirar um ponto e na direita "
    "para somar.",
    "pontos_motivo": "O motivo que você escreveu na auditoria ao ajustar/confirmar a "
    "pontuação desta foto.",
    "remetente": "Quem mandou a foto (um número vira nome em ⚙ Ajustes → Remetentes).",
    "telefone_remetente": "O telefone do remetente, quando o rótulo da conversa é um número.",
    "data": "Data da mensagem no export (AAAA-MM-DD).",
    "hora": "Hora da mensagem no export.",
    "contexto": "Trecho do texto da própria mensagem, para dar contexto ao casamento.",
    "legenda": "O texto que veio junto da foto (a mensagem sem a marca da mídia).",
    "contexto_provavel": "A próxima mensagem da mesma pessoa — a pista do que a foto é, "
    "usada também para sugerir a pontuação.",
    "foto_arquivo": "Nome do arquivo da foto dentro do export (o WhatsApp renomeia para "
    "IMG-AAAAMMDD-WA####).",
    "foto_existe": "“sim” quando o arquivo da foto está de fato dentro do export (.zip).",
    "midia_pendente": "“sim” quando o arquivo NÃO veio no export: sobra a legenda e a "
    "marca da mídia, sem imagem nem metadados.",
}

#: A smaller set for when scrolling speed matters more than seeing everything.
_FAST_COLUMNS = ("incluido", "remetente", "data", "legenda", "foto_arquivo")

_ALL_COLUMN_KEYS = tuple(key for key, _, _, _ in _DISPLAY_COLUMNS)

#: Heading of each column (kept to redraw the sort arrow).
_COLUMN_LABELS = {key: title for key, title, _, _ in _DISPLAY_COLUMNS}


class StatusSink(Protocol):
    """Callable that shows a status message (``ok=False`` for errors)."""

    def __call__(self, message: str, *, ok: bool = True) -> None:
        """Show ``message``; ``ok=False`` marks it as an error."""


def _cell(row: Mapping[str, Any], column: str) -> str:
    if column == "incluido":
        return "☑" if row.get("incluir") else "☐"
    if column == "pontos":
        return f"− {points_of(row)} +"
    text = str(row.get(column, "") or "")
    if not text:
        return "—"
    return text if len(text) <= _CELL_TEXT else text[:_CELL_TEXT] + "…"


def _sort_value(row: Mapping[str, Any], column: str) -> Sortable:
    """What a column is sorted by: a number where that makes sense, text otherwise."""
    if column == "incluido":
        return int(bool(row.get("incluir")))
    if column == "pontos":
        return points_of(row)
    return str(row.get(column, "") or "").casefold()


class ResultsView(ttk.Frame):
    """The unified screen: import, filter, preview, include toggle, delete, save."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        store: Store,
        on_status: StatusSink,
        on_changed: Callable[[], None],
        on_save: Callable[[], None],
        on_import: Callable[[Path], None] | None = None,
        on_analytics: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, padding=8)
        self._store = store
        self._on_status = on_status
        self._on_changed = on_changed
        self._on_save = on_save
        self._on_import = on_import
        self._on_analytics = on_analytics
        self._source: Path | None = None
        self._filter_job: str | None = None
        self._rows: list[dict[str, Any]] = []
        self._row_by_id: dict[int, dict[str, Any]] = {}
        self._by_iid: dict[str, dict[str, Any]] = {}
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
        self._sort_column: str | None = None
        self._sort_descending = False
        self._build()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        drop_text = "Arraste o export do WhatsApp (.zip/.txt) aqui"
        if dnd_available():
            drop_text += " ou clique para escolher"
        self.drop = tk.Label(
            self,
            text=drop_text,
            relief="groove",
            borderwidth=2,
            background="#f2f2f2",
            foreground="#333333",
            cursor="hand2",
            height=3,
            justify="center",
        )
        self.drop.pack(fill="x")
        self.drop.bind("<Button-1>", lambda _event: self._choose_input())
        register_drop(self.drop, self._on_drop)

        import_row = ttk.Frame(self)
        import_row.pack(fill="x", pady=(4, 6))
        ttk.Button(import_row, text="Escolher arquivo…", command=self._choose_input).pack(
            side="left"
        )
        self.input_label = ttk.Label(
            import_row, text="nenhum arquivo escolhido", foreground="#c0392b"
        )
        self.input_label.pack(side="left", padx=8)
        self.import_button = ttk.Button(import_row, text="Gerar", command=self._generate)
        self.import_button.pack(side="left")

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        toggle_button = ttk.Button(
            toolbar, text="Incluir/Excluir da análise (Espaço)", command=self._toggle
        )
        toggle_button.pack(side="left")
        delete_button = ttk.Button(toolbar, text="Excluir (lixeira)", command=self._delete)
        delete_button.pack(side="left", padx=4)
        save_button = ttk.Button(toolbar, text="Salvar CSV…", command=self._on_save)
        save_button.pack(side="left", padx=4)
        columns_button = ttk.Button(toolbar, text="Colunas…", command=self._choose_columns)
        columns_button.pack(side="left", padx=4)
        self.points_button = ttk.Menubutton(toolbar, text="Pontos ▾")
        points_menu = tk.Menu(self.points_button, tearoff=False)
        points_menu.add_command(label="+1 ponto", command=partial(self._adjust_selected, 1))
        points_menu.add_command(label="−1 ponto", command=partial(self._adjust_selected, -1))
        points_menu.add_separator()
        points_menu.add_command(
            label="Reavaliar pelas legendas", command=self._rescore_from_captions
        )
        self.points_button.configure(menu=points_menu)
        self.points_button.pack(side="left", padx=4)
        self.count_label = ttk.Label(toolbar, text="sem dados")
        self.count_label.pack(side="left", padx=10)
        add_hints(
            {
                toggle_button: "Tira ou põe as linhas selecionadas na análise (as Análises "
                "só contam as marcadas com ☑).",
                delete_button: "Manda as linhas selecionadas para a lixeira (dá para "
                "restaurar em ⚙ Ajustes → Lixeira).",
                save_button: "Salva o que está na tela num CSV, incluindo os pontos e o "
                "motivo do ajuste.",
                columns_button: "Escolhe quais colunas a tabela mostra (tem um preset "
                "“Enxuto”, mais leve para rolar).",
                self.points_button: "Ajusta a pontuação das linhas selecionadas e reavalia "
                "as legendas de tudo que você ainda não decidiu.",
                self.count_label: "Quantas linhas estão na tela, do total, e a soma dos "
                "pontos mostrados.",
            }
        )

        filters = ttk.Frame(self)
        filters.pack(fill="x", pady=(4, 0))
        search_label = ttk.Label(filters, text="Buscar:")
        search_label.pack(side="left")
        self.query_var = tk.StringVar()
        query_entry = ttk.Entry(filters, textvariable=self.query_var, width=18)
        query_entry.pack(side="left", padx=(2, 4))
        query_entry.bind("<Return>", lambda _event: self._apply_filters())
        self.regex_var = tk.BooleanVar(value=False)
        regex_box = ttk.Checkbutton(
            filters, text="regex", variable=self.regex_var, command=self._apply_filters
        )
        regex_box.pack(side="left", padx=(0, 8))
        self.query_var.trace_add("write", lambda *_args: self._schedule_filter())
        sender_label = ttk.Label(filters, text="Remetente:")
        sender_label.pack(side="left")
        self.sender_var = tk.StringVar(value=_ALL_SENDERS)
        self.sender_box = ttk.Combobox(
            filters, textvariable=self.sender_var, width=18, state="readonly"
        )
        self.sender_box.pack(side="left", padx=(2, 8))
        self.sender_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_filters())
        start_label = ttk.Label(filters, text="De:")
        start_label.pack(side="left")
        self.start_var = tk.StringVar()
        start_entry = ttk.Entry(filters, textvariable=self.start_var, width=11)
        start_entry.pack(side="left")
        end_label = ttk.Label(filters, text="até:")
        end_label.pack(side="left", padx=(4, 2))
        self.end_var = tk.StringVar()
        end_entry = ttk.Entry(filters, textvariable=self.end_var, width=11)
        end_entry.pack(side="left")
        self.pending_var = tk.BooleanVar(value=False)
        pending_box = ttk.Checkbutton(
            filters, text="só sem arquivo", variable=self.pending_var, command=self._apply_filters
        )
        pending_box.pack(side="left", padx=8)
        self.auto_var = tk.BooleanVar(value=False)
        auto_box = ttk.Checkbutton(
            filters,
            text="só sugestões automáticas",
            variable=self.auto_var,
            command=self._apply_filters,
        )
        auto_box.pack(side="left", padx=8)
        filter_button = ttk.Button(filters, text="Filtrar", command=self._apply_filters)
        filter_button.pack(side="left")
        add_hints(
            {
                search_label: "Filtra a lista por texto. Marque “regex” para usar uma "
                "expressão regular (ex.: \\bpix\\b).",
                query_entry: "Filtra a lista por texto. Marque “regex” para usar uma "
                "expressão regular (ex.: \\bpix\\b).",
                regex_box: "Trata o que você digitou como expressão regular, não como "
                "texto literal.",
                sender_label: "Mostra só o que um remetente postou.",
                self.sender_box: "Mostra só o que um remetente postou.",
                start_label: "Recorte por data da mensagem (AAAA-MM-DD).",
                start_entry: "Recorte por data da mensagem (AAAA-MM-DD).",
                end_label: "Recorte por data da mensagem (AAAA-MM-DD).",
                end_entry: "Recorte por data da mensagem (AAAA-MM-DD).",
                pending_box: "Mostra só as fotos cujo arquivo não veio no export (sobra a "
                "legenda, sem imagem).",
                auto_box: "Mostra só as pontuações sugeridas pela legenda que você ainda "
                "não revisou na auditoria.",
                filter_button: "Aplica os filtros agora (eles também aplicam sozinhos ao "
                "mudar um campo).",
            }
        )

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
            self.tree.heading(column, text=title, command=partial(self._sort_by, column))
            self.tree.column(column, width=width, anchor=anchor, stretch=False)
        self.tree.tag_configure("pontuada", foreground=_POINTED_COLOUR)
        add_tree_hints(self.tree, _COLUMN_HINTS)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._show_preview())
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click, add="+")
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("+", partial(self._on_points_key, 1))
        self.tree.bind("-", partial(self._on_points_key, -1))
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
        self._rows = [dict(row) for row in rows]
        self._row_by_id = {int(row["id"]): row for row in self._rows if row.get("id") is not None}
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
        rows = filter_rows(
            self._rows,
            sender=None if sender == _ALL_SENDERS else sender,
            start=self.start_var.get().strip() or None,
            end=self.end_var.get().strip() or None,
            only_pending=bool(self.pending_var.get()),
            only_auto=bool(self.auto_var.get()),
        )
        term = self.query_var.get().strip()
        if not term:
            return rows
        if self.regex_var.get():
            try:
                pattern = re.compile(term, re.IGNORECASE)
            except re.error as exc:
                self._on_status(f"regex inválida: {exc}", ok=False)
                return rows
        else:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
        return [row for row in rows if pattern.search(_searchable(row))]

    def _schedule_filter(self) -> None:
        """Re-filter while typing, a moment after the last keystroke."""
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(_FILTER_DELAY_MS, self._apply_filters)

    # -- importing --------------------------------------------------------
    def _choose_input(self) -> None:
        chosen = filedialog.askopenfilename(title="Escolha o export", filetypes=_EXPORT_TYPES)
        if chosen:
            self._set_source(Path(chosen))

    def _on_drop(self, data: str) -> None:
        paths = self.tk.splitlist(data)
        if paths:
            self._set_source(Path(str(paths[0])))

    def _set_source(self, path: Path) -> None:
        self._source = path
        self.input_label.configure(text=str(path), foreground="#1a7f37")

    def _generate(self) -> None:
        if self._source is None:
            self._on_status("Escolha o arquivo exportado do WhatsApp (.zip ou .txt).", ok=False)
            return
        if self._on_import is not None:
            self._on_import(self._source)

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the *Gerar* button."""
        self.import_button.configure(state="disabled" if busy else "normal")

    def _apply_filters(self) -> None:
        visible = self._sorted_rows(self._visible_rows())
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for index, row in enumerate(visible):
            if self._db_backed:
                key = int(str(row["id"]))
                # Share the row object with ``self._rows`` so a toggle is seen
                # by the next click, the cell refresh and the CSV export.
                self._by_iid[str(key)] = self._row_by_id.get(key) or dict(row)
            else:
                self._by_iid[str(index)] = dict(row)
            iid = str(row["id"]) if self._db_backed else str(index)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=[_cell(row, key) for key in _ALL_COLUMN_KEYS],
                tags=self._tags(row),
            )
        points = sum(points_of(row) for row in visible)
        self.count_label.configure(
            text=f"{len(visible)} de {len(self._rows)} linha(s) · {points} ponto(s)"
        )

    # -- sorting ----------------------------------------------------------
    def _sorted_rows(self, rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Apply the current column order (the store's own order by default)."""
        column = self._sort_column
        if column is None:
            return rows
        return sort_items(
            rows, lambda row: _sort_value(row, column), descending=self._sort_descending
        )

    def _sort_by(self, column: str) -> None:
        """Sort by ``column``; clicking the same heading again flips the order."""
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._apply_headings()
        self._apply_filters()
        direction = "decrescente" if self._sort_descending else "crescente"
        self._on_status(f"Ordenado por {_COLUMN_LABELS[column]} ({direction}).")

    def _apply_headings(self) -> None:
        """Redraw every heading, marking the sorted column with an arrow."""
        for column, title in _COLUMN_LABELS.items():
            self.tree.heading(
                column,
                text=heading_label(
                    title,
                    active=column == self._sort_column,
                    descending=self._sort_descending,
                ),
            )

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
    def _tags(self, row: Mapping[str, Any]) -> tuple[str, ...]:
        """Row tags: a coloured line for the photos worth two points or more."""
        return ("pontuada",) if points_of(row) >= score.PONTOS_EXERCICIO else ()

    def _on_space(self, _event: tk.Event) -> str:
        self._toggle()
        return "break"

    def _on_points_key(self, delta: int, _event: tk.Event) -> str:
        """Sum or take a point from the selected rows (``+`` and ``-``)."""
        self._adjust_selected(delta)
        return "break"

    def _column_under(self, event: tk.Event) -> tuple[str | None, str | None]:
        """The row id and column key under the pointer, when it is over a cell."""
        if not self._db_backed or not self._visible_columns:
            return None, None
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None, None
        column_id = self.tree.identify_column(event.x)
        if not column_id.startswith("#") or not column_id[1:].isdigit():
            return None, None
        index = int(column_id[1:]) - 1
        if not 0 <= index < len(self._visible_columns):
            return None, None
        return self.tree.identify_row(event.y) or None, self._visible_columns[index]

    def _on_click(self, event: tk.Event) -> str | None:
        """Toggle the ☑/☐ or score the photo, depending on the clicked cell."""
        iid, column = self._column_under(event)
        if iid is None or column not in {"incluido", "pontos"}:
            return None
        row = self._by_iid.get(iid)
        if row is None or row.get("id") is None:
            return None
        if column == "incluido":
            included = not bool(row.get("incluir"))
            self._set_included([int(row["id"])], included)
            self.tree.set(iid, "incluido", "☑" if included else "☐")
            state = "dentro" if included else "fora"
            self._on_status(f"{row.get('remetente', '')} agora está {state} da análise.")
            return "break"
        delta = 1 if self._is_plus_half(event, iid, column) else -1
        self._adjust_points([int(row["id"])], delta)
        return "break"

    def _is_plus_half(self, event: tk.Event, iid: str, column: str) -> bool:
        """Whether the pointer is on the right (``+``) half of the score cell."""
        box = self.tree.bbox(iid, column)
        if not box:
            return True
        left, _top, width, _height = box
        return event.x >= left + width / 2

    def _on_double_click(self, event: tk.Event) -> str | None:
        """Open the viewer — except on the ☑/☐ and Pontos cells, already handled."""
        _iid, column = self._column_under(event)
        if column in {"incluido", "pontos"}:
            return "break"
        self._open_viewer()
        return None

    def _set_included(self, ids: list[int], included: bool) -> None:
        """Persist the flag, update the cached rows and refresh the analytics."""
        self._store.set_included(ids, included)
        for row in self._rows:
            if row.get("id") in ids:
                row["incluir"] = 1 if included else 0
        if self._on_analytics is not None:
            self._on_analytics()

    def _refresh_included_cells(self, ids: list[int]) -> None:
        for iid, row in self._by_iid.items():
            if row.get("id") in ids:
                self.tree.set(iid, "incluido", "☑" if row.get("incluir") else "☐")

    def _adjust_points(self, ids: list[int], delta: int) -> None:
        """Persist the new score, update the cached rows and redraw the cell."""
        self._store.adjust_points(ids, delta)
        adjusted = [row for row in self._rows if row.get("id") in ids]
        for row in adjusted:
            row["pontos"] = max(points_of(row) + delta, score.PONTOS_MIN)
            row["pontos_origem"] = score.ORIGEM_MANUAL
        self._refresh_points(ids)
        if self._on_analytics is not None:
            self._on_analytics()
        if len(adjusted) == 1:
            row = adjusted[0]
            self._on_status(
                f"{row.get('remetente', '')}: {points_of(row)} ponto(s) — ajustado por você."
            )
        else:
            self._on_status(f"{len(adjusted)} linha(s) ajustada(s) em {delta:+d} ponto(s).")

    def _refresh_points(self, ids: list[int]) -> None:
        """Redraw the score cell (and its colour) of the rows already on screen."""
        for iid, row in self._by_iid.items():
            if row.get("id") not in ids:
                continue
            self.tree.set(iid, "pontos", _cell(row, "pontos"))
            self.tree.item(iid, tags=self._tags(row))

    def _adjust_selected(self, delta: int) -> None:
        """Score every selected row by ``delta`` points."""
        ids = self._selected_ids()
        if not ids:
            self._on_status("Selecione uma linha (ou clique no −/+ da coluna Pontos).", ok=False)
            return
        self._adjust_points(ids, delta)

    def _rescore_from_captions(self) -> None:
        """Re-apply the caption heuristic everywhere, manual scores untouched."""
        rows = self._store.rows(include_deleted=True)
        changed = self._store.rescore_auto(score.suggestions(rows))
        self._on_changed()
        self._on_status(
            f"{changed} pontuação(ões) atualizada(s) pelas legendas."
            if changed
            else "Nenhuma sugestão nova nas legendas."
        )

    def _toggle(self) -> None:
        if not self._db_backed:
            self._on_status("A análise só existe para a lista de fotos (aba Explorar).", ok=False)
            return
        ids = self._selected_ids()
        if not ids:
            self._on_status("Selecione uma linha (ou clique no ☑/☐ da primeira coluna).", ok=False)
            return
        rows = [row for row in self._rows if row.get("id") in ids]
        included = all(bool(row.get("incluir")) for row in rows)
        self._set_included(ids, not included)
        self._refresh_included_cells(ids)
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
