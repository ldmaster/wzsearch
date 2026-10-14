"""Score each photo record, guessing the exercise ones from the caption.

Every record is worth at least one point; a photo whose caption (or likely
context — the next message from the same sender) mentions an exercise is worth
two. The decision is purely textual and offline: no model, no network.

What the caption suggests is only a *suggestion*. Records the heuristic flagged
keep ``pontos_origem == "auto"`` so the app can list them for review, and any
manual adjustment marks them ``"manual"`` — which the bulk re-evaluation never
touches.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

#: Smallest score a record can have.
PONTOS_MIN = 1

#: Score of a photo the caption points at as an exercise.
PONTOS_EXERCICIO = 2

#: Origin of a score nobody has touched yet.
ORIGEM_VAZIA = ""

#: Origin of a score the caption suggested.
ORIGEM_AUTO = "auto"

#: Origin of a score adjusted by hand (never rewritten by the heuristic).
ORIGEM_MANUAL = "manual"

#: Origin of a suggestion the person looked at and accepted as it was.
ORIGEM_CONFIRMADO = "confirmado"

#: Origins that mean someone decided the value: the heuristic never rewrites them.
ORIGEM_DECIDIDA = (ORIGEM_MANUAL, ORIGEM_CONFIRMADO)

#: Words that make a photo an exercise one. Written without accents, since the
#: caption is folded before matching, and matched on word boundaries.
#:
#: The list is deliberately conservative — a false positive only costs a click
#: in the review filter, but a missed caption costs a manual point. Extend it
#: here when a new way of writing "treino" shows up in the conversations.
_EXERCISE_TERMS = frozenset(
    {
        "abdominal",
        "abdominais",
        "academia",
        "aerobica",
        "agachamento",
        "alongamento",
        "barra fixa",
        "basquete",
        "beach tennis",
        "bicicleta",
        "bike",
        "boxe",
        "caminhada",
        "caminhei",
        "cardio",
        "corri",
        "corrida",
        "correndo",
        "crossfit",
        "escalada",
        "esteira",
        "exercicio",
        "exercicios",
        "flexao",
        "flexoes",
        "futebol",
        "ginastica",
        "hidroginastica",
        "hiit",
        "jiujitsu",
        "muaythai",
        "musculacao",
        "nadar",
        "nadei",
        "natacao",
        "pedal",
        "pedalada",
        "pilates",
        "running",
        "spinning",
        "supino",
        "surf",
        "treinei",
        "treinando",
        "treino",
        "treinos",
        "trilha",
        "volei",
        "wod",
        "workout",
        "yoga",
    }
)

_TERM_RE = re.compile(rf"\b(?:{'|'.join(sorted(_EXERCISE_TERMS))})\b")


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key, "") or "")


def fold(text: str) -> str:
    """Lowercase ``text`` and drop its accents, so matching ignores spelling."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def matched_terms(legenda: str, contexto_provavel: str) -> tuple[str, ...]:
    """The exercise words the caption matched, in the order they appear."""
    found = _TERM_RE.findall(fold(f"{legenda}\n{contexto_provavel}"))
    return tuple(dict.fromkeys(found))


def is_exercise(legenda: str, contexto_provavel: str) -> bool:
    """Whether the caption or the likely context mentions an exercise."""
    return bool(matched_terms(legenda, contexto_provavel))


def score_for(row: Mapping[str, object]) -> tuple[int, str]:
    """Return the ``(pontos, origem)`` a record earns on import."""
    if is_exercise(_text(row, "legenda"), _text(row, "contexto_provavel")):
        return PONTOS_EXERCICIO, ORIGEM_AUTO
    return PONTOS_MIN, ORIGEM_VAZIA


def terms_for(row: Mapping[str, object]) -> tuple[str, ...]:
    """The exercise words found in a record's caption (used by the audit screen)."""
    return matched_terms(_text(row, "legenda"), _text(row, "contexto_provavel"))


def match_reason(row: Mapping[str, object]) -> str:
    """Why a record looks like an exercise: the words and where they came from."""
    terms = terms_for(row)
    if not terms:
        return ""
    na_legenda = [term for term in terms if term in fold(_text(row, "legenda"))]
    where = "na legenda" if na_legenda else "na mensagem seguinte da mesma pessoa"
    return f"“{', '.join(terms)}” {where}"


def suggestions(rows: Sequence[Mapping[str, object]]) -> dict[int, int]:
    """Map each record ``id`` to the score the captions suggest for it."""
    suggested: dict[int, int] = {}
    for row in rows:
        row_id = row.get("id")
        if row_id is None:
            continue
        points, _origin = score_for(row)
        suggested[int(str(row_id))] = points
    return suggested
