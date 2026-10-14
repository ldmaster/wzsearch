from typing import Any

from wzsearch.photometa import describe, describe_lines


def test_name_gives_the_date_and_the_kind() -> None:
    facts = describe(
        "IMG-20260921-WA0011.jpg", None, message_date="2026-09-21", message_time="08:07"
    )
    assert facts.kind == "foto"
    assert facts.file_date == "2026-09-21"
    assert facts.sequence == "0011"
    assert facts.size_bytes == 0
    assert any("confere" in nota for nota in facts.notes)


def test_name_date_is_compared_with_the_message() -> None:
    facts = describe(
        "IMG-20260921-WA0002.jpg", None, message_date="2026-09-22", message_time="08:07"
    )
    assert facts.file_date == "2026-09-21"
    assert any("diferença de 1 dia" in nota for nota in facts.notes)


def test_media_without_a_whatsapp_name() -> None:
    facts = describe("foto-editada.png", b"\x89PNG", message_date="2026-09-21")
    assert facts.kind == ""
    assert facts.file_date is None
    assert any("não segue o padrão" in nota for nota in facts.notes)


def test_pending_photo_has_nothing_to_check() -> None:
    facts = describe("", None)
    assert facts.filename == ""
    assert facts.size_bytes == 0
    assert facts.notes == ("sem o arquivo no export: não há o que checar",)


def test_describe_lines_are_labelled() -> None:
    facts = describe(
        "IMG-20260921-WA0011.jpg", None, message_date="2026-09-21", message_time="08:07"
    )
    linhas = describe_lines(facts, message_date="2026-09-21", message_time="08:07")
    texto = "\n".join(linhas)
    assert "Arquivo         : IMG-20260921-WA0011.jpg (foto)" in texto
    assert "Data no nome    : 21/09/2026 (sequência 0011)" in texto
    assert "Data da mensagem: 21/09/2026 08:07" in texto
    assert "EXIF            : nenhum (o WhatsApp remove)" in texto


def test_describe_reads_the_file_when_pillow_is_available() -> None:
    """Com Pillow, o tamanho e a forma saem do próprio arquivo."""
    import pytest

    pytest.importorskip("PIL")
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (900, 1600), "white").save(buffer, format="JPEG")
    data = buffer.getvalue()

    facts = describe("IMG-20260921-WA0011.jpg", data, message_date="2026-09-21")
    assert facts.size_bytes == len(data)
    assert (facts.width, facts.height) == (900, 1600)
    assert facts.orientation == "retrato"
    assert facts.taken_at is None  # imagem nova, sem EXIF

    linhas: list[Any] = list(describe_lines(facts, message_date="2026-09-21"))
    assert any("900x1600 (retrato)" in linha for linha in linhas)
