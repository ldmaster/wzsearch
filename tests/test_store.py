import zipfile
from pathlib import Path

from wzsearch.pipeline import import_photos
from wzsearch.store import Store, row_key

_ROW = {
    "chat": "Ana",
    "message_id": 1,
    "remetente": "Ana",
    "data": "2024-03-01",
    "hora": "09:00:00",
    "timestamp": "2024-03-01 09:00:00",
    "legenda": "olha o bolo",
    "contexto": "<anexo: foto.jpg>",
    "contexto_provavel": "dia 02",
    "foto_arquivo": "foto.jpg",
    "foto_evidencia": "export.zip::foto.jpg",
    "foto_existe": "sim",
    "midia_pendente": "nao",
}


def test_row_key_is_stable() -> None:
    assert row_key(_ROW) == row_key(dict(_ROW))
    assert row_key(_ROW) != row_key({**_ROW, "message_id": 2})


def test_add_and_deduplicate() -> None:
    store = Store(":memory:")
    key = row_key(_ROW)
    assert store.add_rows([_ROW], media={key: b"IMG"}) == 1
    assert store.add_rows([_ROW]) == 0
    stored = store.rows()
    assert len(stored) == 1
    assert stored[0]["legenda"] == "olha o bolo"
    assert store.media(stored[0]["id"]) == b"IMG"


def test_include_delete_restore_purge() -> None:
    store = Store(":memory:")
    store.add_rows([_ROW, {**_ROW, "message_id": 2}])
    ids = [record["id"] for record in store.rows()]
    assert len(ids) == 2

    assert store.set_included([ids[0]], False) == 1
    assert len(store.rows(only_included=True)) == 1
    assert store.counts()["excluded"] == 1

    assert store.delete([ids[1]]) == 1
    assert len(store.rows()) == 1
    assert store.counts() == {"active": 1, "deleted": 1, "excluded": 1}

    assert store.restore([ids[1]]) == 1
    assert len(store.rows()) == 2

    store.delete([ids[1]])
    assert store.purge() == 1
    assert len(store.rows()) == 1


def test_import_photos_embeds_media(tmp_path: Path) -> None:
    export = tmp_path / "export.zip"
    with zipfile.ZipFile(export, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Ana.txt",
            "12/03/2024 14:22 - Ana: <anexo: foto.jpg>\n",
        )
        archive.writestr("foto.jpg", b"JPEGDATA")
    store = Store(":memory:")
    result = import_photos([export], store)
    assert result.added == 1
    assert result.skipped == 0
    stored = store.rows()
    assert stored[0]["foto_arquivo"] == "foto.jpg"
    assert store.media(stored[0]["id"]) == b"JPEGDATA"
    assert import_photos([export], store).added == 0
