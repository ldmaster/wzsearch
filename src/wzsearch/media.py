"""Recognise and link media placeholders found in message bodies.

WhatsApp writes a placeholder where a photo, video or document was sent, and
the shape varies by platform and version:

- ``<anexo: foto.jpg>`` / ``<attached: foto.jpg>`` (tagged angle brackets)
- ``<IMG-20240101-WA0001.jpg>`` (bare filename between angle brackets, iOS)
- ``IMG-20240101-WA0001.jpg (arquivo anexado)`` (filename + label, Android)
- ``<Mídia oculta>`` / ``<Media omitted>`` (media not included in the export)

In a ``.zip`` export the real file sits next to the chat text; in a plain
``.txt`` export (or for omitted media) only the placeholder exists.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

from .models import MediaRef

#: Extensions counted as photos for the media-evidence columns.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif"})

#: WhatsApp names stickers ``STK-...``; they are images but not photos.
_STICKER_RE = re.compile(r"^stk[-_]", re.IGNORECASE)

#: Extensions recognised as attachments when they appear as a bare filename.
_MEDIA_EXT = (
    "jpg|jpeg|png|webp|heic|heif|gif|bmp|tiff|tif|"
    "mp4|mov|3gp|mkv|avi|webm|"
    "opus|m4a|mp3|ogg|wav|aac|amr|"
    "pdf|doc|docx|xls|xlsx|ppt|pptx|txt|vcf|zip|apk"
)

_ANGLED_TAGGED = re.compile(
    r"<(?P<tag>anexo|attached|adjunto|arquivo|file|attachment)\s*:\s*(?P<name>[^>\n]+)>",
    re.IGNORECASE,
)
_ANGLED_BARE = re.compile(rf"<(?P<name>[^<>\n]+?\.(?:{_MEDIA_EXT}))>", re.IGNORECASE)
_SUFFIXED = re.compile(
    rf"(?P<name>[^\s<>/\\]{{1,120}}?\.(?:{_MEDIA_EXT}))\s*"
    r"\([^)\n]*(?:arquivo|file|anexo|adjunto|attached|documento)[^)\n]*\)",
    re.IGNORECASE,
)
_OMITTED = re.compile(
    r"<(?P<label>[^>\n]*(?:ocult|omitid|omitted|hidden|n[ãa]o inclu|n[ãa]o encontrad)[^>\n]*)>",
    re.IGNORECASE,
)

_NAMED_PATTERNS = (_ANGLED_TAGGED, _ANGLED_BARE, _SUFFIXED)


def normalize_media_name(name: str) -> str:
    """Normalise a media filename for case- and encoding-insensitive matching."""
    return unicodedata.normalize("NFC", unquote(name)).strip().casefold()


def extract_media(text: str, *, media_names: frozenset[str] = frozenset()) -> MediaRef:
    """Return the :class:`MediaRef` for the first media placeholder in ``text``."""
    for pattern in _NAMED_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            name = match.group("name").strip()
            return MediaRef(
                filename=name,
                omitted=False,
                exists_in_export=normalize_media_name(name) in media_names,
            )
    if _OMITTED.search(text) is not None:
        return MediaRef(omitted=True)
    return MediaRef()


def strip_media_placeholders(text: str) -> str:
    """Remove media placeholders so they do not pollute number extraction."""
    for pattern in (*_NAMED_PATTERNS, _OMITTED):
        text = pattern.sub(" ", text)
    return text


def is_photo(media: MediaRef) -> bool:
    """Whether the media placeholder points at a photo (not a sticker)."""
    if media.filename is None:
        return False
    if _STICKER_RE.match(media.filename):
        return False
    return Path(media.filename).suffix.lower() in IMAGE_EXTENSIONS
