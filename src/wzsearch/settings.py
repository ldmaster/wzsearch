"""User preferences kept in a small JSON file next to the database."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import data_dir

_SETTINGS_NAME = "settings.json"


def settings_file() -> Path:
    """Path of the settings file."""
    return data_dir() / _SETTINGS_NAME


@dataclass(slots=True)
class Settings:
    """Everything the app remembers between runs."""

    check_updates: bool = True
    skipped_version: str = ""
    highest_seen_version: str = ""
    last_check: float = 0.0


def load() -> Settings:
    """Read the settings (defaults when the file is missing or broken)."""
    try:
        raw = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(raw, dict):
        return Settings()
    return Settings(
        check_updates=bool(raw.get("check_updates", True)),
        skipped_version=str(raw.get("skipped_version", "") or ""),
        highest_seen_version=str(raw.get("highest_seen_version", "") or ""),
        last_check=float(raw.get("last_check", 0.0) or 0.0),
    )


def save(settings: Settings) -> None:
    """Write the settings atomically (a crash never leaves a half file)."""
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    temporary = settings_file().with_name(f"{_SETTINGS_NAME}.tmp")
    temporary.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(settings_file())


def checked_recently(settings: Settings, *, hours: float = 24.0, now: float | None = None) -> bool:
    """Whether a check happened recently enough to skip a new one."""
    moment = time.time() if now is None else now
    return (moment - settings.last_check) < hours * 3600
