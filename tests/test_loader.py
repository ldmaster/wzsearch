import zipfile
from pathlib import Path

import pytest

from wzsearch.loader import load_export


def test_loads_utf8_txt(tmp_path: Path) -> None:
    path = tmp_path / "WhatsApp Chat com Fulano.txt"
    path.write_text("12/03/2024 14:22 - Fulano: olá\n", encoding="utf-8")
    export = load_export(path)
    assert export.chat_name == "Fulano"
    assert "olá" in export.text
    assert export.media_names == frozenset()


def test_loads_cp1252_txt(tmp_path: Path) -> None:
    path = tmp_path / "chat.txt"
    path.write_bytes("mensagem ação\n".encode("cp1252"))
    export = load_export(path)
    assert "ação" in export.text


def test_loads_bom_txt(tmp_path: Path) -> None:
    path = tmp_path / "chat.txt"
    path.write_bytes(b"\xef\xbb\xbf12/03/2024 14:22 - Fulano: oi\n")
    export = load_export(path)
    assert export.text.startswith("12/03/2024")


def test_normalises_crlf(tmp_path: Path) -> None:
    path = tmp_path / "chat.txt"
    path.write_bytes(b"linha1\r\nlinha2\r\n")
    export = load_export(path)
    assert export.text == "linha1\nlinha2\n"


def test_loads_zip(tmp_path: Path) -> None:
    path = tmp_path / "WhatsApp Chat com Fulano.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("_chat.txt", "12/03/2024 14:22 - Fulano: oi\n")
        archive.writestr("midia.jpg", b"x")
    export = load_export(path)
    assert export.chat_name == "Fulano"
    assert "oi" in export.text
    assert "midia.jpg" in export.media_names


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "chat.pdf"
    path.write_bytes(b"x")
    with pytest.raises(ValueError):
        load_export(path)


def test_zip_chat_name_from_inner_txt(tmp_path: Path) -> None:
    path = tmp_path / "teste.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Essence em Movimento.txt",
            "12/03/2024 14:22 - Ana: <anexo: foto.jpg>\n",
        )
        archive.writestr("foto.jpg", b"x")
    export = load_export(path)
    assert export.chat_name == "Essence em Movimento"


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_export(tmp_path / "nope.txt")
