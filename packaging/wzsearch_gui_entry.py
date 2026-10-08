"""Entry point used by PyInstaller to build the windowed GUI binary."""

from __future__ import annotations

import sys

from wzsearch.gui import main

if __name__ == "__main__":
    sys.exit(main())
