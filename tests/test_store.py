import sqlite3
import zipfile
from pathlib import Path

from wzsearch.pipeline import import_photos
from wzsearch.store import Store

#: The table as it was before the score columns existed.
_OLD_SCHEMA = """
CREATE TABLE photos (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    chat TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    remetente TEXT NOT NULL DEFAULT '',
    telefone_remetente TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '',
    hora TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT '',
    legenda TEXT NOT NULL DEFAULT '',
    contexto TEXT NOT NULL DEFAULT '',
    contexto_provavel TEXT NOT NULL DEFAULT '',
    foto_arquivo TEXT NOT NULL DEFAULT '',
    foto_evidencia TEXT NOT NULL DEFAULT '',
    foto_existe TEXT NOT NULL DEFAULT 'nao',
    midia_pendente TEXT NOT NULL DEFAULT 'sim',
    incluir INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    deleted_at TEXT,
    media BLOB,
    created_at TEXT NOT NULL
);
"""

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


def test_add_and_deduplicate() -> None:
    store = Store(":memory:")
    assert store.add_rows([_ROW], media={0: b"IMG"}).added == 1
    assert store.add_rows([_ROW]).added == 0
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


def test_new_records_start_at_one_point() -> None:
    store = Store(":memory:")
    store.add_rows([_ROW])
    stored = store.rows()[0]
    assert stored["pontos"] == 1
    assert stored["pontos_origem"] == ""


def test_exercise_caption_arrives_with_two_points() -> None:
    store = Store(":memory:")
    store.add_rows([{**_ROW, "legenda": "treino de hoje cedo"}])
    stored = store.rows()[0]
    assert stored["pontos"] == 2
    assert stored["pontos_origem"] == "auto"


def test_adjust_points_keeps_the_minimum_and_marks_manual() -> None:
    store = Store(":memory:")
    store.add_rows([_ROW])
    row_id = int(store.rows()[0]["id"])

    assert store.adjust_points([row_id], -1) == 1
    stored = store.rows()[0]
    assert stored["pontos"] == 1
    assert stored["pontos_origem"] == "manual"

    assert store.adjust_points([row_id], 1) == 1
    assert store.rows()[0]["pontos"] == 2

    assert store.set_points([row_id], 0) == 1
    assert store.rows()[0]["pontos"] == 1


def test_rescore_auto_leaves_manual_scores_alone() -> None:
    store = Store(":memory:")
    store.add_rows([_ROW])
    row_id = int(store.rows()[0]["id"])

    assert store.rescore_auto({row_id: 2}) == 1
    assert store.rows()[0]["pontos"] == 2
    assert store.rows()[0]["pontos_origem"] == "auto"

    store.set_points([row_id], 1)
    assert store.rescore_auto({row_id: 2}) == 0
    assert store.rows()[0]["pontos"] == 1


def test_reimport_keeps_a_manual_score() -> None:
    store = Store(":memory:")
    store.add_rows([_ROW])
    row_id = int(store.rows()[0]["id"])
    store.set_points([row_id], 4)

    assert store.add_rows([_ROW]).added == 0
    assert store.rows()[0]["pontos"] == 4


def test_confirm_points_keeps_the_value_and_blocks_the_heuristic() -> None:
    store = Store(":memory:")
    store.add_rows([{**_ROW, "legenda": "treino de hoje"}])
    row_id = int(store.rows()[0]["id"])
    assert store.rows()[0]["pontos"] == 2
    assert store.rows()[0]["pontos_origem"] == "auto"

    assert store.confirm_points([row_id]) == 1
    assert store.rows()[0]["pontos"] == 2
    assert store.rows()[0]["pontos_origem"] == "confirmado"

    assert store.rescore_auto({row_id: 1}) == 0
    assert store.rows()[0]["pontos"] == 2


def test_the_reason_of_an_adjustment_is_kept() -> None:
    store = Store(":memory:")
    store.add_rows([{**_ROW, "legenda": "treino"}])
    row_id = int(store.rows()[0]["id"])
    assert store.rows()[0]["pontos_motivo"] == ""

    assert store.adjust_points([row_id], -1, motivo="vi a foto: era um café") == 1
    assert store.rows()[0]["pontos"] == 1
    assert store.rows()[0]["pontos_motivo"] == "vi a foto: era um café"

    # sem motivo, a anotação anterior continua lá
    assert store.adjust_points([row_id], 1) == 1
    assert store.rows()[0]["pontos_motivo"] == "vi a foto: era um café"

    assert store.confirm_points([row_id], motivo="confirmado com a legenda") == 1
    assert store.rows()[0]["pontos_motivo"] == "confirmado com a legenda"
    assert store.rows()[0]["pontos_origem"] == "confirmado"


def test_database_without_the_reason_column_is_migrated(tmp_path: Path) -> None:
    """Banco criado antes da coluna de motivo também é ajustado."""
    path = tmp_path / "wzsearch.db"
    old = sqlite3.connect(str(path))
    old.executescript(_OLD_SCHEMA)
    old.execute(
        "INSERT INTO photos (key, remetente, legenda, created_at) VALUES (?, ?, ?, ?)",
        ("velho#1#a.jpg", "Ana", "treino", "2024-03-01T09:00:00"),
    )
    old.commit()
    old.close()

    store = Store(path)
    assert store.rows()[0]["pontos_motivo"] == ""
    row_id = int(store.rows()[0]["id"])
    assert store.adjust_points([row_id], 1, motivo="é treino") == 1
    assert store.rows()[0]["pontos_motivo"] == "é treino"


def test_rescore_unevaluated_scores_an_existing_base(tmp_path: Path) -> None:
    """Uma base que já existia antes da pontuação ser avaliada sem clique."""
    path = tmp_path / "wzsearch.db"
    old = sqlite3.connect(str(path))
    old.executescript(_OLD_SCHEMA)
    old.executemany(
        "INSERT INTO photos (key, remetente, legenda, created_at) VALUES (?, ?, ?, ?)",
        [
            ("base#1#a.jpg", "Ana", "olha o bolo", "2024-03-01T09:00:00"),
            ("base#2#b.jpg", "Ana", "treino de hoje", "2024-03-01T10:00:00"),
            ("base#3#c.jpg", "Bruno", "academia 💪", "2024-03-02T10:00:00"),
        ],
    )
    old.commit()
    old.close()

    store = Store(path)
    assert store.rescore_unevaluated() == 2
    assert [row["pontos"] for row in store.rows()] == [1, 2, 2]
    assert [row["pontos_origem"] for row in store.rows()] == ["", "auto", "auto"]

    manual_id = int(store.rows()[1]["id"])
    assert store.set_points([manual_id], 5) == 1
    assert store.rescore_unevaluated() == 0
    assert store.rows()[1]["pontos"] == 5
    assert store.rescore_unevaluated() == 0


def test_database_from_an_older_version_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "wzsearch.db"
    old = sqlite3.connect(str(path))
    old.executescript(_OLD_SCHEMA)
    old.execute(
        "INSERT INTO photos (key, remetente, legenda, created_at) VALUES (?, ?, ?, ?)",
        ("antigo#1#foto.jpg", "Ana", "olha o bolo", "2024-03-01T09:00:00"),
    )
    old.commit()
    old.close()

    store = Store(path)
    stored = store.rows()
    assert len(stored) == 1
    assert stored[0]["pontos"] == 1
    assert stored[0]["pontos_origem"] == ""
    assert store.adjust_points([int(stored[0]["id"])], 1) == 1
    assert store.rows()[0]["pontos"] == 2


# --- reimportação idempotente -------------------------------------------------

_CHAT = "Conversa do WhatsApp com Ana"

_TEXTO = (
    "12/03/2024 14:22 - Ana: <anexo: foto.jpg>\n"
    "12/03/2024 14:25 - Ana: treino de hoje\n"
    "12/03/2024 15:01 - Ana: <anexo: foto.jpg>\n"
    "12/03/2024 15:30 - Bruno: <anexo: foto.jpg>\n"
)


def _zip(tmp_path: Path, name: str, *, com_midia: bool, texto: str = _TEXTO) -> Path:
    caminho = tmp_path / name
    with zipfile.ZipFile(caminho, "w") as archive:
        archive.writestr(name.removesuffix(".zip") + ".txt", texto)
        if com_midia:
            archive.writestr("foto.jpg", b"JPEGDATA")
    return caminho


def _txt(tmp_path: Path, name: str, texto: str = _TEXTO) -> Path:
    caminho = tmp_path / name
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def _com_arquivo(store: Store) -> int:
    return sum(1 for row in store.rows() if row["foto_existe"] == "sim")


def test_reimporting_the_same_export_adds_nothing(tmp_path: Path) -> None:
    export = _zip(tmp_path, f"{_CHAT}.zip", com_midia=True)
    store = Store(":memory:")
    primeira = import_photos([export], store)
    assert (primeira.added, primeira.enriched) == (3, 0)
    segunda = import_photos([export], store)
    assert (segunda.added, segunda.enriched) == (0, 0)
    assert len(store.rows()) == 3


def test_reimporting_a_renamed_export_adds_nothing(tmp_path: Path) -> None:
    """WhatsApp chama a 2ª exportação de "… (1).zip": não pode duplicar."""
    store = Store(":memory:")
    import_photos([_zip(tmp_path, f"{_CHAT}.zip", com_midia=True)], store)
    renomeado = _zip(tmp_path, f"{_CHAT} (1).zip", com_midia=True)
    resultado = import_photos([renomeado], store)
    assert resultado.added == 0
    assert len(store.rows()) == 3


def test_reimporting_with_the_photo_completes_the_record(tmp_path: Path) -> None:
    """Importou só o texto e depois o zip com a mídia: completa, não duplica."""
    store = Store(":memory:")
    import_photos([_txt(tmp_path, f"{_CHAT}.txt")], store)
    assert len(store.rows()) == 3
    assert _com_arquivo(store) == 0

    resultado = import_photos([_zip(tmp_path, f"{_CHAT}.zip", com_midia=True)], store)
    assert (resultado.added, resultado.enriched) == (0, 3)
    assert len(store.rows()) == 3
    assert _com_arquivo(store) == 3
    assert all(row["midia_pendente"] == "nao" for row in store.rows())
    assert all(row["foto_evidencia"] for row in store.rows())


def test_importing_the_text_after_the_zip_adds_nothing(tmp_path: Path) -> None:
    store = Store(":memory:")
    import_photos([_zip(tmp_path, f"{_CHAT}.zip", com_midia=True)], store)
    resultado = import_photos([_txt(tmp_path, f"{_CHAT}.txt")], store)
    assert resultado.added == 0
    assert len(store.rows()) == 3
    assert _com_arquivo(store) == 3


def test_completing_a_record_keeps_the_score_decided(tmp_path: Path) -> None:
    store = Store(":memory:")
    import_photos([_txt(tmp_path, f"{_CHAT}.txt")], store)
    alvo = int(store.rows()[0]["id"])
    store.set_points([alvo], 5, motivo="conferi com ela")

    import_photos([_zip(tmp_path, f"{_CHAT}.zip", com_midia=True)], store)
    row = next(r for r in store.rows() if r["id"] == alvo)
    assert (row["pontos"], row["pontos_motivo"]) == (5, "conferi com ela")
    assert row["foto_existe"] == "sim"


def test_growing_export_adds_only_the_new_photo(tmp_path: Path) -> None:
    store = Store(":memory:")
    export = _zip(tmp_path, f"{_CHAT}.zip", com_midia=True)
    import_photos([export], store)
    crescido = _TEXTO + "13/03/2024 09:00 - Ana: <anexo: foto.jpg>\n"
    resultado = import_photos(
        [_zip(tmp_path, f"{_CHAT}.zip", com_midia=True, texto=crescido)], store
    )
    assert resultado.added == 1
    assert len(store.rows()) == 4
    assert _com_arquivo(store) == 4


def test_identical_consecutive_photos_are_both_kept(tmp_path: Path) -> None:
    """Duas <Mídia oculta> iguais no mesmo segundo são mensagens diferentes."""
    texto = (
        "12/03/2024 16:00 - Ana: <Mídia oculta>\n"
        "12/03/2024 16:00 - Ana: <Mídia oculta>\n"
        "12/03/2024 16:00 - Bruno: <Mídia oculta>\n"
    )
    store = Store(":memory:")
    assert import_photos([_txt(tmp_path, f"{_CHAT}.txt", texto=texto)], store).added == 3
    assert len(store.rows()) == 3
    # e reimportar continua não duplicando
    assert import_photos([_txt(tmp_path, f"{_CHAT}.txt", texto=texto)], store).added == 0
    assert len(store.rows()) == 3


def test_an_old_database_does_not_duplicate_on_reimport(tmp_path: Path) -> None:
    """Base antiga (chaves do formato velho) + export renomeado: sem duplicata."""
    store = Store(tmp_path / "wzsearch.db")
    export = _zip(tmp_path, f"{_CHAT}.zip", com_midia=True)
    import_photos([export], store)
    antigas = store.rows()
    assert len(antigas) == 3

    # apaga as colunas de identidade para simular uma base da versão anterior
    store._conn.execute("UPDATE photos SET assinatura = '', ocorrencia = 1")
    store._conn.commit()
    store.close()

    reaberta = Store(tmp_path / "wzsearch.db")
    reaberta.add_rows([])  # a migração preencheu a identidade
    resultado = import_photos([_zip(tmp_path, f"{_CHAT} (1).zip", com_midia=True)], reaberta)
    assert resultado.added == 0
    assert len(reaberta.rows()) == 3
