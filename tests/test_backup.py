from pathlib import Path

import pytest

from wzsearch import backup, senders
from wzsearch.store import Store


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path / "data"))


def _seed() -> None:
    store = Store()
    store.add_rows(
        [
            {
                "chat": "Ana",
                "message_id": 1,
                "remetente": "Ana",
                "foto_arquivo": "foto.jpg",
                "foto_evidencia": "export.zip::foto.jpg",
            }
        ]
    )
    store.close()
    senders.set_name("Ana", "Ana Paula")


def test_backup_contains_everything(tmp_path: Path) -> None:
    _seed()
    destination = backup.backup_zip(tmp_path / "bkp.zip")
    assert destination.exists()
    import zipfile

    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
    assert {"wzsearch.db", "senders.json"} <= names


def test_restore_brings_the_data_back(tmp_path: Path) -> None:
    _seed()
    archive = backup.backup_zip(tmp_path / "bkp.zip")
    # apaga tudo
    store = Store()
    assert store.clear_all() == 1
    store.close()
    backup.clear_all_data()
    assert senders.load_names() == {}

    restored = backup.restore_zip(archive)
    assert "wzsearch.db" in restored
    store = Store()
    assert len(store.rows()) == 1
    assert senders.load_names() == {"Ana": "Ana Paula"}
    store.close()


def test_restore_rejects_foreign_zip(tmp_path: Path) -> None:
    import zipfile

    foreign = tmp_path / "outro.zip"
    with zipfile.ZipFile(foreign, "w") as archive:
        archive.writestr("qualquer.txt", "x")
    with pytest.raises(ValueError):
        backup.restore_zip(foreign)


def test_restore_rejects_non_zip(tmp_path: Path) -> None:
    bad = tmp_path / "nao.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ValueError):
        backup.restore_zip(bad)
