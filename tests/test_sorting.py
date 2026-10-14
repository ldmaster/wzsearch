from typing import Any

from wzsearch.sorting import ASCENDING, DESCENDING, heading_label, sort_items


def test_sort_items_ascending_and_descending() -> None:
    items: list[dict[str, Any]] = [{"n": 2}, {"n": 1}, {"n": 3}]
    assert [item["n"] for item in sort_items(items, lambda item: item["n"])] == [1, 2, 3]
    assert [item["n"] for item in sort_items(items, lambda item: item["n"], descending=True)] == [
        3,
        2,
        1,
    ]


def test_sort_items_keeps_the_empty_values_at_the_end() -> None:
    items: list[dict[str, Any]] = [{"n": ""}, {"n": 2}, {"n": None}, {"n": 1}]
    assert [item["n"] for item in sort_items(items, lambda item: item["n"])] == [1, 2, "", None]
    assert [item["n"] for item in sort_items(items, lambda item: item["n"], descending=True)] == [
        2,
        1,
        "",
        None,
    ]


def test_sort_items_is_stable_and_handles_nothing_to_sort() -> None:
    assert sort_items([], lambda item: item) == []
    items: list[dict[str, Any]] = [{"n": 1, "tag": "a"}, {"n": 1, "tag": "b"}]
    assert [item["tag"] for item in sort_items(items, lambda item: item["n"])] == ["a", "b"]


def test_heading_label_marks_the_sorted_column() -> None:
    assert heading_label("Pontos", active=False, descending=False) == "Pontos"
    assert heading_label("Pontos", active=True, descending=False) == f"Pontos{ASCENDING}"
    assert heading_label("Pontos", active=True, descending=True) == f"Pontos{DESCENDING}"
