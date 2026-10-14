"""Column sorting helpers shared by the tables.

Clicking a heading sorts the table by that column; clicking it again flips the
direction. Rows without a value (the empty cells the tables draw as ``—``) stay
at the end of the list, so a table sorted by a sparse column is still readable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

#: Heading markers for the sorted column.
ASCENDING = " ▲"
DESCENDING = " ▼"

#: What a column can be sorted by: a number or text, always the same per column.
Sortable = int | float | str


def sort_items[T](
    items: Sequence[T], value_of: Callable[[T], Sortable | None], *, descending: bool = False
) -> list[T]:
    """Sort ``items`` by ``value_of``, keeping the empty ones at the end."""
    filled: list[tuple[Sortable, T]] = []
    empty: list[T] = []
    for item in items:
        value = value_of(item)
        if value is None or value == "":
            empty.append(item)
        else:
            filled.append((value, item))
    filled.sort(key=lambda pair: pair[0], reverse=descending)
    return [item for _value, item in filled] + empty


def heading_label(label: str, *, active: bool, descending: bool) -> str:
    """Heading text, marked with the sort arrow when it is the sorted column."""
    if not active:
        return label
    return f"{label}{DESCENDING if descending else ASCENDING}"
