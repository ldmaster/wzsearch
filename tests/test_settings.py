"""Tests for the settings file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wzsearch import settings


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WZSEARCH_HOME", str(tmp_path))
    return tmp_path


def test_defaults_when_file_is_absent() -> None:
    loaded = settings.load()
    assert loaded.check_updates is True
    assert loaded.skipped_version == ""
    assert loaded.highest_seen_version == ""
    assert loaded.last_check == 0.0


def test_round_trip() -> None:
    settings.save(
        settings.Settings(
            check_updates=False,
            skipped_version="0.9.0",
            highest_seen_version="0.10.0",
            last_check=1234.5,
        )
    )
    loaded = settings.load()
    assert loaded.check_updates is False
    assert loaded.skipped_version == "0.9.0"
    assert loaded.highest_seen_version == "0.10.0"
    assert loaded.last_check == 1234.5


def test_broken_file_falls_back_to_defaults() -> None:
    settings.settings_file().write_text("{not json", encoding="utf-8")
    assert settings.load() == settings.Settings()


def test_non_dict_json_falls_back_to_defaults() -> None:
    settings.settings_file().write_text(json.dumps([1, 2]), encoding="utf-8")
    assert settings.load() == settings.Settings()


def test_missing_keys_keep_defaults() -> None:
    settings.settings_file().write_text(json.dumps({"skipped_version": "1.0.0"}), encoding="utf-8")
    loaded = settings.load()
    assert loaded.skipped_version == "1.0.0"
    assert loaded.check_updates is True


def test_checked_recently() -> None:
    recent = settings.Settings(last_check=1_000_000.0)
    assert settings.checked_recently(recent, now=1_000_000.0 + 3600) is True
    assert settings.checked_recently(recent, now=1_000_000.0 + 25 * 3600) is False
    assert settings.checked_recently(settings.Settings(), now=1_000_000.0) is False
