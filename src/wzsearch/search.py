"""Turn user-provided search terms into compiled matchers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchTerm:
    """A compiled search: a human label plus the regex that finds it."""

    label: str
    pattern: re.Pattern[str]


def build_terms(
    terms: Sequence[str], regexes: Sequence[str], *, ignore_case: bool = False
) -> list[SearchTerm]:
    """Compile literal ``terms`` and ``regexes`` into :class:`SearchTerm`s.

    Literal terms are escaped, so they match exactly. Regexes are validated
    up front.

    Raises:
        ValueError: when one of ``regexes`` is not a valid regular expression.
    """
    flags = re.IGNORECASE if ignore_case else 0
    compiled: list[SearchTerm] = []
    for literal in terms:
        compiled.append(SearchTerm(literal, re.compile(re.escape(literal), flags)))
    for expression in regexes:
        try:
            pattern = re.compile(expression, flags)
        except re.error as exc:
            raise ValueError(f"invalid regex {expression!r}: {exc}") from exc
        compiled.append(SearchTerm(f"re:{expression}", pattern))
    return compiled
