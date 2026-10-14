from typing import Any

from wzsearch.identity import identity_key, signature_of, strip_copy_suffix


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
    # o nome do arquivo do export e a posição da mensagem não entram na assinatura
    assert signature_of(_row()) == signature_of(_row(source="outro nome.zip", message_id=99))
    # nem diferenças de caixa/espaço no texto
    assert signature_of(_row()) == signature_of(_row(legenda="  Treino   de hoje "))


def test_signature_ignores_the_copy_suffix_in_the_stored_chat() -> None:
    """A base antiga gravou o chat com " (1)": a assinatura tem que casar igual."""
    assert signature_of(_row(chat="Ana (1)")) == signature_of(_row(chat="Ana"))
    assert signature_of(_row(chat="Conversa (2).zip")) == signature_of(_row(chat="Conversa.zip"))
    assert signature_of(_row(chat="Grupo (antigo)")) == signature_of(_row(chat="Grupo (antigo)"))


def test_signature_changes_with_the_message() -> None:
    base = signature_of(_row())
    assert base != signature_of(_row(timestamp="2024-03-12 14:23:00"))
    assert base != signature_of(_row(remetente="Bruno"))
    assert base != signature_of(_row(foto_arquivo="outra.jpg"))
    assert base != signature_of(_row(legenda=""))
    assert base != signature_of(_row(chat="Outro grupo"))


def test_identity_key_joins_signature_and_occurrence() -> None:
    assinatura = signature_of(_row())
    assert identity_key(assinatura, 1) != identity_key(assinatura, 2)
    assert identity_key(assinatura, 1).startswith(assinatura)
