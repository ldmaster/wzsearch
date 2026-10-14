from typing import Any

from wzsearch.analytics import (
    audit_rows,
    caption_words,
    filter_rows,
    photo_stats,
    points_of,
    score_audit,
    score_reason,
    score_situation,
    sender_details,
    situation_label,
)

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


def test_rows_without_a_score_count_as_one_point() -> None:
    stats = photo_stats(ROWS)
    assert stats.total_points == 4
    assert stats.avg_points == 1.0
    assert stats.exercise == 0
    assert stats.auto_points == 0


def test_points_metrics_and_per_sender() -> None:
    rows: list[dict[str, Any]] = [
        {"remetente": "Ana", "data": "2024-03-01", "pontos": 2, "pontos_origem": "auto"},
        {"remetente": "Ana", "data": "2024-03-02", "pontos": 3, "pontos_origem": "manual"},
        {"remetente": "Bruno", "data": "2024-03-03", "pontos": "1", "pontos_origem": ""},
    ]
    stats = photo_stats(rows)
    assert stats.total_points == 6
    assert stats.avg_points == 2.0
    assert stats.exercise == 2
    assert stats.auto_points == 1

    details = {detail.sender: detail for detail in stats.senders}
    assert details["Ana"].points == 5
    assert details["Ana"].exercise == 2
    assert details["Bruno"].points == 1
    assert details["Bruno"].exercise == 0


def test_points_of_tolerates_missing_values() -> None:
    assert points_of({}) == 1
    assert points_of({"pontos": None}) == 1
    assert points_of({"pontos": ""}) == 1
    assert points_of({"pontos": "0"}) == 1
    assert points_of({"pontos": 4}) == 4


def test_filter_rows_only_auto() -> None:
    rows: list[dict[str, Any]] = [
        {"pontos_origem": "auto"},
        {"pontos_origem": "manual"},
        {},
    ]
    assert len(filter_rows(rows, only_auto=True)) == 1
    assert len(filter_rows(rows)) == 3


def test_stats_survive_an_odd_value_in_the_base() -> None:
    """Uma data fora do ISO não pode derrubar a aba de análises."""
    rows: list[dict[str, Any]] = [
        {"remetente": "Ana", "data": "2024-03-01", "hora": "10:00:00", "pontos": "abc"},
        {"remetente": "Ana", "data": "12/03/2024", "hora": "10:00:00"},
        {"remetente": "Ana", "data": "10:00:00", "hora": "2024-03-01"},
        {"remetente": "Ana", "data": "", "hora": "", "timestamp": "2024-03-01"},
    ]
    stats = photo_stats(rows)
    assert stats.total == 4
    assert stats.longest_streak_days == 1  # só o dia válido conta
    assert sum(stats.per_weekday) == 1
    assert sum(sum(row) for row in stats.per_weekday_hour) == 1


SITUACOES: list[dict[str, Any]] = [
    {"id": 1, "remetente": "Ana", "pontos": 2, "pontos_origem": "auto", "legenda": "treino"},
    {"id": 2, "remetente": "Ana", "pontos": 2, "pontos_origem": "confirmado", "legenda": "treino"},
    {"id": 3, "remetente": "Bruno", "pontos": 1, "pontos_origem": "manual", "legenda": "bolo"},
    {"id": 4, "remetente": "Bruno", "pontos": 4, "pontos_origem": "manual", "legenda": "corrida"},
    {"id": 5, "remetente": "Bruno", "pontos": 1, "pontos_origem": "", "legenda": "café"},
]


def test_score_situation_and_labels() -> None:
    assert [score_situation(row) for row in SITUACOES] == [
        "auto",
        "confirmado",
        "manual",
        "manual",
        "sem_sugestao",
    ]
    assert situation_label(SITUACOES[0]) == "Sugestão a revisar"
    assert situation_label(SITUACOES[1]) == "Sugestão confirmada"
    assert situation_label(SITUACOES[2]) == "Ajustada por você"
    assert situation_label(SITUACOES[3]) == "4 pontos (fora do padrão)"
    assert situation_label(SITUACOES[4]) == "1 ponto (sem sugestão)"


def test_audit_rows_by_situation_and_sender() -> None:
    assert [row["id"] for row in audit_rows(SITUACOES, "auto")] == [1]
    assert [row["id"] for row in audit_rows(SITUACOES, "revisadas")] == [2, 3, 4]
    assert [row["id"] for row in audit_rows(SITUACOES, "alto")] == [4]
    assert [row["id"] for row in audit_rows(SITUACOES, "todas")] == [1, 2, 3, 4, 5]
    assert [row["id"] for row in audit_rows(SITUACOES, "todas", "Bruno")] == [3, 4, 5]
    assert audit_rows(SITUACOES, "auto", "Bruno") == []


def test_score_audit_totals() -> None:
    totals = score_audit(SITUACOES)
    assert totals.photos == 5
    assert totals.points == 10
    assert totals.suggestions == 1
    assert totals.confirmed == 1
    assert totals.manual == 2
    assert totals.over == 1
    assert score_audit([]).photos == 0


def test_score_reason_explains_each_situation() -> None:
    assert "treino" in score_reason(SITUACOES[0])
    assert "treino" in score_reason(SITUACOES[1])
    assert score_reason(SITUACOES[2]) == "ajustada por você"
    assert score_reason(SITUACOES[4]) == ""
