"""Locale-aware handling of the export's date and time formatting.

WhatsApp exports differ by platform and locale: ``DD/MM`` vs ``M/D`` dates,
12-hour vs 24-hour clocks, and bracketed (iOS) vs dash-separated (Android)
lines. wzsearch *detects* the shape from the data instead of assuming one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

_DATE_SEP = r"[/.\-]"
_AMPM = r"(?:\s?[APap]\.?[Mm]\.?)?"

#: Android / Desktop line, e.g. ``12/03/2024 14:22 - Fulano: texto``.
DASH_LINE = re.compile(
    rf"^(?P<date>\d{{1,4}}{_DATE_SEP}\d{{1,2}}{_DATE_SEP}\d{{1,4}}),?\s+"
    rf"(?P<time>\d{{1,2}}:\d{{2}}(?::\d{{2}})?{_AMPM})\s+[-–—]\s?"
    r"(?P<rest>.*)$"
)

#: iOS line, e.g. ``[12/03/2024, 14:22:31] Fulano: texto``.
BRACKET_LINE = re.compile(
    rf"^\[(?P<date>\d{{1,4}}{_DATE_SEP}\d{{1,2}}{_DATE_SEP}\d{{1,4}}),?\s+"
    rf"(?P<time>\d{{1,2}}:\d{{2}}(?::\d{{2}})?{_AMPM})\]\s?"
    r"(?P<rest>.*)$"
)

_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
    r"(?:\s?(?P<ampm>[APap])\.?[Mm]\.?)?$"
)


@dataclass(frozen=True, slots=True)
class DateProfile:
    """Resolved interpretation of the export's date and time strings."""

    day_first: bool
    four_digit_year: bool
    hour12: bool
    bracket: bool


def _date_parts(date_str: str) -> tuple[int, int, int]:
    first, second, third = (int(part) for part in re.split(_DATE_SEP, date_str))
    return first, second, third


def detect_profile(lines: Sequence[str]) -> tuple[DateProfile, re.Pattern[str]] | None:
    """Detect the date/time shape and line pattern used by ``lines``.

    Returns ``(profile, line_pattern)``, or ``None`` when no timestamped line
    is found. Detection is data-driven: a day value above 12 in the first
    position proves ``DD/MM``, in the second proves ``MM/DD``; the Brazilian
    ``DD/MM`` order is the fallback when every value is ambiguous.
    """
    dash = [match for line in lines if (match := DASH_LINE.match(line)) is not None]
    bracket = [match for line in lines if (match := BRACKET_LINE.match(line)) is not None]
    if not dash and not bracket:
        return None

    bracket_mode = len(bracket) > len(dash)
    matches = bracket if bracket_mode else dash
    pattern = BRACKET_LINE if bracket_mode else DASH_LINE

    parts = [_date_parts(match.group("date")) for match in matches]
    big_first = any(first > 12 for first, _, _ in parts)
    big_second = any(second > 12 for _, second, _ in parts)
    day_first = not (big_second and not big_first)
    four_digit_year = any(year > 99 for _, _, year in parts)
    hour12 = any(re.search(r"[APap]\.?[Mm]", match.group("time")) is not None for match in matches)
    profile = DateProfile(day_first, four_digit_year, hour12, bracket_mode)
    return profile, pattern


def parse_datetime(date_str: str, time_str: str, profile: DateProfile) -> datetime:
    """Build a :class:`datetime` from the raw date and time strings.

    Raises:
        ValueError: when the time string cannot be parsed.
    """
    first, second, third = _date_parts(date_str)
    day, month = (first, second) if profile.day_first else (second, first)
    year = third if third > 99 else 2000 + third

    match = _TIME_RE.match(time_str.strip())
    if match is None:
        raise ValueError(f"unrecognised time: {time_str!r}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second_value = int(match.group("second") or 0)
    ampm = match.group("ampm")
    if ampm is not None:
        hour = hour % 12 + (12 if ampm.lower() == "p" else 0)
    return datetime(year, month, day, hour, minute, second_value)
