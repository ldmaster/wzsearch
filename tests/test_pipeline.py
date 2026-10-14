import zipfile
from pathlib import Path

import pytest

from wzsearch.pipeline import WzsearchError, generate_photos, generate_search

FIXTURES = Path(__file__).parent / "fixtures"


def _photo_zip(path: Path, *, extra: bool = False) -> None:
    text = "21/09/2026 17:12 - +55 11 99338-9386: IMG-1.jpg (arquivo anexado)\n"
    if extra:
        text += "22/09/2026 10:00 - +55 11 99338-9386: IMG-2.jpg (arquivo anexado)\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Conversa do WhatsApp com Grupo.txt", text)
        archive.writestr("IMG-1.jpg", b"x")
        if extra:
            archive.writestr("IMG-2.jpg", b"x")


def test_generate_photos_returns_result(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _photo_zip(zip_path)
    out = tmp_path / "fotos.csv"
    result = generate_photos([zip_path], out)
    assert result.added == 1
    assert result.skipped == 0
    assert result.output == out
    assert result.label == "foto(s)"
    assert out.exists()


def test_generate_photos_is_incremental(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _photo_zip(zip_path)
    out = tmp_path / "fotos.csv"
    generate_photos([zip_path], out)
    _photo_zip(zip_path, extra=True)
    result = generate_photos([zip_path], out)
    assert result.added == 1
    assert result.skipped == 1


def test_generate_photos_ignores_the_renamed_export(tmp_path: Path) -> None:
    """O CSV não ganha linha repetida quando o export é reexportado como ' (1)'."""
    out = tmp_path / "fotos.csv"
    primeiro = tmp_path / "Conversa do WhatsApp com Grupo.zip"
    _photo_zip(primeiro)
    generate_photos([primeiro], out)

    segundo = tmp_path / "Conversa do WhatsApp com Grupo (1).zip"
    _photo_zip(segundo)
    result = generate_photos([segundo], out)

    assert result.added == 0
    assert result.skipped == 1
    assert len(out.read_text(encoding="utf-8-sig").strip().splitlines()) == 2  # header + 1


def test_generate_search_reports_invalid_regex(tmp_path: Path) -> None:
    source = FIXTURES / "chat_android_pt.txt"
    with pytest.raises(WzsearchError) as excinfo:
        generate_search([source], [], ["("], tmp_path / "o.csv")
    assert excinfo.value.exit_code == 2


def test_generate_missing_file_is_user_error(tmp_path: Path) -> None:
    with pytest.raises(WzsearchError):
        generate_photos([tmp_path / "nope.zip"], tmp_path / "fotos.csv")
