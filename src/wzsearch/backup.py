"""Backup and restore of everything wzsearch stores locally.

A backup is a single zip with the database (photos included), the sender name
mapping and the avatars. Restoring overwrites those files in the data dir.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from pathlib import Path

from .avatars import avatars_file
from .senders import names_file
from .store import default_db_path


def data_files() -> list[Path]:
    """The files that make up "all data"."""
    return [default_db_path(), names_file(), avatars_file()]


def backup_zip(destination: Path) -> Path:
    """Write a zip with every existing data file and return its path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in data_files():
            if path.exists():
                archive.write(path, path.name)
    return destination


def restore_zip(source: Path) -> list[str]:
    """Replace the local data with the contents of ``source``.

    Returns the names restored.

    Raises:
        ValueError: when the zip has none of the expected files.
    """
    targets = {path.name: path for path in data_files()}
    restored: list[str] = []
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as exc:
        raise ValueError("o arquivo não é um zip válido") from exc
    with archive:
        for name in archive.namelist():
            target = targets.get(Path(name).name)
            if target is None or name.endswith("/"):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            restored.append(target.name)
    if not restored:
        raise ValueError("o arquivo não parece um backup do wzsearch")
    return restored


def clear_all_data() -> Iterable[Path]:
    """Remove the settings files (the database is emptied by the store)."""
    removed: list[Path] = []
    for path in (names_file(), avatars_file()):
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed
