from typing import Any

from wzsearch.analytics import caption_words, filter_rows, photo_stats, sender_details

ROWS: list[dict[str, Any]] = [
    {
        "remetente": "Ana",
        "data": "2024-03-01",
        "hora": "09:00:00",
        "timestamp": "2024-03-01 09:00:00",
        "foto_existe": "sim",
        "midia_pendente": "nao",
    },
    {
        "remetente": "Ana",
        "data": "2024-03-01",
        "hora": "10:00:00",
        "timestamp": "2024-03-01 10:00:00",
        "foto_existe": "sim",
        "midia_pendente": "nao",
    },
    {
        "remetente": "Bruno",
        "data": "2024-03-02",
        "hora": "23:30:00",
        "timestamp": "2024-03-02 23:30:00",
        "foto_existe": "nao",
        "midia_pendente": "sim",
    },
    {
        "remetente": "Ana",
        "data": "2024-04-10",
        "hora": "08:00:00",
        "timestamp": "2024-04-10 08:00:00",
        "foto_existe": "sim",
        "midia_pendente": "nao",
    },
]


def test_totals_and_files() -> None:
    stats = photo_stats(ROWS)
    assert stats.total == 4
    assert stats.with_file == 3
    assert stats.pending == 1


def test_participants_ranking() -> None:
    stats = photo_stats(ROWS)
    assert stats.participants == (("Ana", 3), ("Bruno", 1))
    assert stats.most_active == ("Ana", 3)
    assert stats.least_active == ("Bruno", 1)


def test_per_day_month_hour_weekday() -> None:
    stats = photo_stats(ROWS)
    assert stats.per_day == (("2024-03-01", 2), ("2024-03-02", 1), ("2024-04-10", 1))
    assert stats.per_month == (("2024-03", 3), ("2024-04", 1))
    assert stats.per_hour[9] == 1 and stats.per_hour[10] == 1 and stats.per_hour[23] == 1
    assert sum(stats.per_weekday) == 4


def test_top_days_and_range() -> None:
    stats = photo_stats(ROWS)
    assert stats.top_days[0] == ("2024-03-01", 2)
    assert stats.first_date == "2024-03-01"
    assert stats.last_date == "2024-04-10"


def test_active_days_and_averages() -> None:
    stats = photo_stats(ROWS)
    assert stats.active_days == 3
    assert stats.avg_per_active_day == 4 / 3
    assert stats.median_per_active_day == 1.0
    assert stats.longest_streak_days == 2  # 01 e 02/03


def test_average_gap() -> None:
    stats = photo_stats(ROWS)
    assert stats.avg_gap_hours is not None
    assert stats.avg_gap_hours > 0


def test_empty_rows() -> None:
    stats = photo_stats([])
    assert stats.total == 0
    assert stats.most_active is None
    assert stats.avg_gap_hours is None
    assert stats.longest_streak_days == 0


def test_filter_rows() -> None:
    assert len(filter_rows(ROWS, sender="Ana")) == 3
    assert len(filter_rows(ROWS, only_pending=True)) == 1
    assert len(filter_rows(ROWS, start="2024-03-02")) == 2
    assert len(filter_rows(ROWS, end="2024-03-02")) == 3
    assert len(filter_rows(ROWS, sender="Bruno", only_pending=True)) == 1


def test_peak_concentration_and_grid() -> None:
    stats = photo_stats(ROWS)
    assert stats.peak_weekday == 4  # 2024-03-01 é sexta
    assert stats.peak_month == "2024-03"
    assert stats.top3_share == 1.0
    assert stats.with_caption == 0
    assert stats.extensions == (("(sem arquivo)", 4),)
    assert len(stats.per_weekday_hour) == 7
    assert sum(sum(row) for row in stats.per_weekday_hour) == 4


def test_sender_details() -> None:
    details = {detail.sender: detail for detail in sender_details(ROWS)}
    assert details["Ana"].count == 3
    assert details["Ana"].active_days == 2
    assert details["Ana"].first == "2024-03-01"
    assert details["Ana"].last == "2024-04-10"
    assert details["Bruno"].pending == 1
    assert details["Bruno"].with_file == 0


def test_caption_words() -> None:
    rows = [
        {"legenda": "olha o bolo de chocolate"},
        {"legenda": "o bolo ficou bom kkk"},
        {"legenda": "chocolate"},
    ]
    words = dict(caption_words(rows))
    assert words["bolo"] == 2
    assert words["chocolate"] == 2
    assert "o" not in words
    assert "kkk" not in words
