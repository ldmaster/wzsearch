import zipfile
from io import BytesIO
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from wzsearch import avatars  # noqa: E402
from wzsearch.images import (  # noqa: E402
    avatar_color,
    initials_avatar,
    initials_for,
    load_photo,
    sender_avatar,
)


def test_initials_for() -> None:
    assert initials_for("Ana Paula") == "AP"
    assert initials_for("+55 11 91234-5678") == "55"
    assert initials_for("Ana") == "AN"
    assert initials_for("") == "?"


def test_avatar_color_is_stable() -> None:
    assert avatar_color("Ana") == avatar_color("Ana")
    assert avatar_color("Ana").startswith("#")


def test_initials_avatar_has_requested_size() -> None:
    image = initials_avatar("Ana", 64)
    assert image is not None
    assert image.size == (64, 64)


def test_sender_avatar_prefers_user_photo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))
    photo = tmp_path / "ana.png"
    Image.new("RGB", (100, 80), "red").save(photo)
    avatars.set_avatar("Ana", photo)
    image = sender_avatar("Ana", 48)
    assert image is not None
    assert max(image.size) <= 48


def test_load_photo_reads_from_zip(tmp_path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (120, 90), "blue").save(buffer, format="PNG")
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Conversa.txt", "x")
        archive.writestr("foto.png", buffer.getvalue())
    image = load_photo(zip_path, "foto.png", 40)
    assert image is not None
    assert max(image.size) <= 40


def test_load_photo_missing_returns_none(tmp_path: Path) -> None:
    assert load_photo(tmp_path / "nope.zip", "x.png", 40) is None
    assert load_photo(tmp_path / "chat.txt", "x.png", 40) is None
