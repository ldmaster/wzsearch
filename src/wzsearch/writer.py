"""Write occurrences or photo listings to CSV, incrementally if requested."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

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
)


def row_key(row: Mapping[str, object], columns: Sequence[str], id_column: str) -> tuple[str, ...]:
    """Return the stable identity of a row: every column except the sequential id."""
    return tuple(str(row.get(column, "")) for column in columns if column != id_column)


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
    """Write ``rows`` as CSV to ``handle`` and return the number written."""
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
    if write_header:
        writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    return count
