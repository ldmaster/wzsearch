"""Write occurrences or photo listings to CSV, incrementally if requested."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

from . import identity

#: Column order of the occurrences CSV (search mode).
COLUMNS = (
    "occurrence_id",
    "termo",
    "texto_casado",
    "remetente",
    "data",
    "hora",
    "timestamp",
    "chat",
    "message_id",
    "contexto",
    "tem_midia",
    "arquivo_midia",
    "tem_foto",
    "foto_evidencia",
    "foto_existe",
    "telefone_remetente",
    "numero_no_texto",
)

#: Column order of the photo listing (``--photos`` mode). No ``numero_no_texto``.
PHOTO_COLUMNS = (
    "foto_id",
    "remetente",
    "telefone_remetente",
    "data",
    "hora",
    "timestamp",
    "chat",
    "message_id",
    "contexto",
    "legenda",
    "contexto_provavel",
    "foto_arquivo",
    "foto_evidencia",
    "foto_existe",
    "midia_pendente",
)


class CsvSchemaError(ValueError):
    """Raised when an existing CSV has a different column layout."""


#: Columns used when exporting stored rows (the database view) to CSV.
DB_COLUMNS = (
    "id",
    "remetente",
    "remetente_original",
    "telefone_remetente",
    "data",
    "hora",
    "timestamp",
    "chat",
    "message_id",
    "legenda",
    "contexto",
    "contexto_provavel",
    "foto_arquivo",
    "foto_existe",
    "midia_pendente",
    "status",
    "incluir",
    "pontos",
    "pontos_origem",
    "pontos_motivo",
)


def _identity_value(column: str, value: str) -> str:
    """The value a *line already written* is recognised by.

    ``foto_evidencia`` carries the name of the export file, and WhatsApp renames
    every new export (``… (1).zip``) — comparing it as it is would make an
    already recorded line look new. The suffix is dropped here so a re-export
    matches what is already in the file.
    """
    if column != "foto_evidencia":
        return value
    source, separator, arquivo = value.partition("::")
    if not separator:
        return value
    return f"{identity.strip_copy_suffix(source)}::{arquivo}"


def row_key(row: Mapping[str, object], columns: Sequence[str], id_column: str) -> tuple[str, ...]:
    """Return the stable identity of a row: every column except the sequential id."""
    return tuple(
        _identity_value(column, str(row.get(column, "")))
        for column in columns
        if column != id_column
    )


def read_existing_keys(
    path: Path, columns: Sequence[str], id_column: str
) -> tuple[set[tuple[str, ...]], int]:
    """Return the keys already present in ``path`` and its highest id.

    Raises:
        CsvSchemaError: when the file has a different column layout.
    """
    keys: set[tuple[str, ...]] = set()
    max_id = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return keys, max_id
        if reader.fieldnames != list(columns):
            raise CsvSchemaError(
                f"{path.name} tem colunas diferentes das esperadas; use --overwrite ou outro --csv"
            )
        for row in reader:
            keys.add(row_key(row, columns, id_column))
            raw = (row.get(id_column) or "").strip()
            if raw.isdigit():
                max_id = max(max_id, int(raw))
    return keys, max_id


def write_rows(
    rows: Iterable[Mapping[str, object]],
    handle: TextIO,
    columns: Sequence[str],
    *,
    write_header: bool = True,
) -> int:
    """Write ``rows`` as CSV to ``handle`` and return the number written.

    Keys the rows carry beyond ``columns`` (the identity of a record, for one)
    are ignored: the file format stays exactly what it always was.
    """
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    if write_header:
        writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    return count
