from pathlib import Path

import pytest

from wzsearch import avatars


def test_load_is_empty_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))
    assert avatars.load_avatars() == {}
    assert avatars.avatar_path("Ana") is None


def test_set_and_remove(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))
    image = tmp_path / "ana.png"
    image.write_bytes(b"x")
    avatars.set_avatar("Ana", image)
    assert avatars.avatar_path("Ana") == image
    assert avatars.load_avatars() == {"Ana": str(image)}
    avatars.remove_avatar("Ana")
    assert avatars.avatar_path("Ana") is None


def test_corrupt_file_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))
    avatars.avatars_file().write_text("{not json", encoding="utf-8")
    assert avatars.load_avatars() == {}
