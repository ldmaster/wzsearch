"""Where wzsearch keeps its data (database, avatars, log).

The default is the operating system's per-user data directory, which is hidden
from casual browsing (``~/Library/Application Support`` on macOS, ``%APPDATA%``
on Windows). Override it with the ``WZSEARCH_HOME`` environment variable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ENV_HOME = "WZSEARCH_HOME"


def data_dir() -> Path:
    """Directory holding user data, overridable with ``WZSEARCH_HOME``."""
    override = os.environ.get(_ENV_HOME)
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "wzsearch"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "wzsearch"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "wzsearch"
