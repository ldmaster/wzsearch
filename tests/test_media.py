import zipfile
from pathlib import Path

from wzsearch.loader import load_export
from wzsearch.media import (
    extract_media,
    is_photo,
    normalize_media_name,
    strip_media_placeholders,
)


def test_extract_named_media() -> None:
    ref = extract_media("<anexo: foto.jpg>")
    assert ref.filename == "foto.jpg"
    assert ref.present is True
    assert ref.exists_in_export is False


def test_extract_omitted_media() -> None:
    ref = extract_media("<Mídia oculta>")
    assert ref.omitted is True
    assert ref.filename is None
    assert ref.present is True


def test_no_media() -> None:
    assert extract_media("só texto").present is False


def test_strip_placeholders() -> None:
    assert "anexo" not in strip_media_placeholders("<anexo: foto.jpg> veja")


def test_normalize_media_name_is_case_insensitive() -> None:
    assert normalize_media_name("FOTO.JPG") == normalize_media_name("foto.jpg")


def test_is_photo_by_extension() -> None:
    assert is_photo(extract_media("<anexo: foto.JPG>")) is True
    assert is_photo(extract_media("<anexo: print.png>")) is True
    assert is_photo(extract_media("<anexo: clip.mp4>")) is False
    assert is_photo(extract_media("<anexo: doc.pdf>")) is False
    assert is_photo(extract_media("<Mídia oculta>")) is False


def test_stickers_are_not_photos() -> None:
    assert is_photo(extract_media("STK-20261001-WA0008.webp (arquivo anexado)")) is False
    assert is_photo(extract_media("<anexo: IMG-20240101-WA0001.webp>")) is True


def test_extract_suffixed_filename() -> None:
    ref = extract_media("IMG-20260921-WA0011.jpg (arquivo anexado)")
    assert ref.filename == "IMG-20260921-WA0011.jpg"
    assert ref.present is True
    assert is_photo(ref) is True


def test_extract_bare_angled_filename() -> None:
    ref = extract_media("<IMG_0001.HEIC>")
    assert ref.filename == "IMG_0001.HEIC"
    assert is_photo(ref) is True


def test_omitted_still_wins_over_no_filename() -> None:
    ref = extract_media("<Mídia oculta>")
    assert ref.omitted is True
    assert ref.filename is None


def test_strip_removes_suffixed_attachment() -> None:
    stripped = strip_media_placeholders("veja IMG-20260921-WA0011.jpg (arquivo anexado)")
    assert "WA0011" not in stripped


def test_zip_media_existence(tmp_path: Path) -> None:
    zip_path = tmp_path / "WhatsApp Chat com Fulano.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("_chat.txt", "12/03/2024 14:22 - Fulano: <anexo: foto.jpg>\n")
        archive.writestr("foto.jpg", b"\xff\xd8\xff")
    export = load_export(zip_path)
    assert export.chat_name == "Fulano"
    assert "foto.jpg" in export.media_names
    ref = extract_media("<anexo: foto.jpg>", media_names=export.media_names)
    assert ref.exists_in_export is True
