"""Analytics tab: posting-frequency metrics and simple bar charts."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from tkinter import ttk

from .analytics import WEEKDAY_LABELS, PhotoStats, photo_stats
from .chart import BarChart


class AnalyticsView(ttk.Frame):
    """Scrollable panel with summary metrics, rankings and bar charts."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=8)
        canvas = tk.Canvas(self, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        self._metrics: dict[str, tk.StringVar] = {}
        self.charts: dict[str, BarChart] = {}
        self._build()

    def _build(self) -> None:
        metrics_box = ttk.LabelFrame(self._inner, text="Resumo", padding=8)
        metrics_box.pack(fill="x", pady=(0, 10))
        for key in _METRIC_ORDER:
            row = ttk.Frame(metrics_box)
            row.pack(fill="x")
            ttk.Label(row, text=_METRIC_LABELS[key], width=28).pack(side="left")
            variable = tk.StringVar(value="—")
            ttk.Label(row, textvariable=variable).pack(side="left")
            self._metrics[key] = variable

        ranking = ttk.LabelFrame(self._inner, text="Quem postou mais fotos", padding=8)
        ranking.pack(fill="x", pady=(0, 10))
        self.ranking = ttk.Treeview(
            ranking, columns=("remetente", "fotos"), show="headings", height=6
        )
        self.ranking.heading("remetente", text="Remetente")
        self.ranking.heading("fotos", text="Fotos")
        self.ranking.column("remetente", width=220, anchor="w")
        self.ranking.column("fotos", width=70, anchor="e")
        self.ranking.pack(fill="x")

        for key, title in _CHART_TITLES.items():
            block = ttk.LabelFrame(self._inner, text=title, padding=6)
            block.pack(fill="x", pady=(0, 10))
            chart = BarChart(block, height=150)
            chart.pack(fill="x")
            self.charts[key] = chart

        top = ttk.LabelFrame(self._inner, text="Dias mais movimentados", padding=8)
        top.pack(fill="x")
        self.top_days = ttk.Treeview(top, columns=("data", "fotos"), show="headings", height=6)
        self.top_days.heading("data", text="Data")
        self.top_days.heading("fotos", text="Fotos")
        self.top_days.column("data", width=220, anchor="w")
        self.top_days.column("fotos", width=70, anchor="e")
        self.top_days.pack(fill="x")

    def show(self, rows: Sequence[dict[str, object]]) -> None:
        """Recompute and display the metrics for ``rows``."""
        stats = photo_stats(rows)
        for key, variable in self._metrics.items():
            variable.set(_format_metric(stats, key))

        self.ranking.delete(*self.ranking.get_children())
        total = stats.total or 1
        for sender, count in stats.participants:
            self.ranking.insert("", "end", values=(sender, f"{count} ({count / total:.0%})"))

        self.charts["per_day"].set_data(stats.per_day)
        self.charts["per_month"].set_data(stats.per_month)
        self.charts["per_hour"].set_data(
            [(f"{hour:02d}", count) for hour, count in enumerate(stats.per_hour)]
        )
        self.charts["per_weekday"].set_data(
            list(zip(WEEKDAY_LABELS, stats.per_weekday, strict=True))
        )

        self.top_days.delete(*self.top_days.get_children())
        for day, count in stats.top_days:
            self.top_days.insert("", "end", values=(day, count))


_METRIC_LABELS = {
    "total": "Total de fotos",
    "with_file": "Com arquivo no export",
    "pending": "Mídias pendentes",
    "participants": "Participantes",
    "period": "Período",
    "active_days": "Dias com fotos",
    "avg_per_day": "Média por dia ativo",
    "median_per_day": "Mediana por dia ativo",
    "gap_hours": "Intervalo médio entre fotos",
    "streak": "Maior sequência (dias seguidos)",
    "most_active": "Mais ativa",
    "least_active": "Menos ativa",
}

_METRIC_ORDER = tuple(_METRIC_LABELS)

_CHART_TITLES = {
    "per_day": "Fotos por dia",
    "per_month": "Fotos por mês",
    "per_hour": "Fotos por hora do dia",
    "per_weekday": "Fotos por dia da semana",
}


def _format_metric(stats: PhotoStats, key: str) -> str:
    if key == "total":
        return str(stats.total)
    if key == "with_file":
        return str(stats.with_file)
    if key == "pending":
        return str(stats.pending)
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
    if key == "streak":
        return f"{stats.longest_streak_days} dia(s)"
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
