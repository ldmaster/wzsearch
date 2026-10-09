from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from wzsearch.dnd import dnd_available  # noqa: E402
from wzsearch.gui import (  # noqa: E402
    default_output_name,
    validate_source,
)


def test_default_output_name_per_mode() -> None:
    assert default_output_name(Path("Conversa.zip"), "photos") == "Conversa_fotos.csv"
    assert default_output_name(Path("Conversa.txt"), "search") == "Conversa_ocorrencias.csv"
    assert default_output_name(None, "photos") == "conversa_fotos.csv"


def test_validate_source_accepts_valid(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    source.write_bytes(b"x")
    assert validate_source(source) == []


def test_validate_source_reports_problems(tmp_path: Path) -> None:
    assert validate_source(None)
    assert validate_source(tmp_path / "nao-existe.zip")
    bad = tmp_path / "chat.pdf"
    bad.write_bytes(b"x")
    assert validate_source(bad)


def test_dnd_available_is_bool() -> None:
    assert isinstance(dnd_available(), bool)
