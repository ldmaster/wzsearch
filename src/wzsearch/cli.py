"""Command-line interface for wzsearch."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from itertools import count
from pathlib import Path
from typing import TextIO

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


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``wzsearch`` command."""
    parser = argparse.ArgumentParser(
        prog="wzsearch",
        description="Search an exported WhatsApp conversation and emit an occurrences CSV.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="one or more .txt/.zip exports")
    parser.add_argument("--term", action="append", default=[], help="literal keyword (repeatable)")
    parser.add_argument("--regex", action="append", default=[], help="regex (repeatable)")
    parser.add_argument("--csv", type=Path, default=None, help="output CSV (default: stdout)")
    parser.add_argument("--eu", default=None, help="your display name, to identify your side")
    parser.add_argument("--chat", default=None, help="override the chat name for every input")
    parser.add_argument("-i", "--case-insensitive", action="store_true", help="ignore case")
    parser.add_argument("--include-system", action="store_true", help="also scan system notices")
    parser.add_argument(
        "--photos",
        action="store_true",
        help="list only messages that contain a photo (no --term needed)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="rewrite the CSV from scratch instead of appending only new rows",
    )
    return parser


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - _CONTEXT_WINDOW)
    right = min(len(text), end + _CONTEXT_WINDOW)
    chunk = text[left:right].replace("\n", " ")
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{chunk}{suffix}"


def _row(
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


def _iter_rows(
    parsed: Sequence[tuple[str, str, list[Message]]],
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
                    yield _row(
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
    parsed: Sequence[tuple[str, str, list[Message]]],
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


def _print_summary(
    rows: Sequence[dict[str, object]], *, handle: TextIO, label: str, skipped: int = 0
) -> None:
    per_sender = Counter(str(row["remetente"]) or "(sem remetente)" for row in rows)
    print(f"{len(rows)} {label}", file=handle)
    if skipped:
        print(f"  ({skipped} já existiam, ignoradas)", file=handle)
    if rows and "midia_pendente" in rows[0]:
        pending = sum(1 for row in rows if row["midia_pendente"] == "sim")
        print(f"  ({pending} mídia(s) pendente(s))", file=handle)
    if rows and "termo" in rows[0]:
        per_term = Counter(str(row["termo"]) for row in rows)
        for term, amount in per_term.items():
            print(f"  termo {term!r}: {amount}", file=handle)
    for sender, amount in per_sender.most_common():
        print(f"  {sender}: {amount}", file=handle)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``wzsearch`` command and return its exit code."""
    args = build_parser().parse_args(argv)
    if not args.photos and not args.term and not args.regex:
        print("error: informe ao menos um --term/--regex (ou use --photos)", file=sys.stderr)
        return 2

    terms: list[SearchTerm] = []
    if not args.photos:
        try:
            terms = build_terms(args.term, args.regex, ignore_case=args.case_insensitive)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    parsed: list[tuple[str, str, list[Message]]] = []
    for path in args.inputs:
        try:
            export = load_export(path)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        chat_name = args.chat or export.chat_name
        messages = parse_chat(
            export.text,
            chat_name=chat_name,
            media_names=export.media_names,
            eu=args.eu,
        )
        parsed.append((chat_name, export.source.name, messages))

    columns: Sequence[str]
    if args.photos:
        rows = list(_iter_photo_rows(parsed, include_system=args.include_system))
        columns = PHOTO_COLUMNS
        id_column = "foto_id"
        label = "foto(s)"
    else:
        rows = list(_iter_rows(parsed, terms, include_system=args.include_system))
        columns = COLUMNS
        id_column = "occurrence_id"
        label = "ocorrência(s)"

    skipped = 0
    if args.csv is None:
        write_rows(rows, sys.stdout, columns)
    elif args.csv.exists() and not args.overwrite:
        try:
            keys, max_id = read_existing_keys(args.csv, columns, id_column)
        except CsvSchemaError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        rows, skipped = _deduplicate(rows, columns, id_column, keys, max_id)
        with args.csv.open("a", encoding="utf-8", newline="") as handle:
            write_rows(rows, handle, columns, write_header=False)
    else:
        with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
            write_rows(rows, handle, columns)

    _print_summary(rows, handle=sys.stderr, label=label, skipped=skipped)
    return 0
