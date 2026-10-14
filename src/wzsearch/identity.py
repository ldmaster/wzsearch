"""The stable identity of a photo record, used to survive re-imports.

A record is one media message. Re-exporting the same conversation must land on
the *same* identity, otherwise the base fills up with duplicates — and that is
exactly what the export file name and the message position do not guarantee:
WhatsApp renames a new export to ``… (1).zip`` and a chat that grew shifts every
position.

So the identity is built from the message itself — the chat, the moment, who
sent it, the media file and the caption — plus an **occurrence** counter, which
tells apart messages that are identical in all of those (two ``<Mídia oculta>``
photos from the same person in the same second, for instance). WhatsApp exports
in chronological order, so a chat that grows only appends: the first occurrence
of a signature stays the first, and re-importing finds it in the same place.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

#: Separator that cannot appear in a name or a caption, so the parts cannot blur.
_SEPARATOR = "\x1f"

#: ``Conversa (1)`` — the suffix WhatsApp adds to a repeated export file, which
#: can come either at the end of a name or right before its extension
#: (``Conversa do WhatsApp com Ana (1).zip``).
_COPY_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def strip_copy_suffix(name: str) -> str:
    """Drop the ``(1)``/``(2)`` a repeated WhatsApp export puts in the file name.

    The file is what gets renamed, not the chat, so this is applied where a name
    comes *from a file* (the export name and the evidence column). Both the name
    and the name-before-the-extension are handled.
    """
    stem, dot, extension = name.rpartition(".")
    if dot and extension and " " not in extension:
        return f"{_COPY_SUFFIX_RE.sub('', stem)}{dot}{extension}"
    return _COPY_SUFFIX_RE.sub("", name)


def _normalise(value: object) -> str:
    """Fold a field for comparison: spacing collapsed, case ignored."""
    return " ".join(str(value or "").split()).casefold()


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key, "") or "")


def signature_of(row: Mapping[str, object]) -> str:
    """Return the stable signature of a record (a hash of what the message is).

    The chat is normalised here, and not only where it is read from the file:
    the value stored by an older version may still carry the ``(1)`` a repeated
    export put in the file name, and the same message has to land on the same
    signature on both sides.
    """
    parts = (
        strip_copy_suffix(_text(row, "chat")),
        _text(row, "timestamp"),
        _text(row, "remetente"),
        _text(row, "foto_arquivo"),
        _text(row, "legenda"),
    )
    return hashlib.sha1(_SEPARATOR.join(_normalise(part) for part in parts).encode()).hexdigest()


def identity_key(signature: str, ocurrence: int) -> str:
    """Return the string that identifies a record: signature plus occurrence."""
    return f"{signature}-{ocurrence}"
