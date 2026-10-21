"""Analytics tab: posting-frequency metrics, rankings, charts and a heatmap."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from functools import partial
from tkinter import ttk
from typing import Literal

from .analytics import WEEKDAY_LABELS, PhotoStats, SenderDetail, filter_rows, photo_stats
from .chart import BarChart, Heatmap
from .hint import add_hint, add_hints, add_tree_hints
from .scroll import bind_wheel
from .sorting import Sortable, heading_label, sort_items

_ALL = "(todos)"

_METRIC_LABELS = {
    "total": "Total de fotos",
    "with_file": "Com o arquivo no export",
    "pending": "Sem o arquivo no export",
    "total_points": "Pontuação total",
    "avg_points": "Média de pontos por foto",
    "exercise": "Fotos de exercício (2 pts)",
    "auto_points": "Sugestões a revisar",
    "without_points": "Sem pontuação (sem legenda)",
    "participants": "Participantes",
    "period": "Período",
    "active_days": "Dias com fotos",
    "avg_per_day": "Média por dia ativo",
    "median_per_day": "Mediana por dia ativo",
    "gap_hours": "Intervalo médio entre fotos",
    "gap_median": "Intervalo mediano entre fotos",
    "streak": "Maior sequência (dias seguidos)",
    "peak_hour": "Hora mais ativa",
    "peak_weekday": "Dia da semana mais ativo",
    "peak_month": "Mês mais ativo",
    "with_caption": "Fotos com legenda",
    "top3": "Concentração (top 3 remetentes)",
    "most_active": "Mais ativa",
    "least_active": "Menos ativa",
}

#: What each number in the summary means (shown when the pointer rests on it).
_METRIC_HINTS = {
    "total": "Quantas fotos entraram na análise: as ativas e marcadas com ☑ na aba "
    "Explorar. Uma linha = uma mensagem com mídia.",
    "with_file": "Fotos cujo arquivo veio dentro do export (.zip). É o que permite ver "
    "a imagem e ler os metadados do arquivo.",
    "pending": "Fotos que existem no chat mas cujo arquivo NÃO veio no export: sobra só "
    "a legenda e a marca da mídia na mensagem. Sem arquivo não há imagem, tamanho nem "
    "metadados — costuma acontecer com mídia que expirou, foi apagada ou que o WhatsApp "
    "não incluiu na exportação (veja Ajuda → Exportar com as mídias).",
    "total_points": "Soma das pontuações: 1 ponto quando a foto tem legenda, 2 quando a "
    "legenda (ou a mensagem seguinte da mesma pessoa) fala de exercício, e 0 quando veio "
    "sem legenda. Você ajusta na lista ou na auditoria.",
    "avg_points": "Pontuação total dividida pelo número de fotos analisadas.",
    "exercise": "Fotos valendo 2 pontos ou mais: as sugeridas pela legenda que você "
    "aceitou e as que você pontuou na mão.",
    "auto_points": "Sugestões automáticas da legenda que ainda não foram revisadas — "
    "abra a auditoria para confirmar ou corrigir.",
    "without_points": "Fotos que vieram sem legenda e por isso ficaram com zero ponto. "
    "Elas aparecem no filtro “Sem pontuação (sem legenda)” da auditoria, onde você pode "
    "dar pontos a elas.",
    "participants": "Quantas pessoas diferentes postaram fotos no recorte.",
    "period": "Da primeira à última foto do recorte.",
    "active_days": "Quantos dias diferentes têm pelo menos uma foto.",
    "avg_per_day": "Média de fotos por dia que teve alguma postagem.",
    "median_per_day": "Metade dos dias ativos tem menos fotos que isso, a outra metade tem mais.",
    "gap_hours": "Tempo médio entre uma foto e a seguinte.",
    "gap_median": "Tempo típico entre uma foto e a seguinte (menos sensível aos extremos).",
    "streak": "O maior número de dias seguidos com fotos.",
    "peak_hour": "A hora do dia com mais fotos.",
    "peak_weekday": "O dia da semana com mais fotos.",
    "peak_month": "O mês com mais fotos.",
    "with_caption": "Fotos que vieram com texto junto da mídia (a legenda).",
    "top3": "Quanto das fotos se concentra nos 3 remetentes que mais postam.",
    "most_active": "Quem mais postou fotos no recorte.",
    "least_active": "Quem menos postou fotos no recorte.",
}

_METRIC_ORDER = tuple(_METRIC_LABELS)

_CHART_TITLES = {
    "per_day": "Fotos por dia",
    "per_month": "Fotos por mês",
    "per_hour": "Fotos por hora do dia",
    "per_weekday": "Fotos por dia da semana",
    "points_by_sender": "Pontos por remetente",
    "caption_words": "Palavras mais usadas nas legendas",
    "extensions": "Tipos de arquivo",
}

_CHART_HINTS = {
    "per_day": "Uma barra por dia com foto, no recorte escolhido.",
    "per_month": "Fotos agrupadas por mês.",
    "per_hour": "Distribuição das fotos pelas 24 horas (fuso do horário do export).",
    "per_weekday": "Fotos por dia da semana.",
    "points_by_sender": "Pontuação somada de cada remetente (1 ponto por foto, 2 nas de "
    "exercício).",
    "caption_words": "Palavras que mais aparecem nas legendas, sem as muito comuns.",
    "extensions": "Extensão dos arquivos que vieram no export (jpg, heic, png…).",
}

#: Pixels per wheel step (a fixed step feels the same for mouse and trackpad).
_SCROLL_STEP = 24

_SENDER_COLUMNS: tuple[tuple[str, str, int, Literal["w", "e"]], ...] = (
    ("remetente", "Remetente", 200, "w"),
    ("fotos", "Fotos", 60, "e"),
    ("pct", "%", 60, "e"),
    ("arquivo", "Com arquivo", 90, "e"),
    ("pendentes", "Sem arquivo", 80, "e"),
    ("pontos", "Pontos", 70, "e"),
    ("exercicio", "2 pts", 60, "e"),
    ("dias", "Dias", 60, "e"),
    ("primeira", "1ª foto", 100, "w"),
    ("ultima", "Última", 100, "w"),
)

#: What each per-sender column means.
_SENDER_HINTS = {
    "remetente": "Quem postou (o número vira nome em ⚙ Ajustes → Remetentes).",
    "fotos": "Quantas fotos essa pessoa postou no recorte.",
    "pct": "Fatia desse remetente no total de fotos.",
    "arquivo": "Quantas dessas fotos têm o arquivo dentro do export.",
    "pendentes": "Quantas ficaram sem o arquivo no export (só a legenda).",
    "pontos": "Pontuação somada das fotos dessa pessoa.",
    "exercicio": "Quantas fotos valem 2 pontos ou mais.",
    "dias": "Em quantos dias diferentes essa pessoa postou.",
    "primeira": "Data da primeira foto dela no recorte.",
    "ultima": "Data da última foto dela no recorte.",
}

#: Heading of each per-sender column (kept to redraw the sort arrow).
_SENDER_LABELS = {column: title for column, title, _, _ in _SENDER_COLUMNS}

#: What each per-sender column is sorted by.
_SENDER_SORT_KEYS: dict[str, Callable[[SenderDetail], Sortable]] = {
    "remetente": lambda detail: detail.sender.casefold(),
    "fotos": lambda detail: detail.count,
    "pct": lambda detail: detail.count,
    "arquivo": lambda detail: detail.with_file,
    "pendentes": lambda detail: detail.pending,
    "pontos": lambda detail: detail.points,
    "exercicio": lambda detail: detail.exercise,
    "dias": lambda detail: detail.active_days,
    "primeira": lambda detail: detail.first or "",
    "ultima": lambda detail: detail.last or "",
}


class AnalyticsView(ttk.Frame):
    """Scrollable panel with summary metrics, rankings, charts and a heatmap."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=8)
        canvas = tk.Canvas(self, highlightthickness=0, yscrollincrement=_SCROLL_STEP)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._canvas = canvas

        self._inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        self._metrics: dict[str, tk.StringVar] = {}
        self.charts: dict[str, BarChart] = {}
        self._all_rows: list[dict[str, object]] = []
        self._sender_rows: list[SenderDetail] = []
        self._sender_total = 1
        self._sender_sort: str | None = None
        self._sender_descending = False
        self.sender_var = tk.StringVar(value=_ALL)
        self._build()
        # A roda rola a página com o ponteiro em qualquer ponto dela. A tabela
        # "Por remetente" é a exceção: ela tem altura fixa e barra própria, então
        # a roda sobre ela rola a tabela (e o "break" impede a página de se mexer).
        bind_wheel(self.senders, lambda rows: self.senders.yview_scroll(rows, "units"))
        bind_wheel(self.top_days, self.scroll)

    def scroll(self, rows: int) -> None:
        """Scroll the page by ``rows`` wheel steps."""
        self._canvas.yview_scroll(rows, "units")

    def _build(self) -> None:
        filter_box = ttk.Frame(self._inner)
        filter_box.pack(fill="x", pady=(0, 8))
        filter_label = ttk.Label(filter_box, text="Análises de:")
        filter_label.pack(side="left")
        self.sender_box = ttk.Combobox(
            filter_box, textvariable=self.sender_var, width=28, state="readonly"
        )
        self.sender_box.pack(side="left", padx=6)
        self.sender_box.bind("<<ComboboxSelected>>", lambda _event: self._recompute())
        self.scope_label = ttk.Label(filter_box, text="geral", foreground="#666")
        self.scope_label.pack(side="left", padx=8)
        add_hints(
            {
                filter_label: "Escolha “(todos)” para ver o grupo inteiro ou um remetente "
                "só — o resumo, as tabelas e os gráficos seguem esse filtro.",
                self.sender_box: "Escolha “(todos)” para ver o grupo inteiro ou um "
                "remetente só — o resumo, as tabelas e os gráficos seguem esse filtro.",
                self.scope_label: "Mostra qual recorte está sendo analisado agora.",
            }
        )

        metrics_box = ttk.LabelFrame(self._inner, text="Resumo", padding=8)
        metrics_box.pack(fill="x", pady=(0, 10))
        for key in _METRIC_ORDER:
            row = ttk.Frame(metrics_box)
            row.pack(fill="x")
            label = ttk.Label(row, text=_METRIC_LABELS[key], width=32)
            label.pack(side="left")
            variable = tk.StringVar(value="—")
            value_label = ttk.Label(row, textvariable=variable)
            value_label.pack(side="left")
            hint = _METRIC_HINTS.get(key, "")
            add_hints({label: hint, value_label: hint})
            self._metrics[key] = variable

        senders_box = ttk.LabelFrame(self._inner, text="Por remetente", padding=8)
        senders_box.pack(fill="x", pady=(0, 10))
        senders_table = ttk.Frame(senders_box)
        senders_table.pack(fill="x")
        self.senders = ttk.Treeview(senders_table, show="headings", height=8)
        senders_y = ttk.Scrollbar(senders_table, orient="vertical", command=self.senders.yview)
        senders_x = ttk.Scrollbar(senders_table, orient="horizontal", command=self.senders.xview)
        self.senders.configure(yscrollcommand=senders_y.set, xscrollcommand=senders_x.set)
        self.senders.configure(columns=[column for column, _, _, _ in _SENDER_COLUMNS])
        for column, title, width, anchor in _SENDER_COLUMNS:
            self.senders.heading(column, text=title, command=partial(self._sort_senders, column))
            self.senders.column(column, width=width, anchor=anchor, stretch=False)
        senders_y.pack(side="right", fill="y")
        senders_x.pack(side="bottom", fill="x")
        self.senders.pack(side="left", fill="x", expand=True)
        add_tree_hints(self.senders, _SENDER_HINTS)

        heat_box = ttk.LabelFrame(
            self._inner, text="Quando postam (dia da semana × hora)", padding=6
        )
        heat_box.pack(fill="x", pady=(0, 10))
        add_hint(
            heat_box,
            "Quando cada pessoa posta: as linhas são os dias da semana, as colunas as "
            "horas, e quanto mais escuro o quadrado, mais fotos naquela hora.",
        )
        self.heatmap = Heatmap(heat_box)
        self.heatmap.pack(anchor="w")

        for key, title in _CHART_TITLES.items():
            block = ttk.LabelFrame(self._inner, text=title, padding=6)
            block.pack(fill="x", pady=(0, 10))
            add_hint(block, _CHART_HINTS.get(key, ""))
            chart = BarChart(block, height=150)
            chart.pack(fill="x")
            self.charts[key] = chart

        top = ttk.LabelFrame(self._inner, text="Dias mais movimentados", padding=8)
        top.pack(fill="x")
        self.top_days = ttk.Treeview(top, columns=("data", "fotos"), show="headings", height=6)
        self.top_days.heading("data", text="Data")
        self.top_days.heading("fotos", text="Fotos")
        self.top_days.column("data", width=200, anchor="w")
        self.top_days.column("fotos", width=70, anchor="e")
        self.top_days.pack(fill="x")
        add_tree_hints(
            self.top_days,
            {
                "data": "Os 10 dias com mais fotos no recorte.",
                "fotos": "Quantas fotos naquele dia.",
            },
        )

    def _render_senders(self) -> None:
        """Fill the per-sender table in the chosen order."""
        rows = self._sorted_senders()
        # Altura fixa (até 12 linhas) com barra própria: a tabela pode crescer
        # muito e nem por isso empurra a página inteira para baixo.
        self.senders.configure(height=max(3, min(len(rows), 12)))
        self.senders.delete(*self.senders.get_children())
        total = self._sender_total or 1
        for detail in rows:
            self.senders.insert(
                "",
                "end",
                values=(
                    detail.sender,
                    detail.count,
                    f"{detail.count / total:.0%}",
                    detail.with_file,
                    detail.pending,
                    detail.points,
                    detail.exercise,
                    detail.active_days,
                    detail.first or "—",
                    detail.last or "—",
                ),
            )

    def _sorted_senders(self) -> list[SenderDetail]:
        """The per-sender rows ordered by the clicked column (most active first)."""
        column = self._sender_sort
        if column is None:
            return self._sender_rows
        return sort_items(
            self._sender_rows, _SENDER_SORT_KEYS[column], descending=self._sender_descending
        )

    def _sort_senders(self, column: str) -> None:
        """Sort the table by ``column``; clicking the same heading flips it."""
        if self._sender_sort == column:
            self._sender_descending = not self._sender_descending
        else:
            self._sender_sort = column
            self._sender_descending = False
        for key, title in _SENDER_LABELS.items():
            self.senders.heading(
                key,
                text=heading_label(title, active=key == column, descending=self._sender_descending),
            )
        self._render_senders()

    def show(self, rows: Sequence[dict[str, object]]) -> None:
        """Store ``rows`` and refresh the panel for the selected sender."""
        self._all_rows = list(rows)
        senders = sorted(
            {str(row.get("remetente", "") or "") for row in self._all_rows if row.get("remetente")}
        )
        self.sender_box.configure(values=[_ALL, *senders])
        if self.sender_var.get() not in [*senders, _ALL]:
            self.sender_var.set(_ALL)
        self._recompute()

    def _recompute(self) -> None:
        sender = self.sender_var.get()
        self.scope_label.configure(text="geral" if sender == _ALL else f"só {sender}")
        rows = self._all_rows if sender == _ALL else filter_rows(self._all_rows, sender=sender)
        self._render(photo_stats(rows))

    def _render(self, stats: PhotoStats) -> None:
        for key, variable in self._metrics.items():
            variable.set(_format_metric(stats, key))

        self._sender_rows = list(stats.senders)
        self._sender_total = stats.total or 1
        self._render_senders()

        self.heatmap.set_data(stats.per_weekday_hour, row_labels=WEEKDAY_LABELS)
        self.charts["per_day"].set_data(stats.per_day)
        self.charts["per_month"].set_data(stats.per_month)
        self.charts["per_hour"].set_data(
            [(f"{hour:02d}", count) for hour, count in enumerate(stats.per_hour)]
        )
        self.charts["per_weekday"].set_data(
            list(zip(WEEKDAY_LABELS, stats.per_weekday, strict=True))
        )
        self.charts["points_by_sender"].set_data(
            [(detail.sender, detail.points) for detail in stats.senders]
        )
        self.charts["caption_words"].set_data(stats.caption_words)
        self.charts["extensions"].set_data(stats.extensions)

        self.top_days.configure(height=max(3, len(stats.top_days)))
        self.top_days.delete(*self.top_days.get_children())
        for day, count in stats.top_days:
            self.top_days.insert("", "end", values=(day, count))


def _format_metric(stats: PhotoStats, key: str) -> str:
    if key == "total":
        return str(stats.total)
    if key == "with_file":
        return str(stats.with_file)
    if key == "pending":
        return str(stats.pending)
    if key == "total_points":
        return str(stats.total_points)
    if key == "avg_points":
        return "—" if not stats.total else f"{stats.avg_points:.1f}"
    if key == "exercise":
        if not stats.total:
            return "—"
        return f"{stats.exercise} ({stats.exercise / stats.total:.0%})"
    if key == "auto_points":
        return str(stats.auto_points)
    if key == "without_points":
        if not stats.total:
            return "—"
        return f"{stats.without_points} ({stats.without_points / stats.total:.0%})"
    if key == "participants":
        return str(len(stats.participants))
    if key == "period":
        if stats.first_date is None:
            return "—"
        return f"{stats.first_date} → {stats.last_date}"
    if key == "active_days":
        return str(stats.active_days)
    if key == "avg_per_day":
        return f"{stats.avg_per_active_day:.1f}"
    if key == "median_per_day":
        return f"{stats.median_per_active_day:.1f}"
    if key == "gap_hours":
        return "—" if stats.avg_gap_hours is None else f"{stats.avg_gap_hours:.1f} h"
    if key == "gap_median":
        return "—" if stats.median_gap_hours is None else f"{stats.median_gap_hours:.1f} h"
    if key == "streak":
        return f"{stats.longest_streak_days} dia(s)"
    if key == "peak_hour":
        return "—" if stats.peak_hour is None else f"{stats.peak_hour:02d}h"
    if key == "peak_weekday":
        return "—" if stats.peak_weekday is None else WEEKDAY_LABELS[stats.peak_weekday]
    if key == "peak_month":
        return stats.peak_month or "—"
    if key == "with_caption":
        if not stats.total:
            return "—"
        return f"{stats.with_caption} ({stats.with_caption / stats.total:.0%})"
    if key == "top3":
        return f"{stats.top3_share:.0%}"
    if key == "most_active":
        return (
            "—" if stats.most_active is None else f"{stats.most_active[0]} ({stats.most_active[1]})"
        )
    if key == "least_active":
        return (
            "—"
            if stats.least_active is None
            else f"{stats.least_active[0]} ({stats.least_active[1]})"
        )
    return "—"
