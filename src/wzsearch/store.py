"""SQLite store for photo records, with optional embedded media.

The database is a single file; records are added incrementally (a stable key
avoids duplicates), can be marked as *not included* in the analytics, soft
deleted into a trash and restored, or purged for good. Each record also carries
a score (see :mod:`wzsearch.score`), adjustable one point at a time.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import identity, score
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
    pontos INTEGER NOT NULL DEFAULT 1,
    pontos_origem TEXT NOT NULL DEFAULT '',
    pontos_motivo TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    deleted_at TEXT,
    media BLOB,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_data ON photos(data);
"""

#: Columns added after the first release, with the definition used to add them
#: to a database created before they existed (``CREATE TABLE IF NOT EXISTS``
#: never touches an existing table).
_ADDED_COLUMNS = (
    ("pontos", "INTEGER NOT NULL DEFAULT 1"),
    ("pontos_origem", "TEXT NOT NULL DEFAULT ''"),
    ("pontos_motivo", "TEXT NOT NULL DEFAULT ''"),
    ("assinatura", "TEXT NOT NULL DEFAULT ''"),
    ("ocorrencia", "INTEGER NOT NULL DEFAULT 1"),
)

#: Identity index: two records with the same signature are the same message, and
#: the occurrence tells apart the ones that look identical (see wzsearch.identity).
_IDENTITY_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_identidade
    ON photos (assinatura, ocorrencia) WHERE assinatura <> '';
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
_LIST_COLUMNS = (
    "id",
    *_FIELDS,
    "incluir",
    "pontos",
    "pontos_origem",
    "pontos_motivo",
    "status",
    "deleted_at",
    "created_at",
)


def default_db_path() -> Path:
    """Default database location (hidden per-user data directory)."""
    return data_dir() / "wzsearch.db"


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key, "") or "")


@dataclass(frozen=True, slots=True)
class AddResult:
    """What an import did: how many records are new, how many got their file."""

    added: int
    enriched: int


class Store:
    """Photo records persisted in a SQLite file (use ``":memory:"`` for tests)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection
        self._connect()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add the columns a database created by an older version is missing."""
        existing = {str(record[1]) for record in self._conn.execute("PRAGMA table_info(photos)")}
        for column, definition in _ADDED_COLUMNS:
            if column not in existing:
                self._conn.execute(
                    f"ALTER TABLE photos ADD COLUMN {column} {definition}"  # noqa: S608 - fixed DDL
                )
        self._backfill_identities()
        self._conn.executescript(_IDENTITY_INDEX)

    def _backfill_identities(self) -> None:
        """Give the records that came from an older version their identity.

        The occurrence counts the records with the same signature in date order,
        which is the order they were imported in.
        """
        pending = self._conn.execute(
            "SELECT id, chat, timestamp, remetente, foto_arquivo, legenda FROM photos "
            "WHERE assinatura = '' ORDER BY timestamp, id"
        ).fetchall()
        if not pending:
            return
        counters: dict[str, int] = {}
        for record in pending:
            row = dict(record)
            signature = identity.signature_of(row)
            counters[signature] = counters.get(signature, 0) + 1
            self._conn.execute(
                "UPDATE photos SET assinatura = ?, ocorrencia = ? WHERE id = ?",
                (signature, counters[signature], row["id"]),
            )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def reopen(self) -> None:
        """Reconnect to the same file (after a restore replaced it)."""
        self._conn.close()
        self._connect()

    def clear_all(self) -> int:
        """Delete every record and return how many were removed."""
        cursor = self._conn.execute("DELETE FROM photos")
        self._conn.commit()
        return cursor.rowcount

    def add_rows(
        self, rows: Iterable[Mapping[str, object]], *, media: Mapping[int, bytes] | None = None
    ) -> AddResult:
        """Insert new records, complete the ones that arrived before their file.

        The identity of a record is its signature plus the occurrence (see
        :mod:`wzsearch.identity`), so re-importing the same conversation — even
        exported again under another file name — does not duplicate anything.

        A record already stored without media gets the file as soon as an import
        brings it (``foto_existe``/``midia_pendente``/``foto_evidencia`` are
        updated); what was decided about the score is never touched, so a manual
        adjustment survives any re-import.

        ``media`` is keyed by the position of the row in ``rows``.
        """
        added = 0
        enriched = 0
        now = datetime.now().isoformat(timespec="seconds")
        columns = ", ".join(
            ("key", *_FIELDS, "pontos", "pontos_origem", "created_at", "assinatura", "ocorrencia")
        )
        placeholders = ", ".join("?" * (len(_FIELDS) + 6))
        counters: dict[str, int] = {}
        for position, row in enumerate(rows):
            signature = _text(row, "assinatura") or identity.signature_of(row)
            if row.get("ocorrencia"):
                occurrence = int(str(row["ocorrencia"]))
                counters[signature] = max(counters.get(signature, 0), occurrence)
            else:
                occurrence = counters.get(signature, 0) + 1
                counters[signature] = occurrence
            data = media.get(position) if media else None

            known = self._find_identity(signature, occurrence)
            if known is not None:
                if data is not None and self._attach_media(int(known["id"]), row, data):
                    enriched += 1
                continue

            points, origin = score.score_for(row)
            values: tuple[Any, ...] = (
                identity.identity_key(signature, occurrence),
                *(_text(row, field) for field in _FIELDS),
                points,
                origin,
                now,
                signature,
                occurrence,
            )
            cursor = self._conn.execute(
                f"INSERT OR IGNORE INTO photos ({columns}) VALUES ({placeholders})", values
            )
            if not cursor.rowcount:
                continue
            added += 1
            if data is not None:
                self._conn.execute(
                    "UPDATE photos SET media = ? WHERE id = ?", (data, cursor.lastrowid)
                )
        self._conn.commit()
        return AddResult(added=added, enriched=enriched)

    def _find_identity(self, signature: str, occurrence: int) -> sqlite3.Row | None:
        """The record with this identity, if it is already stored."""
        known: sqlite3.Row | None = self._conn.execute(
            "SELECT id, media FROM photos WHERE assinatura = ? AND ocorrencia = ?",
            (signature, occurrence),
        ).fetchone()
        return known

    def _attach_media(self, row_id: int, row: Mapping[str, object], data: bytes) -> bool:
        """Store the file of a record that was waiting for it; say if it changed."""
        known = self._conn.execute("SELECT media FROM photos WHERE id = ?", (row_id,)).fetchone()
        if known is None or known[0] is not None:
            return False
        self._conn.execute(
            "UPDATE photos SET media = ?, foto_existe = ?, midia_pendente = ?, "
            "foto_evidencia = ? WHERE id = ?",
            (data, "sim", "nao", _text(row, "foto_evidencia"), row_id),
        )
        return True

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

    def set_points(
        self,
        ids: Sequence[int],
        points: int,
        *,
        origem: str = score.ORIGEM_MANUAL,
        motivo: str | None = None,
    ) -> int:
        """Set the score of records, never below :data:`wzsearch.score.PONTOS_MIN`.

        ``motivo`` (when given) is stored as the reason of the adjustment —
        ``None`` leaves whatever was written before.
        """
        value = max(int(points), score.PONTOS_MIN)
        updated = 0
        for row_id in ids:
            if motivo is None:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos = ?, pontos_origem = ? WHERE id = ?",
                    (value, origem, row_id),
                )
            else:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos = ?, pontos_origem = ?, pontos_motivo = ? "
                    "WHERE id = ?",
                    (value, origem, motivo, row_id),
                )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def adjust_points(
        self,
        ids: Sequence[int],
        delta: int,
        *,
        origem: str = score.ORIGEM_MANUAL,
        motivo: str | None = None,
    ) -> int:
        """Add ``delta`` to the score of records, keeping the minimum of one."""
        updated = 0
        for row_id in ids:
            if motivo is None:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos = max(pontos + ?, ?), pontos_origem = ? WHERE id = ?",
                    (int(delta), score.PONTOS_MIN, origem, row_id),
                )
            else:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos = max(pontos + ?, ?), pontos_origem = ?, "
                    "pontos_motivo = ? WHERE id = ?",
                    (int(delta), score.PONTOS_MIN, origem, motivo, row_id),
                )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def rescore_auto(self, suggested: Mapping[int, int]) -> int:
        """Apply the caption suggestions, leaving decided scores untouched."""
        updated = 0
        for row_id, points in suggested.items():
            value = max(int(points), score.PONTOS_MIN)
            origin = score.ORIGEM_AUTO if value > score.PONTOS_MIN else score.ORIGEM_VAZIA
            cursor = self._conn.execute(
                "UPDATE photos SET pontos = ?, pontos_origem = ? "
                "WHERE id = ? AND coalesce(pontos_origem, '') NOT IN (?, ?) AND pontos <> ?",
                (value, origin, row_id, *score.ORIGEM_DECIDIDA, value),
            )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def confirm_points(self, ids: Sequence[int], *, motivo: str | None = None) -> int:
        """Mark suggestions as reviewed, keeping the value they already have."""
        updated = 0
        for row_id in ids:
            if motivo is None:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos_origem = ? WHERE id = ?",
                    (score.ORIGEM_CONFIRMADO, row_id),
                )
            else:
                cursor = self._conn.execute(
                    "UPDATE photos SET pontos_origem = ?, pontos_motivo = ? WHERE id = ?",
                    (score.ORIGEM_CONFIRMADO, motivo, row_id),
                )
            updated += cursor.rowcount
        self._conn.commit()
        return updated

    def rescore_unevaluated(self) -> int:
        """Score the records no caption has looked at yet.

        Called when the app opens: a base imported before the score existed (or
        by the CLI) gets its exercise photos marked without anyone clicking
        anything. Records adjusted by hand are never touched, and the pass is
        cheap to repeat — a caption that matches nothing simply stays at one
        point.
        """
        rows = self.rows(include_deleted=True)
        pending = [row for row in rows if not str(row.get("pontos_origem") or "")]
        if not pending:
            return 0
        return self.rescore_auto(score.suggestions(pending))

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
