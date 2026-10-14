from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from wzsearch.dnd import dnd_available  # noqa: E402
from wzsearch.gui import (  # noqa: E402
    _is_inside,
    default_output_name,
    validate_source,
)
from wzsearch.gui_results import _cell, _sort_value  # noqa: E402


def test_is_inside_never_blows_up_on_a_non_widget() -> None:
    """O Tk pode devolver o caminho do widget (string) em vez do widget."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    painel = tk.Frame(root)
    filho = tk.Frame(painel)
    assert _is_inside(filho, painel)
    assert _is_inside(painel, painel)
    assert not _is_inside(painel, filho)
    assert not _is_inside("ana", painel)
    assert not _is_inside(None, painel)
    assert not _is_inside(42, painel)
    root.destroy()


def test_score_cell_shows_both_clickable_halves() -> None:
    assert _cell({"pontos": 1}, "pontos") == "− 1 +"
    assert _cell({"pontos": 3, "pontos_origem": "manual"}, "pontos") == "− 3 +"


def test_sort_value_is_numeric_where_it_matters() -> None:
    assert _sort_value({"pontos": 2}, "pontos") == 2
    assert _sort_value({"incluir": 0}, "incluido") == 0
    assert _sort_value({"incluir": 1}, "incluido") == 1
    assert _sort_value({"legenda": "ANA"}, "legenda") == "ana"
    assert _sort_value({"legenda": ""}, "legenda") == ""
    assert _sort_value({}, "foto_arquivo") == ""


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
