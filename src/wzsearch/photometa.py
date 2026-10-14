"""What the file itself tells about a photo: name, size, dimensions and EXIF.

WhatsApp renames every media file to ``IMG-YYYYMMDD-WA####.jpg`` and strips the
original EXIF before it ever reaches the export, so the capture date, the camera
and the GPS are normally gone — in a real export measured here, none of the
photos kept any EXIF. What is always there is the file name (with the date
WhatsApp used) and the file itself, and comparing that date with the date of the
message is what the audit can check.

Pillow is optional: without it the name, the size and the notes still work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO

try:
    from PIL import ExifTags, Image

    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - only the GUI ships Pillow
    ExifTags = None
    Image = None
    PILLOW_AVAILABLE = False

#: ``IMG-20260921-WA0011.jpg`` — the name WhatsApp gives to every media file.
_NAME_RE = re.compile(r"^(?P<kind>[A-Za-z]{2,4})-(?P<date>\d{8})-WA(?P<seq>\d+)")

#: Media prefix -> what it is (only the ones worth showing).
_KINDS = {
    "IMG": "foto",
    "VID": "vídeo",
    "AUD": "áudio",
    "PTT": "áudio gravado",
    "DOC": "documento",
    "STK": "figurinha",
}


@dataclass(frozen=True, slots=True)
class PhotoFacts:
    """What the stored file says about one photo."""

    filename: str
    kind: str
    size_bytes: int
    file_date: str | None
    sequence: str | None
    width: int | None
    height: int | None
    orientation: str
    taken_at: str | None
    camera: str | None
    gps: bool
    notes: tuple[str, ...]


def _br_date(iso_day: str | None) -> str:
    """``2026-09-21`` -> ``21/09/2026`` (``—`` when there is no date)."""
    if not iso_day:
        return "—"
    try:
        return date.fromisoformat(iso_day).strftime("%d/%m/%Y")
    except ValueError:
        return iso_day


def _size_text(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, round(size_bytes / 1024))} KB"


def _orientation(width: int, height: int) -> str:
    if width == height:
        return "quadrada"
    return "retrato" if height > width else "paisagem"


def _image_facts(data: bytes) -> tuple[int | None, int | None, str | None, str | None, bool]:
    """Decode the image once: ``(width, height, taken_at, camera, has_gps)``."""
    if not PILLOW_AVAILABLE:
        return None, None, None, None, False
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = int(image.width), int(image.height)
            exif = image.getexif()
    except Exception:  # Pillow raises many formats; treat all as unreadable
        return None, None, None, None, False
    tags = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
    taken = tags.get("DateTimeOriginal") or tags.get("DateTime")
    camera = " ".join(str(part) for part in (tags.get("Make"), tags.get("Model")) if part)
    return width, height, (str(taken) if taken else None), camera or None, bool(tags.get("GPSInfo"))


def describe(
    filename: str,
    data: bytes | None,
    *,
    message_date: str = "",
    message_time: str = "",
) -> PhotoFacts:
    """Describe a stored photo, comparing the file name date with the message."""
    name = filename or ""
    match = _NAME_RE.match(name)
    kind = _KINDS.get(match.group("kind").upper(), "") if match else ""
    file_date: str | None = None
    sequence: str | None = None
    if match:
        raw = match.group("date")
        try:
            file_date = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).isoformat()
        except ValueError:
            file_date = None
        sequence = match.group("seq")

    size_bytes = len(data) if data else 0
    width, height, taken_at, camera, gps = (
        _image_facts(data) if data else (None, None, None, None, False)
    )

    notes: list[str] = []
    if not name:
        notes.append("sem o arquivo no export: não há o que checar")
    elif not match:
        notes.append("o nome do arquivo não segue o padrão do WhatsApp (IMG-AAAAMMDD-WA####)")
    elif file_date and message_date:
        if file_date == message_date:
            notes.append("a data do nome do arquivo confere com a data da mensagem")
        else:
            days = abs((date.fromisoformat(message_date) - date.fromisoformat(file_date)).days)
            notes.append(
                f"o nome do arquivo diz {_br_date(file_date)} e a mensagem é de "
                f"{_br_date(message_date)} (diferença de {days} dia(s)) — "
                "pode ser encaminhada ou reenviada"
            )
    if data and taken_at is None:
        notes.append("sem EXIF: o WhatsApp remove os metadados ao exportar")
    elif taken_at is not None:
        notes.append("a imagem ainda traz a data de captura no EXIF")

    return PhotoFacts(
        filename=name,
        kind=kind,
        size_bytes=size_bytes,
        file_date=file_date,
        sequence=sequence,
        width=width,
        height=height,
        orientation=_orientation(width, height) if width and height else "",
        taken_at=taken_at,
        camera=camera,
        gps=gps,
        notes=tuple(notes),
    )


def describe_lines(
    facts: PhotoFacts, *, message_date: str = "", message_time: str = ""
) -> tuple[str, ...]:
    """The facts as labelled lines, ready for the audit panel."""
    quando = f"{_br_date(message_date)} {message_time}".strip()
    nome = f"{facts.filename} ({facts.kind})" if facts.kind else (facts.filename or "—")
    forma = f"{facts.width}x{facts.height} ({facts.orientation})" if facts.width else "—"
    tamanho = f"{_size_text(facts.size_bytes)} · {forma}" if facts.filename else "—"
    if not facts.filename:
        exif = "—"
    elif facts.taken_at:
        exif = f"{facts.taken_at} · {facts.camera}" if facts.camera else facts.taken_at
        exif += " · com GPS" if facts.gps else ""
    else:
        exif = "nenhum (o WhatsApp remove)"
    linhas = (
        f"Arquivo         : {nome}",
        f"Tamanho e forma : {tamanho}",
        f"Data no nome    : {_br_date(facts.file_date)}"
        + (f" (sequência {facts.sequence})" if facts.sequence else ""),
        f"Data da mensagem: {quando or '—'}",
        f"EXIF            : {exif}",
    )
    return linhas + tuple(f"Observação      : {nota}" for nota in facts.notes)
