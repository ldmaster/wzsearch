"""Score audit window: what each photo scores, and why.

The audit answers the questions the score raises: which records the captions
flagged (and with which words), which ones somebody already reviewed, and which
ones left the usual 1–2 range. The selected record shows the photo itself and
what the file says about it (name, size, dimensions, EXIF when it survived), and
whatever is written in the reason field is saved together with the adjustment.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from functools import partial
from tkinter import ttk
from typing import Any, Literal

from . import images, photometa, score, senders
from .analytics import (
    SITUATIONS,
    audit_rows,
    points_of,
    score_audit,
    score_reason,
    score_situation,
    situation_label,
)
from .gui_results import StatusSink
from .hint import add_hint, add_hints, add_tree_hints
from .scroll import bind_wheel
from .sorting import Sortable, heading_label, sort_items
from .store import Store

_ALL_SENDERS = "(todos)"
_CELL_TEXT = 70
_PREVIEW_BOX = 230
_PREVIEW_PAD = 12
_PREVIEW_SIDE = _PREVIEW_BOX + _PREVIEW_PAD * 2
_VIEWER_BOX = 900
_DETAIL_DELAY_MS = 60
_PREVIEW_CACHE_MAX = 40

_DISPLAY_COLUMNS: tuple[tuple[str, str, int, Literal["w", "center"]], ...] = (
    ("pontos", "Pontos", 70, "center"),
    ("situacao", "Situação", 140, "w"),
    ("remetente", "Remetente", 160, "w"),
    ("data", "Data", 90, "w"),
    ("legenda", "Legenda", 200, "w"),
    ("motivo", "Sugerido por", 230, "w"),
    ("seu_motivo", "Seu motivo", 230, "w"),
)

_COLUMN_LABELS = {key: title for key, title, _, _ in _DISPLAY_COLUMNS}

_COLUMN_HINTS = {
    "pontos": "Pontuação do registro: 1 por padrão, 2 quando a legenda sugere exercício.",
    "situacao": "Se a pontuação foi sugerida pela legenda (a revisar), confirmada por "
    "você ou ajustada na mão; “fora do padrão” é o que passou de 2 pontos.",
    "remetente": "Quem postou a foto.",
    "data": "Data da mensagem no export.",
    "legenda": "O texto que veio junto da foto.",
    "motivo": "Por que o app deu essa pontuação: a palavra que casou e onde apareceu "
    "(na legenda ou na mensagem seguinte da mesma pessoa).",
    "seu_motivo": "O que você escreveu no campo “Motivo do ajuste” ao mexer nesta foto.",
}

_SORT_KEYS: dict[str, Callable[[Mapping[str, Any]], Sortable]] = {
    "pontos": lambda row: points_of(row),
    "situacao": lambda row: situation_label(row).casefold(),
    "remetente": lambda row: str(row.get("remetente", "") or "").casefold(),
    "data": lambda row: str(row.get("data", "") or ""),
    "legenda": lambda row: str(row.get("legenda", "") or "").casefold(),
    "motivo": lambda row: score_reason(row).casefold(),
    "seu_motivo": lambda row: str(row.get("pontos_motivo", "") or "").casefold(),
}


def _cell(row: Mapping[str, Any], column: str) -> str:
    """One cell of the audit table, with ``—`` where there is nothing to show."""
    if column == "pontos":
        return str(points_of(row))
    if column == "situacao":
        text = situation_label(row)
    elif column == "motivo":
        text = score_reason(row)
    elif column == "seu_motivo":
        text = str(row.get("pontos_motivo", "") or "")
    else:
        text = str(row.get(column, "") or "")
    if not text:
        return "—"
    return text if len(text) <= _CELL_TEXT else text[:_CELL_TEXT] + "…"


class ScoreAuditWindow(ttk.Frame):
    """Table of the scored records, with the situation filter and bulk actions."""

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
        self._rows: list[dict[str, Any]] = []
        self._by_iid: dict[str, Mapping[str, Any]] = {}
        self._sort_column: str | None = None
        self._sort_descending = False
        self._preview_cache: dict[int, Any] = {}
        self._facts_cache: dict[int, photometa.PhotoFacts] = {}
        self._photo: Any = None
        self._viewer_image: Any = None
        self._shown_id: int | None = None
        self._detail_job: str | None = None
        self._build()
        self.reload()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        resumo = ttk.Frame(self)
        resumo.pack(fill="x")
        self.summary_label = ttk.Label(resumo, text="sem dados", font=("TkDefaultFont", 11, "bold"))
        self.summary_label.pack(side="left")
        self.count_label = ttk.Label(resumo, text="", foreground="#666")
        self.count_label.pack(side="right")

        filtros = ttk.Frame(self)
        filtros.pack(fill="x", pady=(6, 0))
        most_label = ttk.Label(filtros, text="Mostrar:")
        most_label.pack(side="left")
        self.situation_var = tk.StringVar(value=SITUATIONS[0][1])
        self.situation_box = ttk.Combobox(
            filtros,
            textvariable=self.situation_var,
            values=[label for _key, label in SITUATIONS],
            state="readonly",
            width=32,
        )
        self.situation_box.pack(side="left", padx=6)
        self.situation_box.bind("<<ComboboxSelected>>", lambda _event: self._fill())
        sender_label = ttk.Label(filtros, text="Remetente:")
        sender_label.pack(side="left", padx=(8, 0))
        self.sender_var = tk.StringVar(value=_ALL_SENDERS)
        self.sender_box = ttk.Combobox(
            filtros, textvariable=self.sender_var, width=24, state="readonly"
        )
        self.sender_box.pack(side="left", padx=6)
        self.sender_box.bind("<<ComboboxSelected>>", lambda _event: self._fill())
        add_hints(
            {
                most_label: "Separa o que a legenda sugeriu (a revisar), o que você já "
                "decidiu e o que saiu do padrão (3 pontos ou mais).",
                self.situation_box: "Separa o que a legenda sugeriu (a revisar), o que "
                "você já decidiu e o que saiu do padrão (3 pontos ou mais).",
                sender_label: "Mostra só o que um remetente postou.",
                self.sender_box: "Mostra só o que um remetente postou.",
            }
        )

        acoes = ttk.Frame(self)
        acoes.pack(fill="x", pady=(6, 0))
        confirm_button = ttk.Button(acoes, text="Confirmar sugestão", command=self._confirm)
        confirm_button.pack(side="left")
        plus_button = ttk.Button(acoes, text="+1 ponto", command=partial(self._adjust, 1))
        plus_button.pack(side="left", padx=4)
        minus_button = ttk.Button(acoes, text="−1 ponto", command=partial(self._adjust, -1))
        minus_button.pack(side="left", padx=4)
        rescore_button = ttk.Button(acoes, text="Reavaliar pelas legendas", command=self._rescore)
        rescore_button.pack(side="left", padx=(12, 0))
        add_hints(
            {
                confirm_button: "Aceita a sugestão como está e tira a linha das pendências "
                "(o “Reavaliar” não mexe mais nela).",
                plus_button: "Soma um ponto nas linhas selecionadas; a linha passa a ser "
                "sua e o “Reavaliar” não mexe mais nela.",
                minus_button: "Tira um ponto das linhas selecionadas; o mínimo é 1.",
                rescore_button: "Relê as legendas de tudo que você ainda não decidiu.",
            }
        )

        motivo_row = ttk.Frame(self)
        motivo_row.pack(fill="x", pady=(6, 0))
        motivo_label = ttk.Label(motivo_row, text="Motivo do ajuste (opcional):")
        motivo_label.pack(side="left")
        self.motivo_var = tk.StringVar()
        self.motivo_entry = ttk.Entry(motivo_row, textvariable=self.motivo_var)
        self.motivo_entry.pack(side="left", fill="x", expand=True, padx=6)
        motivo_hint = (
            "Escreva por que você está mexendo na pontuação: fica gravado na foto (coluna "
            "“Seu motivo”) e vai no CSV. Vale para as linhas selecionadas quando você "
            "confirma ou ajusta; depois o campo é limpo."
        )
        add_hints({motivo_label: motivo_hint, self.motivo_entry: motivo_hint})

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))
        panes.add(self._build_table(panes), weight=3)
        panes.add(self._build_side(panes), weight=1)

    def _build_table(self, master: tk.Misc) -> ttk.Frame:
        table = ttk.Frame(master)
        self.tree = ttk.Treeview(table, show="headings", selectmode="extended")
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.configure(columns=[key for key, _, _, _ in _DISPLAY_COLUMNS])
        for column, title, width, anchor in _DISPLAY_COLUMNS:
            self.tree.heading(column, text=title, command=partial(self._sort_by, column))
            self.tree.column(column, width=width, anchor=anchor, stretch=False)
        self.tree.tag_configure("pontuada", foreground="#1a7f37")
        add_tree_hints(self.tree, _COLUMN_HINTS)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._schedule_detail())
        self.tree.bind("<Double-1>", lambda _event: self._open_viewer())
        bind_wheel(self.tree, lambda rows: self.tree.yview_scroll(rows, "units"))
        return table

    def _build_side(self, master: tk.Misc) -> ttk.Frame:
        side = ttk.Frame(master, padding=8)
        self.photo_canvas = tk.Canvas(
            side,
            width=_PREVIEW_SIDE,
            height=_PREVIEW_SIDE,
            background="#f2f2f2",
            highlightthickness=0,
        )
        self.photo_canvas.pack()
        add_hint(
            self.photo_canvas,
            "A foto desta linha, lida do banco (nada é extraído para o disco). Duplo "
            "clique na tabela abre a imagem grande.",
        )
        self.detail = tk.Text(side, height=12, wrap="word")
        self.detail.pack(fill="both", expand=True, pady=(6, 0))
        self.detail.configure(state="disabled")
        add_hint(self.detail, "A legenda, o contexto e o que o arquivo diz desta foto.")
        return side

    # -- data -------------------------------------------------------------
    def reload(self) -> None:
        """Re-read the records from the store (the main window keeps them in sync)."""
        self._rows = senders.rename_rows(self._store.rows())
        nomes = sorted({str(row.get("remetente", "") or "") for row in self._rows} - {""})
        self.sender_box.configure(values=[_ALL_SENDERS, *nomes])
        if self.sender_var.get() not in [*nomes, _ALL_SENDERS]:
            self.sender_var.set(_ALL_SENDERS)
        totals = score_audit(self._rows)
        self.summary_label.configure(
            text=(
                f"{totals.photos} foto(s) · {totals.points} ponto(s) · "
                f"{totals.suggestions} sugestão(ões) a revisar · "
                f"{totals.manual} ajuste(s) seu(s)"
                + (f" · {totals.over} fora do padrão" if totals.over else "")
            )
        )
        self._fill()

    def _situation_key(self) -> str:
        label = self.situation_var.get()
        return next((key for key, text in SITUATIONS if text == label), SITUATIONS[0][0])

    def _fill(self) -> None:
        sender = self.sender_var.get()
        visible = audit_rows(
            self._rows,
            self._situation_key(),
            None if sender == _ALL_SENDERS else sender,
        )
        visible = self._sorted(visible)
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for index, row in enumerate(visible):
            iid = str(index)
            self._by_iid[iid] = row
            tags = ("pontuada",) if points_of(row) >= score.PONTOS_EXERCICIO else ()
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=[_cell(row, key) for key, _, _, _ in _DISPLAY_COLUMNS],
                tags=tags,
            )
        self.count_label.configure(text=f"{len(visible)} de {len(self._rows)} registro(s)")

    # -- sorting ----------------------------------------------------------
    def _sorted(self, rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        column = self._sort_column
        if column is None:
            return rows
        return sort_items(rows, _SORT_KEYS[column], descending=self._sort_descending)

    def _sort_by(self, column: str) -> None:
        """Sort by ``column``; clicking the same heading again flips the order."""
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        for key, title in _COLUMN_LABELS.items():
            self.tree.heading(
                key,
                text=heading_label(
                    title, active=key == self._sort_column, descending=self._sort_descending
                ),
            )
        self._fill()

    # -- actions ----------------------------------------------------------
    def _selected(self) -> list[Mapping[str, Any]]:
        return [self._by_iid[iid] for iid in self.tree.selection() if iid in self._by_iid]

    def _selected_ids(self) -> list[int]:
        return [int(str(row["id"])) for row in self._selected() if row.get("id") is not None]

    def _nota(self) -> str | None:
        """The reason typed in the field (``None`` when it is empty)."""
        texto = self.motivo_var.get().strip()
        return texto or None

    def _confirm(self) -> None:
        """Accept the suggested scores of the selected records as they are."""
        sugestoes = [row for row in self._selected() if score_situation(row) == "auto"]
        if not sugestoes:
            self._on_status("Selecione uma sugestão automática para confirmar.", ok=False)
            return
        motivo = self._nota()
        confirmados = self._store.confirm_points(
            [int(str(row["id"])) for row in sugestoes], motivo=motivo
        )
        self._on_changed()
        self._on_status(
            f"{confirmados} sugestão(ões) confirmada(s)" + (" com o seu motivo." if motivo else ".")
        )
        self.motivo_var.set("")

    def _adjust(self, delta: int) -> None:
        """Sum or take a point from the selected records."""
        ids = self._selected_ids()
        if not ids:
            self._on_status("Selecione uma ou mais linhas para ajustar a pontuação.", ok=False)
            return
        motivo = self._nota()
        self._store.adjust_points(ids, delta, motivo=motivo)
        self._on_changed()
        self._on_status(
            f"{len(ids)} registro(s) ajustado(s) em {delta:+d} ponto(s)"
            + (" com o seu motivo." if motivo else ".")
        )
        self.motivo_var.set("")

    def _rescore(self) -> None:
        """Re-read every caption, leaving the scores you decided untouched."""
        changed = self._store.rescore_auto(score.suggestions(self._store.rows()))
        self._on_changed()
        self._on_status(
            f"{changed} pontuação(ões) atualizada(s) pelas legendas."
            if changed
            else "Nenhuma sugestão nova nas legendas."
        )

    # -- selection detail -------------------------------------------------
    def _selected_row(self) -> Mapping[str, Any] | None:
        selection = self.tree.selection()
        return self._by_iid.get(selection[0]) if selection else None

    def _schedule_detail(self) -> None:
        """Debounce the detail so arrowing through the table stays smooth."""
        if self._detail_job is not None:
            self.after_cancel(self._detail_job)
        self._detail_job = self.after(_DETAIL_DELAY_MS, self._render_detail)

    def _media(self, row: Mapping[str, Any]) -> bytes | None:
        if row.get("id") is None:
            return None
        return self._store.media(int(str(row["id"])))

    def _cached_photo(self, row: Mapping[str, Any], data: bytes | None) -> Any:
        row_id = int(str(row["id"]))
        if row_id not in self._preview_cache:
            image = images.image_from_bytes(data, _PREVIEW_BOX)
            self._preview_cache[row_id] = images.to_photoimage(image)
            if len(self._preview_cache) > _PREVIEW_CACHE_MAX:
                self._preview_cache.clear()
        return self._preview_cache[row_id]

    def _facts(self, row: Mapping[str, Any], data: bytes | None) -> photometa.PhotoFacts:
        row_id = int(str(row["id"]))
        if row_id not in self._facts_cache:
            self._facts_cache[row_id] = photometa.describe(
                str(row.get("foto_arquivo", "") or ""),
                data,
                message_date=str(row.get("data", "") or ""),
                message_time=str(row.get("hora", "") or "")[:5],
            )
        return self._facts_cache[row_id]

    def _render_detail(self) -> None:
        self._detail_job = None
        row = self._selected_row()
        if row is None:
            return
        data = self._media(row)
        self._draw_photo(row, data)
        if row.get("id") is None:
            return
        facts = self._facts(row, data)
        hora = str(row.get("hora", "") or "")[:5]
        linhas = [
            f"{row.get('remetente', '')} · {row.get('data', '')} {hora}",
            f"Pontos: {points_of(row)} · {situation_label(row)}",
            "",
            f"Legenda: {row.get('legenda', '') or '—'}",
            f"Contexto seguinte: {row.get('contexto_provavel', '') or '—'}",
            f"Sugerido por: {score_reason(row) or '—'}",
            f"Seu motivo: {row.get('pontos_motivo', '') or '—'}",
            "",
            "O que o arquivo diz:",
            *photometa.describe_lines(
                facts,
                message_date=str(row.get("data", "") or ""),
                message_time=hora,
            ),
        ]
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", "\n".join(linhas))
        self.detail.configure(state="disabled")

    def _draw_photo(self, row: Mapping[str, Any], data: bytes | None) -> None:
        row_id = int(str(row["id"])) if row.get("id") is not None else None
        if row_id is not None and self._shown_id == row_id:
            return
        self._shown_id = row_id
        canvas = self.photo_canvas
        canvas.delete("all")
        photo = self._cached_photo(row, data) if row_id is not None else None
        if photo is None:
            faltando = (
                "(sem o arquivo no export — só a legenda)"
                if not row.get("foto_arquivo")
                else "(imagem indisponível)"
            )
            canvas.create_text(
                _PREVIEW_SIDE / 2,
                _PREVIEW_SIDE / 2,
                text=faltando,
                fill="#666",
                width=_PREVIEW_BOX,
            )
            self._photo = None
            return
        canvas.create_image(_PREVIEW_SIDE / 2, _PREVIEW_SIDE / 2, image=photo)
        self._photo = photo

    def _open_viewer(self) -> None:
        """Open the selected photo bigger (double click)."""
        row = self._selected_row()
        if row is None or row.get("id") is None:
            return
        image = images.image_from_bytes(self._media(row), _VIEWER_BOX)
        if image is None:
            self._on_status("Esta linha não tem foto para abrir.", ok=False)
            return
        window = tk.Toplevel(self)
        window.title(f"{row.get('remetente', '')} — {row.get('foto_arquivo', '')}")
        self._viewer_image = images.to_photoimage(image)
        tk.Label(window, image=self._viewer_image).pack()
