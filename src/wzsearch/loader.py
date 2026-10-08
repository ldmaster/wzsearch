"""Read chat text and media listing from ``.txt`` and ``.zip`` exports."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .media import normalize_media_name

_CHAT_NAME_RE = re.compile(
    r"^(?:Conversa do WhatsApp|WhatsApp Chat)\s+(?:com|with|con)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
_CHAT_TXT_RE = re.compile(r"(?:^|/)_?chat\.txt$", re.IGNORECASE)
#: Invisible bidi/format marks that WhatsApp occasionally injects into names.
_INVISIBLE = re.compile(r"[\u200e\u200f\u202a-\u202e\ufeff]")


@dataclass(frozen=True, slots=True)
class ChatExport:
    """A loaded export: normalised text, chat name, and media file names."""

    source: Path
    chat_name: str
    text: str
    media_names: frozenset[str]


def _decode(data: bytes) -> str:
    """Decode export bytes, honouring BOMs and falling back to cp1252."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _INVISIBLE.sub("", text)


def _chat_name_from_stem(stem: str) -> str:
    match = _CHAT_NAME_RE.match(stem)
    if match is not None:
        return match.group("name").strip()
    return stem


def _chat_name(path: Path, member: str) -> str:
    """Prefer the descriptive inner file name, falling back to the zip name."""
    inner_stem = Path(member).stem
    if _CHAT_NAME_RE.match(inner_stem) is not None:
        return _chat_name_from_stem(inner_stem)
    return _chat_name_from_stem(path.stem)


def load_export(path: Path) -> ChatExport:
    """Load ``path`` (``.txt`` or ``.zip``) into a :class:`ChatExport`.

    Raises:
        FileNotFoundError: when ``path`` does not exist.
        ValueError: when the extension is unsupported or the zip has no chat
            text file.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = _clean(_decode(path.read_bytes()))
        return ChatExport(path, _chat_name_from_stem(path.stem), text, frozenset())
    if suffix == ".zip":
        return _load_zip(path)
    raise ValueError(f"unsupported input (expected .txt or .zip): {path}")


def _load_zip(path: Path) -> ChatExport:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        member = _find_chat_member(names)
        if member is None:
            raise ValueError(f"no chat text file found inside {path.name}")
        text = _clean(_decode(archive.read(member)))
        media = frozenset(
            normalize_media_name(Path(name).name)
            for name in names
            if name != member and not name.endswith("/")
        )
    return ChatExport(path, _chat_name(path, member), text, media)


def _find_chat_member(names: list[str]) -> str | None:
    for name in names:
        if _CHAT_TXT_RE.search(name):
            return name
    for name in names:
        if name.lower().endswith(".txt"):
            return name
    return None
