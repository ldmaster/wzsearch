"""Command-line interface for wzsearch."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from .pipeline import GenerateResult, WzsearchError, generate_photos, generate_search


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


def _print_summary(result: GenerateResult, *, handle: TextIO) -> None:
    rows = result.rows
    per_sender = Counter(str(row["remetente"]) or "(sem remetente)" for row in rows)
    print(f"{len(rows)} {result.label}", file=handle)
    if result.skipped:
        print(f"  ({result.skipped} já existiam, ignoradas)", file=handle)
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

    try:
        if args.photos:
            result = generate_photos(
                args.inputs,
                args.csv,
                eu=args.eu,
                chat=args.chat,
                include_system=args.include_system,
                overwrite=args.overwrite,
            )
        else:
            result = generate_search(
                args.inputs,
                args.term,
                args.regex,
                args.csv,
                ignore_case=args.case_insensitive,
                eu=args.eu,
                chat=args.chat,
                include_system=args.include_system,
                overwrite=args.overwrite,
            )
    except WzsearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code

    _print_summary(result, handle=sys.stderr)
    return 0
