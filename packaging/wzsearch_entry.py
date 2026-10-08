"""Entry point used by PyInstaller to build standalone binaries."""

from __future__ import annotations

import sys

from wzsearch.cli import main

if __name__ == "__main__":
    sys.exit(main())
