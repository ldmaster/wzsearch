"""Display names for ingested senders, set by the user.

WhatsApp exports often show a phone number instead of a saved name; the user can
map each number to a friendly name, stored locally and used across the app.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .paths import data_dir


def names_file() -> Path:
    """Path of the JSON file mapping raw sender -> display name."""
    return data_dir() / "senders.json"


def load_names() -> dict[str, str]:
    """Read the saved raw sender -> name mapping (empty when absent)."""
    try:
        data = json.loads(names_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def save_names(mapping: Mapping[str, str]) -> None:
    """Persist the mapping to disk."""
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    names_file().write_text(
        json.dumps(dict(mapping), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_name(sender: str, name: str) -> dict[str, str]:
    """Associate a display ``name`` with ``sender`` and save."""
    mapping = load_names()
    mapping[sender] = name
    save_names(mapping)
    return mapping


def remove_name(sender: str) -> dict[str, str]:
    """Drop ``sender``'s display name and save."""
    mapping = load_names()
    mapping.pop(sender, None)
    save_names(mapping)
    return mapping


def rename_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return copies of ``rows`` with ``remetente`` replaced by the user's name.

    The original label is kept in ``remetente_original`` so nothing is lost.
    """
    names = load_names()
    renamed: list[dict[str, Any]] = []
    for row in rows:
        original = str(row.get("remetente", "") or "")
        copy = dict(row)
        copy["remetente_original"] = original
        copy["remetente"] = names.get(original, original)
        renamed.append(copy)
    return renamed
