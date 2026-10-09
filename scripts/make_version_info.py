"""Generate the Windows version resource from the package version.

The executable carries its version in the PE resource, and that is where the
updater reads it from after downloading a release (the resource sits inside the
region covered by the Authenticode signature, so it cannot be forged).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from wzsearch import __version__  # noqa: E402

TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'ldmaster'),
          StringStruct(
            'FileDescription',
            'wzsearch - fotos e estatisticas de um export do WhatsApp',
          ),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'wzsearch'),
          StringStruct('LegalCopyright', 'MIT License'),
          StringStruct('OriginalFilename', 'wzsearch.exe'),
          StringStruct('ProductName', 'wzsearch'),
          StringStruct('ProductVersion', '{version}'),
        ],
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def main() -> int:
    """Write ``packaging/version_info.txt`` and report where it went."""
    numbers = [int(part) for part in __version__.split(".")[:4] if part.isdigit()]
    numbers += [0] * (4 - len(numbers))
    target = ROOT / "packaging" / "version_info.txt"
    target.write_text(
        TEMPLATE.format(version=__version__, numbers=tuple(numbers)), encoding="utf-8"
    )
    print(f"{target} — versão {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
