from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from wzsearch.gui import (  # noqa: E402
    default_output_name,
    resolve_output_path,
    validate_inputs,
)


def test_default_output_name_per_mode() -> None:
    assert default_output_name(Path("Conversa.zip"), "photos") == "Conversa_fotos.csv"
    assert default_output_name(Path("Conversa.txt"), "search") == "Conversa_ocorrencias.csv"


def test_resolve_output_path_appends_csv(tmp_path: Path) -> None:
    assert resolve_output_path(Path("/x/a.zip"), "saida", tmp_path) == tmp_path / "saida.csv"
    assert resolve_output_path(Path("/x/a.zip"), "saida.csv", tmp_path) == tmp_path / "saida.csv"


def test_validate_inputs_accepts_valid(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    source.write_bytes(b"x")
    assert validate_inputs(source, "out.csv", tmp_path) == []


def test_validate_inputs_reports_problems(tmp_path: Path) -> None:
    assert validate_inputs(None, "out.csv", tmp_path)
    source = tmp_path / "chat.zip"
    source.write_bytes(b"x")
    assert validate_inputs(source, "", tmp_path)
    assert validate_inputs(source, "sub/out.csv", tmp_path)
    assert validate_inputs(source, "out.csv", tmp_path / "nao-existe")
