"""SQLite store for photo records, with optional embedded media.

The database is a single file; records are added incrementally (a stable key
avoids duplicates), can be marked as *not included* in the analytics, soft
deleted into a trash and restored, or purged for good.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import data_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    chat TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    remetente TEXT NOT NULL DEFAULT '',
    telefone_remetente TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '',
    hora TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT '',
    legenda TEXT NOT NULL DEFAULT '',
    contexto TEXT NOT NULL DEFAULT '',
    contexto_provavel TEXT NOT NULL DEFAULT '',
    foto_arquivo TEXT NOT NULL DEFAULT '',
    foto_evidencia TEXT NOT NULL DEFAULT '',
    foto_existe TEXT NOT NULL DEFAULT 'nao',
    midia_pendente TEXT NOT NULL DEFAULT 'sim',
    incluir INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    deleted_at TEXT,
    media BLOB,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_data ON photos(data);
"""

_FIELDS = (
    "chat",
    "source",
    "message_id",
    "remetente",
    "telefone_remetente",
    "data",
    "hora",
    "timestamp",
    "legenda",
    "contexto",
    "contexto_provavel",
    "foto_arquivo",
    "foto_evidencia",
    "foto_existe",
    "midia_pendente",
)

#: Columns loaded when listing records (never the ``media`` blob).
_LIST_COLUMNS = ("id", *_FIELDS, "incluir", "status", "deleted_at", "created_at")


def default_db_path() -> Path:
    """Default database location (hidden per-user data directory)."""
    return data_dir() / "wzsearch.db"


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key, "") or "")


def row_key(row: Mapping[str, object]) -> str:
    """Stable identity of a photo record, used to avoid duplicates."""
    evidencia = _text(row, "foto_evidencia")
    chat = _text(row, "chat") or _text(row, "source")
    message_id = _text(row, "message_id")
    arquivo = _text(row, "foto_arquivo")
    return f"{evidencia or chat}#{message_id}#{arquivo}"


class Store:
    """Photo records persisted in a SQLite file (use ``":memory:"`` for tests)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def add_rows(
        self, rows: Iterable[Mapping[str, object]], *, media: Mapping[str, bytes] | None = None
    ) -> int:
        """Insert new records (ignoring duplicates) and return how many were added."""
        added = 0
        now = datetime.now().isoformat(timespec="seconds")
        columns = ", ".join(("key", *_FIELDS, "created_at"))
        placeholders = ", ".join("?" * (len(_FIELDS) + 2))
        for row in rows:
            key = row_key(row)
            values: tuple[Any, ...] = (key, *(_text(row, field) for field in _FIELDS), now)
            cursor = self._conn.execute(
                f"INSERT OR IGNORE INTO photos ({columns}) VALUES ({placeholders})", values
            )
            if not cursor.rowcount:
                continue
            added += 1
            if media and key in media:
                self._conn.execute("UPDATE photos SET media = ? WHERE key = ?", (media[key], key))
        self._conn.commit()
        return added

    def rows(
        self, *, include_deleted: bool = False, only_included: bool = False
    ) -> list[dict[str, Any]]:
        """Return records ordered by date, as dictionaries."""
        clauses: list[str] = []
        if not include_deleted:
            clauses.append("status = 'active'")
        if only_included:
            clauses.append("incluir = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self._conn.execute(
            f"SELECT {', '.join(_LIST_COLUMNS)} FROM photos {where} "  # noqa: S608 - fixed columns
            "ORDER BY data, hora, id"
        )
        return [dict(record) for record in cursor.fetchall()]

    def connected_sources(self) -> set[str]:
        """Names of the export files already imported (for the header info)."""
        cursor = self._conn.execute("SELECT DISTINCT source FROM photos WHERE source <> ''")
        return {str(record[0]) for record in cursor.fetchall()}

    def set_included(self, ids: Sequence[int], included: bool) -> int:
        """Mark records as included/excluded from the analytics."""
        return self._update_many("incluir", 1 if included else 0, ids)

    def delete(self, ids: Sequence[int]) -> int:
        """Soft-delete records (move them to the trash)."""
        now = datetime.now().isoformat(timespec="seconds")
        updated = 0
        for row_id in ids:
            cursor = self._conn.execute(
                "UPDATE photos SET status = 'deleted', deleted_at = ? WHERE id = ?",
                (now, row_id),
            )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def restore(self, ids: Sequence[int]) -> int:
        """Restore soft-deleted records."""
        updated = 0
        for row_id in ids:
            cursor = self._conn.execute(
                "UPDATE photos SET status = 'active', deleted_at = NULL WHERE id = ?", (row_id,)
            )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def purge(self) -> int:
        """Permanently remove everything in the trash and return how many."""
        cursor = self._conn.execute("DELETE FROM photos WHERE status = 'deleted'")
        self._conn.commit()
        return cursor.rowcount

    def media(self, row_id: int) -> bytes | None:
        """Return the stored photo bytes, if the record has one."""
        cursor = self._conn.execute("SELECT media FROM photos WHERE id = ?", (row_id,))
        record = cursor.fetchone()
        return bytes(record[0]) if record is not None and record[0] is not None else None

    def counts(self) -> dict[str, int]:
        """Counts of active, deleted and not-included records."""
        active = self._count("status = 'active'")
        deleted = self._count("status = 'deleted'")
        excluded = self._count("status = 'active' AND incluir = 0")
        return {"active": active, "deleted": deleted, "excluded": excluded}

    def _count(self, where: str) -> int:
        cursor = self._conn.execute(f"SELECT COUNT(*) FROM photos WHERE {where}")  # noqa: S608
        return int(cursor.fetchone()[0])

    def _update_many(self, column: str, value: int, ids: Sequence[int]) -> int:
        updated = 0
        for row_id in ids:
            cursor = self._conn.execute(
                f"UPDATE photos SET {column} = ? WHERE id = ?",  # noqa: S608 - fixed column
                (value, row_id),
            )
            updated += cursor.rowcount
        self._conn.commit()
        return updated
