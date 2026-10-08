"""Extract Brazilian identifiers and amounts from free text.

The patterns are deliberately conservative: they target well-known shapes
(CPF, CNPJ, ``R$`` amounts, phone numbers and labelled order/protocol codes)
instead of every digit run, so a match is usually meaningful. Higher-priority
patterns claim their span first, which prevents a phone number from being
reported twice.
"""

from __future__ import annotations

import re

_PHONE_SOURCE = r"(?<!\d)(?:(?:\+|00)?55[\s\-.]?)?(?:\(?\d{2}\)?[\s\-.]?)?9?\d{4,5}[\s\-]?\d{4}\b"
_PHONE_RE = re.compile(_PHONE_SOURCE)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cnpj", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("valor", re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")),
    ("telefone", _PHONE_RE),
    (
        "pedido",
        re.compile(
            r"(?<!\w)(?:pedido|protocolo|order|n[º°]|n[úu]mero|c[óo]digo|#)\s*:?\s*"
            r"([A-Za-z0-9][A-Za-z0-9._/\-]{1,})",
            re.IGNORECASE,
        ),
    ),
)


def extract_numbers(text: str) -> list[tuple[str, str]]:
    """Return distinct ``(type, value)`` findings, in order of appearance."""
    findings: list[tuple[int, str, str]] = []
    mask = [False] * len(text)
    for label, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(mask[start:end]):
                continue
            value = match.group(1) if match.groups() else match.group(0)
            for index in range(start, end):
                mask[index] = True
            findings.append((start, label, value.strip()))
    findings.sort(key=lambda finding: finding[0])

    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for _, label, value in findings:
        item = (label, value)
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def format_numbers(findings: list[tuple[str, str]]) -> str:
    """Render findings as a single CSV-friendly string."""
    return "; ".join(f"{label}:{value}" for label, value in findings)


def sender_phone(sender: str | None) -> str:
    """Return the phone number embedded in a sender label, if any."""
    if not sender:
        return ""
    match = _PHONE_RE.search(sender)
    return match.group(0).strip() if match is not None else ""
