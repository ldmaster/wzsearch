from pathlib import Path

import pytest

from wzsearch import senders


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))


def test_names_are_empty_by_default() -> None:
    assert senders.load_names() == {}


def test_set_and_remove_name() -> None:
    senders.set_name("+55 11 91234-5678", "Ana")
    assert senders.load_names() == {"+55 11 91234-5678": "Ana"}
    senders.remove_name("+55 11 91234-5678")
    assert senders.load_names() == {}


def test_rename_rows_uses_the_name_and_keeps_the_original() -> None:
    senders.set_name("+55 11 91234-5678", "Ana")
    renamed = senders.rename_rows([{"remetente": "+55 11 91234-5678", "data": "x"}])
    assert renamed[0]["remetente"] == "Ana"
    assert renamed[0]["remetente_original"] == "+55 11 91234-5678"


def test_rename_rows_keeps_unknown_senders() -> None:
    renamed = senders.rename_rows([{"remetente": "Bruno"}])
    assert renamed[0]["remetente"] == "Bruno"


def test_corrupt_file_falls_back() -> None:
    senders.names_file().write_text("{not json", encoding="utf-8")
    assert senders.load_names() == {}
