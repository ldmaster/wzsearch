"""Core value objects shared across the wzsearch pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MediaRef:
    """A media placeholder found inside a message body.

    ``filename`` is the name written in the export (``None`` for placeholders
    such as "Mídia oculta"). ``exists_in_export`` is ``True`` only when the
    referenced file is actually present beside the chat text (never for plain
    ``.txt`` exports or omitted media).
    """

    filename: str | None = None
    omitted: bool = False
    exists_in_export: bool = False

    @property
    def present(self) -> bool:
        """Whether the message carries any media placeholder."""
        return self.filename is not None or self.omitted


@dataclass(frozen=True, slots=True)
class Message:
    """A single parsed chat message or system notice."""

    message_id: int
    timestamp: datetime
    sender: str | None
    text: str
    is_system: bool
    raw: str
    media: MediaRef
