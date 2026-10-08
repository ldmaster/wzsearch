"""Turn raw export text into structured :class:`~wzsearch.models.Message`s.

The parser handles the dirty parts of the format: multiline messages that
continue without a timestamp prefix, system notices, and senders that may be a
name, a phone number, or missing entirely (1:1 exports).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .locale import detect_profile, parse_datetime
from .media import extract_media
from .models import Message

_SENDER_RE = re.compile(r"^(?P<sender>[^:\n<>]{1,64}?): (?P<text>.*)$", re.DOTALL)
_PHONE_SENDER_RE = re.compile(r"^\+?[\d(][\d\s\-().]{5,}$")
_SCHEME_LIKE = frozenset({"http", "https", "ftp", "mailto", "tel", "file"})
_USER_LABELS = frozenset({"você", "voce", "you", "eu", "me"})

_SYSTEM_RE = re.compile(
    "|".join(
        (
            r"^as mensagens e as chamadas (?:s[ãa]o|est[ãa]o|ficaram|foram).*$",
            r"^mensagens e chamadas .*$",
            r"^voc[êe] (?:criou|adicionou|removeu|retirou|alterou|mudou|saiu|entrou"
            r"|ativou|desativou|fixou|desfixou|atualizou|apagou|excluiu|deletou"
            r"|bloqueou|desbloqueou|compartilhou|iniciou|encerrou|gravou|participou)\b.*$",
            r"^voc[êe] foi (?:adicionad|removid)[oa]\b.*$",
            r"^.{1,80}\b(?:entrou|saiu|participou)\b(?: usando .*)?$",
            r"^.{1,80}\bfoi (?:adicionad|removid)[oa]\b.*$",
            r"^.{1,80}\bmudou (?:o n[úu]mero|o assunto|o nome|a imagem|a descri[çc][ãa]o"
            r"|o [íi]cone|a foto)\b.*$",
            r"^.{1,80}\bcriou (?:o|este) grupo\b.*$",
            r"^(?:esta|essa) mensagem foi (?:apagada|editada|exclu[íi]da)\b.*$",
            r"^aguardando esta mensagem\b.*$",
            r"^(?:liga[çc][ãa]o|chamada|v[íi]deo-?chamada)\b.*$",
            r"^messages and calls .*$",
            r"^you (?:created|added|removed|changed|left|joined|deleted|pinned"
            r"|unpinned|were added|were removed|changed the subject"
            r"|changed this group|changed the group)\b.*$",
            r"^.{1,80}\b(?:joined|left|was added|were added|created group)\b.*$",
            r"^this message was deleted\b.*$",
            r"^you deleted this message\b.*$",
        )
    ),
    re.IGNORECASE,
)


def _is_valid_sender(sender: str) -> bool:
    if not sender or sender.casefold() in _SCHEME_LIKE:
        return False
    if _PHONE_SENDER_RE.fullmatch(sender) is not None:
        return True
    if not any(character.isalpha() for character in sender):
        return False
    if any(character.isdigit() for character in sender):
        return False
    return len(sender) <= 48


def _split_sender(body: str) -> tuple[str | None, str]:
    match = _SENDER_RE.match(body)
    if match is None:
        return None, body
    sender = match.group("sender").strip()
    if not _is_valid_sender(sender):
        return None, body
    return sender, match.group("text")


def _resolve_sender(
    sender: str | None, *, eu: str | None, contact: str | None = None
) -> str | None:
    if sender is None:
        return contact
    if sender.casefold() in _USER_LABELS:
        return eu or sender
    return sender


def _interpret_body(
    body: str, *, eu: str | None, contact: str | None
) -> tuple[bool, str | None, str]:
    if _SYSTEM_RE.match(body.strip()) is not None:
        return True, None, body
    sender, text = _split_sender(body)
    if sender is not None:
        return False, _resolve_sender(sender, eu=eu), text
    return False, _resolve_sender(None, eu=eu, contact=contact), body


def _split_records(lines: Sequence[str], pattern: re.Pattern[str]) -> list[tuple[str, str, str]]:
    heads: list[tuple[str, str]] = []
    bodies: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        line = line.lstrip("\ufeff")
        match = pattern.match(line)
        if match is not None:
            if current is not None:
                bodies.append(current)
            current = [match.group("rest")]
            heads.append((match.group("date"), match.group("time")))
        elif current is not None:
            current.append(line)
    if current is not None:
        bodies.append(current)

    return [
        (date_str, time_str, "\n".join(body).rstrip("\n"))
        for (date_str, time_str), body in zip(heads, bodies, strict=True)
    ]


def parse_chat(
    text: str,
    *,
    chat_name: str,
    media_names: frozenset[str] = frozenset(),
    eu: str | None = None,
) -> list[Message]:
    """Parse export ``text`` into messages.

    ``chat_name`` is the contact/group label, also used as the sender for
    unmarked 1:1 messages. ``eu`` names your own side so "Você"/"You" is
    normalised to it. ``media_names`` enables media existence checks.
    """
    lines = text.split("\n")
    detected = detect_profile(lines)
    if detected is None:
        return []
    profile, pattern = detected

    messages: list[Message] = []
    for date_str, time_str, body in _split_records(lines, pattern):
        try:
            timestamp = parse_datetime(date_str, time_str, profile)
        except ValueError:
            continue
        is_system, sender, message_text = _interpret_body(body, eu=eu, contact=chat_name)
        messages.append(
            Message(
                message_id=len(messages) + 1,
                timestamp=timestamp,
                sender=sender,
                text=message_text,
                is_system=is_system,
                raw=body,
                media=extract_media(message_text, media_names=media_names),
            )
        )
    return messages
