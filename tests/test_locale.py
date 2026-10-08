from datetime import datetime
from pathlib import Path

from wzsearch.locale import BRACKET_LINE, DASH_LINE, detect_profile, parse_datetime

FIXTURES = Path(__file__).parent / "fixtures"


def _lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").split("\n")


def test_detect_android_pt() -> None:
    detected = detect_profile(_lines("chat_android_pt.txt"))
    assert detected is not None
    profile, pattern = detected
    assert profile.day_first is True
    assert profile.hour12 is False
    assert profile.bracket is False
    assert pattern is DASH_LINE


def test_detect_ios_en() -> None:
    detected = detect_profile(_lines("chat_ios_en.txt"))
    assert detected is not None
    profile, pattern = detected
    assert profile.day_first is False
    assert profile.hour12 is True
    assert profile.bracket is True
    assert pattern is BRACKET_LINE


def test_detect_returns_none_without_timestamps() -> None:
    assert detect_profile(["sem data", "nada aqui"]) is None


def test_parse_datetime_24h_day_first() -> None:
    detected = detect_profile(_lines("chat_android_pt.txt"))
    assert detected is not None
    profile, _ = detected
    assert parse_datetime("12/03/2024", "14:22", profile) == datetime(2024, 3, 12, 14, 22)


def test_parse_datetime_12h_month_first() -> None:
    detected = detect_profile(_lines("chat_ios_en.txt"))
    assert detected is not None
    profile, _ = detected
    assert parse_datetime("3/15/24", "2:22:31 PM", profile) == datetime(2024, 3, 15, 14, 22, 31)


def test_parse_datetime_midnight_am() -> None:
    detected = detect_profile(_lines("chat_ios_en.txt"))
    assert detected is not None
    profile, _ = detected
    assert parse_datetime("3/15/24", "12:05:00 AM", profile).hour == 0
