"""Frequency analytics over generated photo rows.

Pure functions with no GUI dependency, so they are easy to test. Rows are the
dicts produced by :mod:`wzsearch.pipeline` (photo listing).
"""

from __future__ import annotations

import contextlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median

Row = Mapping[str, object]

WEEKDAY_LABELS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


@dataclass(frozen=True, slots=True)
class PhotoStats:
    """Aggregate metrics for a set of photo rows."""

    total: int
    with_file: int
    pending: int
    participants: tuple[tuple[str, int], ...]
    per_day: tuple[tuple[str, int], ...]
    per_month: tuple[tuple[str, int], ...]
    per_hour: tuple[int, ...]
    per_weekday: tuple[int, ...]
    top_days: tuple[tuple[str, int], ...]
    first_date: str | None
    last_date: str | None
    active_days: int
    avg_per_active_day: float
    median_per_active_day: float
    avg_gap_hours: float | None
    longest_streak_days: int

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


def filter_rows(
    rows: Sequence[Row],
    *,
    sender: str | None = None,
    start: str | None = None,
    end: str | None = None,
    only_pending: bool = False,
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
        result.append(row)
    return result


def _longest_streak(days: Sequence[date]) -> int:
    best = streak = 0
    previous: date | None = None
    for day in days:
        streak = streak + 1 if previous is not None and (day - previous).days == 1 else 1
        best = max(best, streak)
        previous = day
    return best


def photo_stats(rows: Sequence[Row]) -> PhotoStats:
    """Compute the frequency metrics shown in the analytics tab."""
    senders = Counter(_text(row, "remetente") or "(sem remetente)" for row in rows)
    days = Counter(_text(row, "data") for row in rows if _text(row, "data"))
    months = Counter(_text(row, "data")[:7] for row in rows if _text(row, "data"))
    hours = [0] * 24
    weekdays = [0] * 7
    stamps: list[datetime] = []
    for row in rows:
        hour_text = _text(row, "hora")
        if hour_text[:2].isdigit():
            hours[int(hour_text[:2]) % 24] += 1
        day_text = _text(row, "data")
        if day_text:
            with contextlib.suppress(ValueError):
                weekdays[date.fromisoformat(day_text).weekday()] += 1
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

    ordered_days = sorted(days)
    active = len(ordered_days)
    total = len(rows)
    avg_per_day = total / active if active else 0.0
    median_per_day = float(median(days.values())) if days else 0.0
    avg_gap_hours = sum(gaps) / len(gaps) / 3600 if gaps else None
    streak = _longest_streak([date.fromisoformat(day) for day in ordered_days])

    return PhotoStats(
        total=total,
        with_file=sum(1 for row in rows if _text(row, "foto_existe") == "sim"),
        pending=sum(1 for row in rows if is_pending(row)),
        participants=tuple(senders.most_common()),
        per_day=tuple(sorted(days.items())),
        per_month=tuple(sorted(months.items())),
        per_hour=tuple(hours),
        per_weekday=tuple(weekdays),
        top_days=tuple(days.most_common(10)),
        first_date=ordered_days[0] if ordered_days else None,
        last_date=ordered_days[-1] if ordered_days else None,
        active_days=active,
        avg_per_active_day=avg_per_day,
        median_per_active_day=median_per_day,
        avg_gap_hours=avg_gap_hours,
        longest_streak_days=streak,
    )
