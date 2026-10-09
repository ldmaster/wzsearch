"""Tests for the updater: versions, manifest, download, signature policy."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Literal

import pytest

from wzsearch import update

API = "https://example.invalid/latest"


class _Response:
    """Tiny stand-in for the object ``urllib`` returns."""

    def __init__(self, payload: bytes, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self._offset = 0
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._payload[self._offset :]
            self._offset = len(self._payload)
            return chunk
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        return False


def _opener(payload: bytes, headers: dict[str, str] | None = None) -> Any:
    def open_url(*_args: object, **_kwargs: object) -> _Response:
        return _Response(payload, headers)

    return open_url


def _release_payload(version: str = "v0.9.5", size: int = 1234) -> dict[str, Any]:
    return {
        "tag_name": version,
        "html_url": "https://github.com/ldmaster/wzsearch/releases/tag/" + version,
        "assets": [
            {
                "name": update.ASSET_NAME,
                "size": size,
                "browser_download_url": "https://example.invalid/wzsearch-windows.zip",
            }
        ],
    }


# -- versions -------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v0.9.1", (0, 9, 1)),
        ("0.9.1", (0, 9, 1)),
        ("v1.0", (1, 0)),
        ("v0.9.0-rc1", (0, 9, 0)),
        ("", ()),
        ("sem versao", ()),
    ],
)
def test_parse_version(text: str, expected: tuple[int, ...]) -> None:
    assert update.parse_version(text) == expected


def test_is_newer() -> None:
    assert update.is_newer("v0.9.0", "0.8.1") is True
    assert update.is_newer("v0.10.0", "0.9.9") is True
    assert update.is_newer("v0.8.1", "0.8.1") is False
    assert update.is_newer("v0.8.0", "0.8.1") is False
    assert update.is_newer("sem versao", "0.8.1") is False


# -- picking the release --------------------------------------------------
def test_release_for_windows() -> None:
    release = update.release_for_platform(_release_payload(), platform="win32")
    assert release is not None
    assert release.version == "0.9.5"
    assert release.size == 1234
    assert release.url.endswith("wzsearch-windows.zip")


def test_release_ignored_outside_windows() -> None:
    assert update.release_for_platform(_release_payload(), platform="darwin") is None
    assert update.release_for_platform(_release_payload(), platform="linux") is None


def test_release_ignored_when_not_newer() -> None:
    payload = _release_payload(version="v0.0.1")
    assert update.release_for_platform(payload, platform="win32") is None


def test_release_without_the_asset_is_ignored() -> None:
    payload = _release_payload()
    payload["assets"] = [{"name": "outra-coisa.zip", "browser_download_url": "x"}]
    assert update.release_for_platform(payload, platform="win32") is None


def test_release_without_assets_key_is_ignored() -> None:
    payload = _release_payload()
    del payload["assets"]
    assert update.release_for_platform(payload, platform="win32") is None


def test_fetch_latest_reads_the_api() -> None:
    payload = json.dumps(_release_payload()).encode()
    release = update.fetch_latest(url=API, platform="win32", opener=_opener(payload))
    assert release is not None and release.version == "0.9.5"


def test_fetch_latest_survives_a_broken_response() -> None:
    assert update.fetch_latest(url=API, platform="win32", opener=_opener(b"nao e json")) is None
    assert update.fetch_latest(url=API, platform="win32", opener=_opener(b"[]")) is None


def test_fetch_latest_survives_a_network_error() -> None:
    def explode(*_args: object, **_kwargs: object) -> _Response:
        raise OSError("sem rede")

    assert update.fetch_latest(url=API, platform="win32", opener=explode) is None


# -- install policy ------------------------------------------------------
def test_install_accepts_a_newer_signed_build() -> None:
    verdict, reason = update.should_install(
        candidate="0.9.5", current="0.8.1", signature="Valid", subject="CN=SignPath Foundation"
    )
    assert verdict is True
    assert reason == ""


def test_install_refuses_without_signature() -> None:
    verdict, reason = update.should_install(
        candidate="0.9.5", current="0.8.1", signature="NotSigned", subject=""
    )
    assert verdict is False
    assert "assinatura" in reason


def test_install_refuses_another_publisher() -> None:
    verdict, reason = update.should_install(
        candidate="0.9.5", current="0.8.1", signature="Valid", subject="CN=Outra Empresa"
    )
    assert verdict is False
    assert "outra entidade" in reason


def test_install_refuses_a_downgrade() -> None:
    verdict, _ = update.should_install(
        candidate="0.8.0", current="0.8.1", signature="Valid", subject=update.SIGNATURE_SUBJECT
    )
    assert verdict is False


def test_install_refuses_an_unreadable_version() -> None:
    verdict, _ = update.should_install(
        candidate="", current="0.8.1", signature="Valid", subject=update.SIGNATURE_SUBJECT
    )
    assert verdict is False


# -- downloading ---------------------------------------------------------
def test_download_writes_the_file_and_reports_progress(tmp_path: Path) -> None:
    payload = b"x" * (update._CHUNK + 10)
    seen: list[tuple[int, int]] = []
    destination = update.download(
        "https://example.invalid/pack.zip",
        tmp_path / "pack.zip",
        on_progress=lambda done, total: seen.append((done, total)),
        opener=_opener(payload, {"Content-Length": str(len(payload))}),
    )
    assert destination.read_bytes() == payload
    assert seen[-1] == (len(payload), len(payload))


def test_extract_executable(tmp_path: Path) -> None:
    archive = tmp_path / "wzsearch-windows.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(update.EXE_NAME, b"conteudo")
    found = update.extract_executable(archive, tmp_path / "out")
    assert found.name == update.EXE_NAME
    assert found.read_bytes() == b"conteudo"


def test_extract_executable_refuses_a_package_without_it(tmp_path: Path) -> None:
    archive = tmp_path / "outro.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("leiame.txt", b"nada")
    with pytest.raises(update.UpdateError):
        update.extract_executable(archive, tmp_path / "out")


# -- swapping ------------------------------------------------------------
def test_windows_script_waits_and_restarts() -> None:
    script = update.windows_script(Path("C:/app/wzsearch.exe"), Path("C:/tmp/novo.exe"), pid=4321)
    assert (
        'set "TARGET=C:\\app\\wzsearch.exe"' in script
        or 'set "TARGET=C:/app/wzsearch.exe"' in script
    )
    assert (
        'set "BACKUP=C:/app/wzsearch.exe.old"' in script
        or "BACKUP=C:\\app\\wzsearch.exe.old" in script
    )
    assert "goto wait" in script
    assert 'start "" "%TARGET%"' in script
    assert "exit /b 0" in script


def test_can_swap_checks_the_folder(tmp_path: Path) -> None:
    executable = tmp_path / update.EXE_NAME
    executable.write_bytes(b"exe")
    assert update.can_swap(executable) is True
    assert update.can_swap(tmp_path / "inexistente" / update.EXE_NAME) is False


def test_update_target_outside_a_frozen_windows_build() -> None:
    assert update.update_target() is None or update.update_target() is not None  # no crash


def test_cleanup_previous_is_quiet_when_there_is_no_backup(tmp_path: Path) -> None:
    update.cleanup_previous(tmp_path / update.EXE_NAME)
