import csv
import zipfile
from pathlib import Path
from typing import Any

from wzsearch.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_end_to_end_csv(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    code = main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--term",
            "pix",
            "--csv",
            str(out),
            "--eu",
            "Lucas",
        ]
    )
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 5
    assert {row["remetente"] for row in rows} == {"Fulano", "Lucas"}
    assert rows[0]["termo"] == "pix"
    assert rows[0]["chat"] == "chat_android_pt"


def test_csv_includes_numbers(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--regex",
            r"\d{3}\.\d{3}\.\d{3}-\d{2}",
            "--csv",
            str(out),
        ]
    )
    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["texto_casado"] == "123.456.789-00"
    assert rows[0]["numero_no_texto"].startswith("cpf:123.456.789-00")


def test_media_columns(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--term",
            "anexo",
            "--csv",
            str(out),
        ]
    )
    rows = _read_csv(out)
    assert rows[0]["tem_midia"] == "sim"
    assert rows[0]["arquivo_midia"] == "00000042-FOTO-2024-03-12-14-22-31.jpg"


def test_photo_evidence_columns(tmp_path: Path) -> None:
    zip_path = tmp_path / "WhatsApp Chat com Ana.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "_chat.txt",
            "12/03/2024 14:22 - +55 11 91234-5678: segue o pix <anexo: comprovante.jpg>\n",
        )
        archive.writestr("comprovante.jpg", b"\xff\xd8\xff")
    out = tmp_path / "out.csv"
    main([str(zip_path), "--term", "pix", "--csv", str(out)])
    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["remetente"] == "+55 11 91234-5678"
    assert rows[0]["telefone_remetente"] == "+55 11 91234-5678"
    assert rows[0]["tem_foto"] == "sim"
    assert rows[0]["foto_existe"] == "sim"
    assert rows[0]["foto_evidencia"] == "WhatsApp Chat com Ana.zip::comprovante.jpg"


def test_non_photo_media_has_no_photo_evidence(tmp_path: Path) -> None:
    zip_path = tmp_path / "chat.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("_chat.txt", "12/03/2024 14:22 - Ana: veja o pix <anexo: clip.mp4>\n")
        archive.writestr("clip.mp4", b"x")
    out = tmp_path / "out.csv"
    main([str(zip_path), "--term", "pix", "--csv", str(out)])
    row = _read_csv(out)[0]
    assert row["tem_midia"] == "sim"
    assert row["tem_foto"] == "nao"
    assert row["foto_evidencia"] == ""
    assert row["foto_existe"] == "nao"


def test_photo_without_file_is_flagged_not_linked(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--term",
            "anexo",
            "--csv",
            str(out),
        ]
    )
    row = _read_csv(out)[0]
    assert row["tem_foto"] == "sim"
    assert row["foto_existe"] == "nao"
    assert row["foto_evidencia"] == ""


def test_requires_a_search_term() -> None:
    assert main([str(FIXTURES / "chat_android_pt.txt")]) == 2


def test_system_messages_excluded_by_default(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--term",
            "criptografia",
            "--csv",
            str(out),
        ]
    )
    assert _read_csv(out) == []


def test_include_system(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    main(
        [
            str(FIXTURES / "chat_android_pt.txt"),
            "--term",
            "criptografia",
            "--include-system",
            "--csv",
            str(out),
        ]
    )
    assert len(_read_csv(out)) == 1


def test_photos_mode_lists_only_photos(tmp_path: Path) -> None:
    zip_path = tmp_path / "WhatsApp Chat com Ana.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "_chat.txt",
            "12/03/2024 14:22 - Ana: bom dia\n"
            "12/03/2024 14:23 - +55 11 91234-5678: <anexo: comprovante.jpg>\n"
            "12/03/2024 14:24 - Ana: veja <anexo: clip.mp4>\n"
            "12/03/2024 14:25 - Ana: <anexo: foto2.png>\n",
        )
        archive.writestr("comprovante.jpg", b"\xff\xd8\xff")
        archive.writestr("clip.mp4", b"x")
        archive.writestr("foto2.png", b"\x89PNG")
    out = tmp_path / "photos.csv"
    code = main([str(zip_path), "--photos", "--csv", str(out)])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 2
    assert "numero_no_texto" not in rows[0]
    assert rows[0]["remetente"] == "+55 11 91234-5678"
    assert rows[0]["telefone_remetente"] == "+55 11 91234-5678"
    assert rows[0]["foto_arquivo"] == "comprovante.jpg"
    assert rows[0]["foto_existe"] == "sim"
    assert rows[0]["foto_evidencia"] == "WhatsApp Chat com Ana.zip::comprovante.jpg"
    assert rows[1]["foto_id"] == "2"
    assert rows[1]["foto_arquivo"] == "foto2.png"


def test_photos_mode_without_file_is_not_linked(tmp_path: Path) -> None:
    out = tmp_path / "photos.csv"
    code = main([str(FIXTURES / "chat_android_pt.txt"), "--photos", "--csv", str(out)])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["foto_existe"] == "nao"
    assert rows[0]["foto_evidencia"] == ""


def test_photos_mode_suffixed_attachment(tmp_path: Path) -> None:
    zip_path = tmp_path / "teste.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Grupo.txt",
            "21/09/2026 17:12 - +55 11 99338-9386: IMG-20260921-WA0020.jpg (arquivo anexado)\n"
            "21/09/2026 18:58 - +55 11 91775-0392: <Mídia oculta>\n"
            "23/09/2026 12:14 - +55 19 99239-2010: VID-20260923-WA0008.mp4 (arquivo anexado)\n",
        )
        archive.writestr("IMG-20260921-WA0020.jpg", b"\xff\xd8\xff")
        archive.writestr("VID-20260923-WA0008.mp4", b"x")
    out = tmp_path / "photos.csv"
    code = main([str(zip_path), "--photos", "--csv", str(out)])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 2  # foto + <Mídia oculta> pendente; o .mp4 fica de fora
    assert {row["midia_pendente"] for row in rows} == {"sim", "nao"}
    assert all(row["foto_arquivo"] != "VID-20260923-WA0008.mp4" for row in rows)
    photo = rows[0]
    assert photo["chat"] == "Grupo"
    assert photo["remetente"] == "+55 11 99338-9386"
    assert photo["telefone_remetente"] == "+55 11 99338-9386"
    assert photo["foto_arquivo"] == "IMG-20260921-WA0020.jpg"
    assert photo["foto_existe"] == "sim"
    assert photo["foto_evidencia"] == "teste.zip::IMG-20260921-WA0020.jpg"


def _write_photo_zip(path: Path, *, extra: bool) -> None:
    text = "21/09/2026 17:12 - +55 11 99338-9386: IMG-1.jpg (arquivo anexado)\n"
    if extra:
        text += "22/09/2026 10:00 - +55 11 99338-9386: IMG-2.jpg (arquivo anexado)\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Conversa do WhatsApp com Grupo.txt", text)
        archive.writestr("IMG-1.jpg", b"x")
        if extra:
            archive.writestr("IMG-2.jpg", b"x")


def test_photos_mode_includes_pending_omitted_media(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Grupo.txt",
            "12/03/2024 14:22 - Ana: <Mídia oculta>\n"
            "12/03/2024 14:23 - Ana: <anexo: bolo.jpg> aqui o bolo\n",
        )
        archive.writestr("bolo.jpg", b"x")
    out = tmp_path / "photos.csv"
    assert main([str(zip_path), "--photos", "--csv", str(out)]) == 0
    rows = _read_csv(out)
    assert len(rows) == 2
    pending = rows[0]
    assert pending["foto_arquivo"] == ""
    assert pending["foto_evidencia"] == ""
    assert pending["foto_existe"] == "nao"
    assert pending["midia_pendente"] == "sim"
    assert pending["legenda"] == ""
    present = rows[1]
    assert present["midia_pendente"] == "nao"
    assert present["foto_existe"] == "sim"
    assert present["foto_arquivo"] == "bolo.jpg"
    assert present["legenda"] == "aqui o bolo"


def test_contexto_provavel_is_next_message_from_same_sender(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Grupo.txt",
            "12/03/2024 14:22 - Ana: <anexo: bolo.jpg>\n"
            "12/03/2024 14:23 - Bruno: não fui eu\n"
            "12/03/2024 14:24 - Ana: olha o bolo que fiz\n",
        )
        archive.writestr("bolo.jpg", b"x")
    out = tmp_path / "photos.csv"
    main([str(zip_path), "--photos", "--csv", str(out)])
    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["contexto_provavel"] == "olha o bolo que fiz"


def test_contexto_provavel_empty_without_following_message(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "Conversa do WhatsApp com Grupo.txt",
            "12/03/2024 14:22 - Ana: <anexo: bolo.jpg>\n",
        )
        archive.writestr("bolo.jpg", b"x")
    out = tmp_path / "photos.csv"
    main([str(zip_path), "--photos", "--csv", str(out)])
    assert _read_csv(out)[0]["contexto_provavel"] == ""


def test_incremental_run_twice_adds_nothing(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _write_photo_zip(zip_path, extra=False)
    out = tmp_path / "photos.csv"
    assert main([str(zip_path), "--photos", "--csv", str(out)]) == 0
    assert main([str(zip_path), "--photos", "--csv", str(out)]) == 0
    rows = _read_csv(out)
    assert len(rows) == 1
    assert rows[0]["foto_id"] == "1"


def test_incremental_adds_only_new_rows(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _write_photo_zip(zip_path, extra=False)
    out = tmp_path / "photos.csv"
    main([str(zip_path), "--photos", "--csv", str(out)])
    _write_photo_zip(zip_path, extra=True)  # a fonte cresceu
    main([str(zip_path), "--photos", "--csv", str(out)])
    rows = _read_csv(out)
    assert len(rows) == 2
    assert [row["foto_id"] for row in rows] == ["1", "2"]
    assert rows[1]["foto_arquivo"] == "IMG-2.jpg"


def test_overwrite_resets_the_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _write_photo_zip(zip_path, extra=True)
    out = tmp_path / "photos.csv"
    main([str(zip_path), "--photos", "--csv", str(out)])
    assert len(_read_csv(out)) == 2
    _write_photo_zip(zip_path, extra=False)  # fonte volta a ter 1 foto
    main([str(zip_path), "--photos", "--csv", str(out), "--overwrite"])
    assert len(_read_csv(out)) == 1


def test_incremental_search_mode(tmp_path: Path) -> None:
    out = tmp_path / "occ.csv"
    args = [str(FIXTURES / "chat_android_pt.txt"), "--term", "pix", "--csv", str(out)]
    main(args)
    main(args)
    assert len(_read_csv(out)) == 5


def test_incremental_rejects_other_schema(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    _write_photo_zip(zip_path, extra=False)
    out = tmp_path / "occ.csv"
    out.write_text("coluna_errada\n1\n", encoding="utf-8")
    assert main([str(zip_path), "--photos", "--csv", str(out)]) == 1
