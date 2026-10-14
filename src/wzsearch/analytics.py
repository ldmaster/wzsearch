"""Frequency analytics over generated photo rows.

Pure functions with no GUI dependency, so they are easy to test. Rows are the
dicts produced by :mod:`wzsearch.pipeline` (photo listing), extended with the
score columns the store keeps.
"""

from __future__ import annotations

import contextlib
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median

from .score import (
    ORIGEM_AUTO,
    ORIGEM_CONFIRMADO,
    ORIGEM_MANUAL,
    PONTOS_EXERCICIO,
    PONTOS_MIN,
    match_reason,
)

Row = Mapping[str, object]

WEEKDAY_LABELS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")

_WORD_RE = re.compile(r"[a-záàâãéêíóôõúüç]{3,}")
_STOPWORDS = frozenset(
    {
        "a",
        "as",
        "o",
        "os",
        "de",
        "da",
        "das",
        "do",
        "dos",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "um",
        "uma",
        "uns",
        "umas",
        "e",
        "que",
        "para",
        "pra",
        "por",
        "com",
        "sem",
        "se",
        "ja",
        "já",
        "nao",
        "não",
        "sim",
        "eh",
        "é",
        "foi",
        "ser",
        "sao",
        "são",
        "esta",
        "está",
        "estou",
        "muito",
        "mais",
        "menos",
        "tambem",
        "também",
        "so",
        "só",
        "aqui",
        "ali",
        "la",
        "lá",
        "eu",
        "voce",
        "você",
        "ele",
        "ela",
        "voces",
        "vocês",
        "meu",
        "minha",
        "seu",
        "sua",
        "isso",
        "isto",
        "aquilo",
        "ai",
        "aí",
        "entao",
        "então",
        "mas",
        "ou",
        "como",
        "quando",
        "onde",
        "kkk",
        "kkkk",
        "kkkkk",
        "rs",
        "rsrs",
        "gente",
        "top",
        "essa",
        "esse",
        "este",
        "pelo",
        "pela",
    }
)


@dataclass(frozen=True, slots=True)
class SenderDetail:
    """Per-sender activity summary."""

    sender: str
    count: int
    with_file: int
    pending: int
    active_days: int
    first: str | None
    last: str | None
    points: int
    exercise: int


@dataclass(frozen=True, slots=True)
class PhotoStats:
    """Aggregate metrics for a set of photo rows."""

    total: int
    with_file: int
    pending: int
    total_points: int
    avg_points: float
    exercise: int
    auto_points: int
    participants: tuple[tuple[str, int], ...]
    per_day: tuple[tuple[str, int], ...]
    per_month: tuple[tuple[str, int], ...]
    per_hour: tuple[int, ...]
    per_weekday: tuple[int, ...]
    per_weekday_hour: tuple[tuple[int, ...], ...]
    top_days: tuple[tuple[str, int], ...]
    first_date: str | None
    last_date: str | None
    active_days: int
    avg_per_active_day: float
    median_per_active_day: float
    avg_gap_hours: float | None
    median_gap_hours: float | None
    longest_streak_days: int
    with_caption: int
    caption_words: tuple[tuple[str, int], ...]
    extensions: tuple[tuple[str, int], ...]
    senders: tuple[SenderDetail, ...]
    peak_hour: int | None
    peak_weekday: int | None
    peak_month: str | None
    top3_share: float

    @property
    def most_active(self) -> tuple[str, int] | None:
        """Sender with the most photos, if any."""
        return self.participants[0] if self.participants else None

    @property
    def least_active(self) -> tuple[str, int] | None:
        """Sender with the fewest photos, if any."""
        return self.participants[-1] if self.participants else None


def _text(row: Row, key: str) -> str:
    return str(row.get(key, "") or "")


def is_pending(row: Row) -> bool:
    """Whether the row's media file was not included in the export."""
    return _text(row, "midia_pendente") == "sim"


def points_of(row: Row) -> int:
    """Score of a record (missing or unreadable values count as the minimum)."""
    raw = row.get("pontos", PONTOS_MIN)
    try:
        return max(int(str(raw)), PONTOS_MIN)
    except (TypeError, ValueError):
        return PONTOS_MIN


def is_scored_as_exercise(row: Row) -> bool:
    """Whether the record scores as an exercise photo (two points or more)."""
    return points_of(row) >= PONTOS_EXERCICIO


def is_auto_scored(row: Row) -> bool:
    """Whether the score came from the caption instead of a manual adjustment."""
    return _text(row, "pontos_origem") == ORIGEM_AUTO


#: (key, label) of every situation the score audit can show, in menu order.
SITUATIONS: tuple[tuple[str, str], ...] = (
    ("auto", "Sugestões a revisar"),
    ("confirmado", "Sugestões confirmadas"),
    ("manual", "Ajustadas por você"),
    ("alto", "3+ pontos (fora do padrão)"),
    ("revisadas", "Já decididas (suas ou confirmadas)"),
    ("todas", "Todas as fotos"),
)


def score_situation(row: Row) -> str:
    """Which situation a record is in, as a key of :data:`SITUATIONS`."""
    origin = _text(row, "pontos_origem")
    if origin == ORIGEM_CONFIRMADO:
        return "confirmado"
    if origin == ORIGEM_MANUAL:
        return "manual"
    if origin == ORIGEM_AUTO:
        return "auto"
    return "sem_sugestao"


def situation_label(row: Row) -> str:
    """Human wording of :func:`score_situation` (what the audit table shows)."""
    points = points_of(row)
    if points > PONTOS_EXERCICIO:
        return f"{points} pontos (fora do padrão)"
    return {
        "auto": "Sugestão a revisar",
        "confirmado": "Sugestão confirmada",
        "manual": "Ajustada por você",
        "sem_sugestao": "1 ponto (sem sugestão)",
    }[score_situation(row)]


def score_reason(row: Row) -> str:
    """Why a record has the score it has (empty when nothing decided it)."""
    situation = score_situation(row)
    if situation in {"auto", "confirmado"}:
        return match_reason(row) or "sugerida pela legenda"
    if situation == "manual":
        return "ajustada por você"
    return ""


def matches_situation(row: Row, situation: str, sender: str | None = None) -> bool:
    """Whether a record belongs in the audit for the chosen situation and sender."""
    if sender is not None and _text(row, "remetente") != sender:
        return False
    if situation == "todas":
        return True
    if situation == "alto":
        return points_of(row) > PONTOS_EXERCICIO
    if situation == "revisadas":
        return score_situation(row) in {"manual", "confirmado"}
    return score_situation(row) == situation


def audit_rows(rows: Sequence[Row], situation: str, sender: str | None = None) -> list[Row]:
    """The rows the score audit shows for a situation (all of them by default)."""
    return [row for row in rows if matches_situation(row, situation, sender)]


@dataclass(frozen=True, slots=True)
class ScoreAudit:
    """Totals shown at the top of the score audit."""

    photos: int
    points: int
    suggestions: int
    confirmed: int
    manual: int
    over: int


def score_audit(rows: Sequence[Row]) -> ScoreAudit:
    """Count the records by situation, for the audit header."""
    return ScoreAudit(
        photos=len(rows),
        points=sum(points_of(row) for row in rows),
        suggestions=sum(1 for row in rows if score_situation(row) == "auto"),
        confirmed=sum(1 for row in rows if score_situation(row) == "confirmado"),
        manual=sum(1 for row in rows if score_situation(row) == "manual"),
        over=sum(1 for row in rows if points_of(row) > PONTOS_EXERCICIO),
    )


def filter_rows(
    rows: Sequence[Row],
    *,
    sender: str | None = None,
    start: str | None = None,
    end: str | None = None,
    only_pending: bool = False,
    only_auto: bool = False,
) -> list[Row]:
    """Return the rows matching the given filters (all optional)."""
    result: list[Row] = []
    for row in rows:
        if sender is not None and _text(row, "remetente") != sender:
            continue
        day = _text(row, "data")
        if start and day and day < start:
            continue
        if end and day and day > end:
            continue
        if only_pending and not is_pending(row):
            continue
        if only_auto and not is_auto_scored(row):
            continue
        result.append(row)
    return result


def caption_words(rows: Sequence[Row], *, limit: int = 15) -> tuple[tuple[str, int], ...]:
    """Most frequent meaningful words across the captions (``legenda``)."""
    counter: Counter[str] = Counter()
    for row in rows:
        for word in _WORD_RE.findall(_text(row, "legenda").lower()):
            if word not in _STOPWORDS:
                counter[word] += 1
    return tuple(counter.most_common(limit))


def sender_details(rows: Sequence[Row]) -> tuple[SenderDetail, ...]:
    """Per-sender summary, most active first."""
    grouped: dict[str, list[Row]] = {}
    for row in rows:
        grouped.setdefault(_text(row, "remetente") or "(sem remetente)", []).append(row)
    details: list[SenderDetail] = []
    for sender, group in grouped.items():
        days = {_text(row, "data") for row in group if _text(row, "data")}
        ordered = sorted(days)
        details.append(
            SenderDetail(
                sender=sender,
                count=len(group),
                with_file=sum(1 for row in group if _text(row, "foto_existe") == "sim"),
                pending=sum(1 for row in group if is_pending(row)),
                active_days=len(days),
                first=ordered[0] if ordered else None,
                last=ordered[-1] if ordered else None,
                points=sum(points_of(row) for row in group),
                exercise=sum(1 for row in group if is_scored_as_exercise(row)),
            )
        )
    details.sort(key=lambda item: item.count, reverse=True)
    return tuple(details)


def _longest_streak(days: Sequence[date]) -> int:
    best = streak = 0
    previous: date | None = None
    for day in days:
        streak = streak + 1 if previous is not None and (day - previous).days == 1 else 1
        best = max(best, streak)
        previous = day
    return best


def _peak(values: Sequence[int]) -> int | None:
    if not values or max(values) == 0:
        return None
    return max(range(len(values)), key=lambda index: values[index])


def photo_stats(rows: Sequence[Row]) -> PhotoStats:
    """Compute the frequency metrics shown in the analytics tab."""
    senders = Counter(_text(row, "remetente") or "(sem remetente)" for row in rows)
    days = Counter(_text(row, "data") for row in rows if _text(row, "data"))
    months = Counter(_text(row, "data")[:7] for row in rows if _text(row, "data"))
    extensions = Counter(
        Path(_text(row, "foto_arquivo")).suffix.lower() or "(sem arquivo)" for row in rows
    )
    hours = [0] * 24
    weekdays = [0] * 7
    grid = [[0] * 24 for _ in range(7)]
    stamps: list[datetime] = []
    with_caption = 0
    for row in rows:
        if _text(row, "legenda").strip():
            with_caption += 1
        hour_text = _text(row, "hora")
        hour = int(hour_text[:2]) % 24 if hour_text[:2].isdigit() else None
        if hour is not None:
            hours[hour] += 1
        day_text = _text(row, "data")
        weekday: int | None = None
        if day_text:
            with contextlib.suppress(ValueError):
                weekday = date.fromisoformat(day_text).weekday()
        if weekday is not None:
            weekdays[weekday] += 1
            if hour is not None:
                grid[weekday][hour] += 1
        stamp_text = _text(row, "timestamp")
        if stamp_text:
            with contextlib.suppress(ValueError):
                stamps.append(datetime.fromisoformat(stamp_text))

    gaps: list[float] = []
    stamps.sort()
    if len(stamps) >= 2:
        gaps = [
            (later - earlier).total_seconds()
            for earlier, later in zip(stamps, stamps[1:], strict=False)
        ]
    gap_hours = [gap / 3600 for gap in gaps]

    ordered_days = sorted(days)
    active = len(ordered_days)
    total = len(rows)
    top3 = sum(count for _, count in senders.most_common(3))
    total_points = sum(points_of(row) for row in rows)

    return PhotoStats(
        total=total,
        with_file=sum(1 for row in rows if _text(row, "foto_existe") == "sim"),
        pending=sum(1 for row in rows if is_pending(row)),
        total_points=total_points,
        avg_points=total_points / total if total else 0.0,
        exercise=sum(1 for row in rows if is_scored_as_exercise(row)),
        auto_points=sum(1 for row in rows if is_auto_scored(row)),
        participants=tuple(senders.most_common()),
        per_day=tuple(sorted(days.items())),
        per_month=tuple(sorted(months.items())),
        per_hour=tuple(hours),
        per_weekday=tuple(weekdays),
        per_weekday_hour=tuple(tuple(row) for row in grid),
        top_days=tuple(days.most_common(10)),
        first_date=ordered_days[0] if ordered_days else None,
        last_date=ordered_days[-1] if ordered_days else None,
        active_days=active,
        avg_per_active_day=total / active if active else 0.0,
        median_per_active_day=float(median(days.values())) if days else 0.0,
        avg_gap_hours=sum(gap_hours) / len(gap_hours) if gap_hours else None,
        median_gap_hours=median(gap_hours) if gap_hours else None,
        longest_streak_days=_longest_streak([date.fromisoformat(day) for day in ordered_days]),
        with_caption=with_caption,
        caption_words=caption_words(rows),
        extensions=tuple(extensions.most_common()),
        senders=sender_details(rows),
        peak_hour=_peak(hours),
        peak_weekday=_peak(weekdays),
        peak_month=months.most_common(1)[0][0] if months else None,
        top3_share=top3 / total if total else 0.0,
    )
