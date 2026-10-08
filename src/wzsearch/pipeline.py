"""Core generation pipeline shared by the CLI and the desktop GUI.

Both front-ends call :func:`generate_photos` / :func:`generate_search`; the
functions load the exports, build the rows, and write the CSV (incrementally
when the target already exists).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from .loader import load_export
from .media import is_photo, strip_media_placeholders
from .models import Message
from .numbers import extract_numbers, format_numbers, sender_phone
from .parser import parse_chat
from .search import SearchTerm, build_terms
from .writer import (
    COLUMNS,
    PHOTO_COLUMNS,
    CsvSchemaError,
    read_existing_keys,
    row_key,
    write_rows,
)

_CONTEXT_WINDOW = 40

#: ``(chat_name, source_name, messages)`` for one loaded export.
ParsedExport = tuple[str, str, list[Message]]


class WzsearchError(Exception):
    """A user-facing error, with the exit code the CLI should return."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """What a generation run produced."""

    output: Path | None
    label: str
    rows: Sequence[dict[str, object]]
    skipped: int = 0

    @property
    def added(self) -> int:
        """Number of rows written in this run."""
        return len(self.rows)


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - _CONTEXT_WINDOW)
    right = min(len(text), end + _CONTEXT_WINDOW)
    chunk = text[left:right].replace("\n", " ")
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{chunk}{suffix}"


def _occurrence_row(
    *,
    occurrence_id: int,
    term: SearchTerm,
    message: Message,
    chat_name: str,
    source_name: str,
    matched: str,
    start: int,
    end: int,
    numbers: str,
) -> dict[str, object]:
    timestamp = message.timestamp
    photo = is_photo(message.media)
    linked = photo and message.media.exists_in_export
    return {
        "occurrence_id": occurrence_id,
        "termo": term.label,
        "texto_casado": matched.replace("\n", " "),
        "remetente": message.sender or "",
        "data": timestamp.date().isoformat(),
        "hora": timestamp.time().isoformat(),
        "timestamp": timestamp.isoformat(sep=" "),
        "chat": chat_name,
        "message_id": message.message_id,
        "contexto": _snippet(message.text, start, end),
        "tem_midia": "sim" if message.media.present else "nao",
        "arquivo_midia": message.media.filename or "",
        "tem_foto": "sim" if photo else "nao",
        "foto_evidencia": f"{source_name}::{message.media.filename}" if linked else "",
        "foto_existe": "sim" if linked else "nao",
        "telefone_remetente": sender_phone(message.sender),
        "numero_no_texto": numbers,
    }


def _iter_occurrence_rows(
    parsed: Sequence[ParsedExport],
    terms: Sequence[SearchTerm],
    *,
    include_system: bool,
) -> Iterator[dict[str, object]]:
    counter = count(1)
    for chat_name, source_name, messages in parsed:
        for message in messages:
            if message.is_system and not include_system:
                continue
            numbers = format_numbers(extract_numbers(strip_media_placeholders(message.text)))
            for term in terms:
                for match in term.pattern.finditer(message.text):
                    yield _occurrence_row(
                        occurrence_id=next(counter),
                        term=term,
                        message=message,
                        chat_name=chat_name,
                        source_name=source_name,
                        matched=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        numbers=numbers,
                    )


def _next_sender_contexts(messages: Sequence[Message]) -> list[str]:
    """For each message, the text of the next message from the same sender.

    Only later messages (higher index) are considered, skipping other people's
    messages. Media placeholders are stripped, so a following photo yields its
    caption (or an empty string).
    """
    contexts = [""] * len(messages)
    next_by_sender: dict[str, str] = {}
    for index in range(len(messages) - 1, -1, -1):
        sender = messages[index].sender
        if sender is None:
            continue
        if sender in next_by_sender:
            contexts[index] = next_by_sender[sender]
        next_by_sender[sender] = strip_media_placeholders(messages[index].text).strip()
    return contexts


def _photo_row(
    *,
    photo_id: int,
    message: Message,
    chat_name: str,
    source_name: str,
    linked: bool,
    contexto_provavel: str,
) -> dict[str, object]:
    timestamp = message.timestamp
    return {
        "foto_id": photo_id,
        "remetente": message.sender or "",
        "telefone_remetente": sender_phone(message.sender),
        "data": timestamp.date().isoformat(),
        "hora": timestamp.time().isoformat(),
        "timestamp": timestamp.isoformat(sep=" "),
        "chat": chat_name,
        "message_id": message.message_id,
        "contexto": _snippet(message.text, 0, len(message.text)),
        "legenda": strip_media_placeholders(message.text).strip(),
        "contexto_provavel": contexto_provavel,
        "foto_arquivo": message.media.filename or "",
        "foto_evidencia": f"{source_name}::{message.media.filename}" if linked else "",
        "foto_existe": "sim" if linked else "nao",
        "midia_pendente": "sim" if not linked else "nao",
    }


def _iter_photo_rows(
    parsed: Sequence[ParsedExport],
    *,
    include_system: bool,
) -> Iterator[dict[str, object]]:
    counter = count(1)
    for chat_name, source_name, messages in parsed:
        contexts = _next_sender_contexts(messages)
        for index, message in enumerate(messages):
            if message.is_system and not include_system:
                continue
            if not (is_photo(message.media) or message.media.omitted):
                continue
            yield _photo_row(
                photo_id=next(counter),
                message=message,
                chat_name=chat_name,
                source_name=source_name,
                linked=message.media.exists_in_export,
                contexto_provavel=contexts[index],
            )


def _deduplicate(
    rows: Sequence[dict[str, object]],
    columns: Sequence[str],
    id_column: str,
    existing_keys: set[tuple[str, ...]],
    max_id: int,
) -> tuple[list[dict[str, object]], int]:
    """Keep only rows not already recorded, continuing the id sequence."""
    added: list[dict[str, object]] = []
    seen = set(existing_keys)
    next_id = max_id
    for row in rows:
        key = row_key(row, columns, id_column)
        if key in seen:
            continue
        seen.add(key)
        next_id += 1
        new_row = dict(row)
        new_row[id_column] = next_id
        added.append(new_row)
    return added, len(rows) - len(added)


def _load_all(inputs: Sequence[Path], *, eu: str | None, chat: str | None) -> list[ParsedExport]:
    parsed: list[ParsedExport] = []
    for path in inputs:
        try:
            export = load_export(path)
        except (OSError, ValueError) as exc:
            raise WzsearchError(str(exc)) from exc
        chat_name = chat or export.chat_name
        messages = parse_chat(
            export.text,
            chat_name=chat_name,
            media_names=export.media_names,
            eu=eu,
        )
        parsed.append((chat_name, export.source.name, messages))
    return parsed


def _write(
    rows: Sequence[dict[str, object]],
    columns: Sequence[str],
    id_column: str,
    csv_path: Path | None,
    *,
    overwrite: bool,
) -> tuple[list[dict[str, object]], int]:
    """Write ``rows`` to ``csv_path`` (or stdout when ``None``); return the new rows."""
    if csv_path is None:
        write_rows(rows, sys.stdout, columns)
        return list(rows), 0

    written: list[dict[str, object]] = list(rows)
    skipped = 0
    try:
        if csv_path.exists() and not overwrite:
            keys, max_id = read_existing_keys(csv_path, columns, id_column)
            written, skipped = _deduplicate(rows, columns, id_column, keys, max_id)
            with csv_path.open("a", encoding="utf-8", newline="") as handle:
                write_rows(written, handle, columns, write_header=False)
        else:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                write_rows(written, handle, columns)
    except CsvSchemaError as exc:
        raise WzsearchError(str(exc)) from exc
    except OSError as exc:
        raise WzsearchError(f"não foi possível gravar {csv_path}: {exc}") from exc
    return written, skipped


MODE_PHOTOS = "photos"
MODE_SEARCH = "search"

#: mode -> (columns, id column, human label)
_MODES: dict[str, tuple[Sequence[str], str, str]] = {
    MODE_PHOTOS: (PHOTO_COLUMNS, "foto_id", "foto(s)"),
    MODE_SEARCH: (COLUMNS, "occurrence_id", "ocorrência(s)"),
}


def columns_for(mode: str) -> Sequence[str]:
    """Column order for a mode (used by the GUI table)."""
    return _MODES[mode][0]


def _compile(
    terms: Sequence[str], regexes: Sequence[str], *, ignore_case: bool
) -> list[SearchTerm]:
    try:
        return build_terms(terms, regexes, ignore_case=ignore_case)
    except ValueError as exc:
        raise WzsearchError(str(exc), exit_code=2) from exc


def collect_photos(
    inputs: Sequence[Path],
    *,
    eu: str | None = None,
    chat: str | None = None,
    include_system: bool = False,
) -> list[dict[str, object]]:
    """Build the photo listing rows without writing anything."""
    parsed = _load_all(inputs, eu=eu, chat=chat)
    return list(_iter_photo_rows(parsed, include_system=include_system))


def collect_search(
    inputs: Sequence[Path],
    terms: Sequence[str],
    regexes: Sequence[str],
    *,
    ignore_case: bool = False,
    eu: str | None = None,
    chat: str | None = None,
    include_system: bool = False,
) -> list[dict[str, object]]:
    """Build the occurrences rows without writing anything."""
    compiled = _compile(terms, regexes, ignore_case=ignore_case)
    parsed = _load_all(inputs, eu=eu, chat=chat)
    return list(_iter_occurrence_rows(parsed, compiled, include_system=include_system))


def save_rows(
    rows: Sequence[dict[str, object]],
    mode: str,
    csv_path: Path | None,
    *,
    overwrite: bool = False,
) -> GenerateResult:
    """Write collected ``rows`` (incremental when the file exists)."""
    columns, id_column, label = _MODES[mode]
    written, skipped = _write(rows, columns, id_column, csv_path, overwrite=overwrite)
    return GenerateResult(csv_path, label, written, skipped)


def generate_photos(
    inputs: Sequence[Path],
    csv_path: Path | None,
    *,
    eu: str | None = None,
    chat: str | None = None,
    include_system: bool = False,
    overwrite: bool = False,
) -> GenerateResult:
    """Collect the photo listing and write it in one call (used by the CLI)."""
    rows = collect_photos(inputs, eu=eu, chat=chat, include_system=include_system)
    return save_rows(rows, MODE_PHOTOS, csv_path, overwrite=overwrite)


def generate_search(
    inputs: Sequence[Path],
    terms: Sequence[str],
    regexes: Sequence[str],
    csv_path: Path | None,
    *,
    ignore_case: bool = False,
    eu: str | None = None,
    chat: str | None = None,
    include_system: bool = False,
    overwrite: bool = False,
) -> GenerateResult:
    """Collect the occurrences and write them in one call (used by the CLI)."""
    rows = collect_search(
        inputs,
        terms,
        regexes,
        ignore_case=ignore_case,
        eu=eu,
        chat=chat,
        include_system=include_system,
    )
    return save_rows(rows, MODE_SEARCH, csv_path, overwrite=overwrite)
