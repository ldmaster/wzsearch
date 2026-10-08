"""Per-sender photo mapping set by the user in the GUI.

The WhatsApp export carries no profile pictures, so the app lets the user pick
a real photo per contact; the mapping sender -> image path is stored locally.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import data_dir


def config_dir() -> Path:
    """Directory holding user settings (the app data directory)."""
    return data_dir()


def avatars_file() -> Path:
    """Path of the JSON file mapping senders to their photo."""
    return config_dir() / "avatars.json"


def load_avatars() -> dict[str, str]:
    """Read the saved sender -> image-path mapping (empty when absent)."""
    try:
        data = json.loads(avatars_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def save_avatars(mapping: dict[str, str]) -> None:
    """Persist the mapping to disk."""
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    avatars_file().write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")


def set_avatar(sender: str, image: Path) -> dict[str, str]:
    """Associate ``image`` with ``sender`` and save."""
    mapping = load_avatars()
    mapping[sender] = str(image)
    save_avatars(mapping)
    return mapping


def remove_avatar(sender: str) -> dict[str, str]:
    """Drop ``sender``'s photo and save."""
    mapping = load_avatars()
    mapping.pop(sender, None)
    save_avatars(mapping)
    return mapping


def avatar_path(sender: str) -> Path | None:
    """Return the user-chosen photo for ``sender``, if any."""
    value = load_avatars().get(sender)
    return Path(value) if value else None
