from typing import Any

from wzsearch.identity import (
    duplicate_groups,
    identity_key,
    signature_of,
    strip_copy_suffix,
)


def test_strip_copy_suffix_removes_whatsapp_renaming() -> None:
    assert strip_copy_suffix("Conversa do WhatsApp com Ana (1)") == "Conversa do WhatsApp com Ana"
    assert strip_copy_suffix("Conversa (12)") == "Conversa"
    assert strip_copy_suffix("Conversa do WhatsApp com Ana") == "Conversa do WhatsApp com Ana"
    # parênteses que fazem parte do nome, sem número, continuam lá
    assert strip_copy_suffix("Grupo (antigo)") == "Grupo (antigo)"
    # o WhatsApp põe o sufixo antes da extensão, no nome do arquivo
    assert strip_copy_suffix("Conversa (1).zip") == "Conversa.zip"
    assert strip_copy_suffix("WhatsApp Chat with Ana (2).txt") == "WhatsApp Chat with Ana.txt"


def _row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "chat": "Ana",
        "timestamp": "2024-03-12 14:22:00",
        "remetente": "Ana",
        "foto_arquivo": "foto.jpg",
        "legenda": "treino de hoje",
    }
    row.update(extra)
    return row


def test_signature_is_stable_for_the_same_message() -> None:
    assert signature_of(_row()) == signature_of(dict(_row()))
    # só os dados da mensagem entram: a fonte (arquivo do export, chat, posição) não
    assert signature_of(_row()) == signature_of(_row(source="outro nome.zip", message_id=99))
    assert signature_of(_row()) == signature_of(_row(chat="Ana (1)"))
    assert signature_of(_row()) == signature_of(_row(chat="outra conversa"))
    # nem diferenças de caixa/espaço no texto
    assert signature_of(_row()) == signature_of(_row(legenda="  Treino   de hoje "))


def test_signature_changes_with_the_message() -> None:
    base = signature_of(_row())
    assert base != signature_of(_row(timestamp="2024-03-12 14:23:00"))
    assert base != signature_of(_row(remetente="Bruno"))
    assert base != signature_of(_row(foto_arquivo="outra.jpg"))
    assert base != signature_of(_row(legenda=""))


def test_identity_key_joins_signature_and_occurrence() -> None:
    assinatura = signature_of(_row())
    assert identity_key(assinatura, 1) != identity_key(assinatura, 2)
    assert identity_key(assinatura, 1).startswith(assinatura)


def test_duplicate_groups_finds_the_same_message_from_two_imports() -> None:
    grupo = [
        _row(id=1, created_at="2026-01-01T10:00:00", source="Conversa.zip"),
        _row(id=2, created_at="2026-02-01T09:00:00", source="Conversa (1).zip"),
    ]
    assert duplicate_groups(grupo) == [grupo]


def test_duplicate_groups_leaves_identical_messages_of_one_import_alone() -> None:
    """Duas <Mídia oculta> iguais no mesmo segundo, importadas juntas, são distintas."""
    juntas = [
        _row(id=1, foto_arquivo="", legenda="", created_at="2026-01-01T10:00:00"),
        _row(id=2, foto_arquivo="", legenda="", created_at="2026-01-01T10:00:00"),
    ]
    assert duplicate_groups(juntas) == []


def test_duplicate_groups_ignores_different_messages() -> None:
    diferentes = [
        _row(id=1, created_at="2026-01-01T10:00:00"),
        _row(id=2, remetente="Bruno", created_at="2026-02-01T09:00:00"),
        _row(id=3, timestamp="2024-03-12 14:23:00", created_at="2026-02-01T09:00:00"),
    ]
    assert duplicate_groups(diferentes) == []
    assert duplicate_groups([]) == []
