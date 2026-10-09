"""Check for, download and install the next release (Windows only).

The release artifact is a single-file executable signed with Windows
Authenticode. The updater asks GitHub for the newest tag, downloads the zip,
checks the code signature *and* the version stored inside the PE, and only then
swaps the running file — through a tiny ``.cmd`` helper, because Windows refuses
to overwrite a running executable.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .paths import data_dir

API_LATEST = "https://api.github.com/repos/ldmaster/wzsearch/releases/latest"

#: Name of the asset the updater installs, and of the executable inside it.
ASSET_NAME = "wzsearch-windows.zip"
EXE_NAME = "wzsearch.exe"

#: Publisher of the certificate that signs the official builds. Pinning the
#: subject is what makes the signature meaningful: a build signed by anybody
#: else is refused.
SIGNATURE_SUBJECT = "SignPath Foundation"

#: Environment override used by the tests and by local rehearsals.
ENV_API = "WZSEARCH_UPDATE_API"

_TIMEOUT = 8
_CHUNK = 64 * 1024
_DETACHED = 0x00000008  # DETACHED_PROCESS
_NEW_GROUP = 0x00000200  # CREATE_NEW_PROCESS_GROUP
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

_SWAP_SCRIPT = """@echo off
rem Troca o wzsearch.exe depois que o aplicativo fecha. Gerado pela atualizacao.
setlocal
set "TARGET={target}"
set "NEW={new}"
set "BACKUP={target}.old"
set /a TRIES=0
:wait
timeout /t 1 /nobreak >nul
copy /y "%TARGET%" "%BACKUP%" >nul 2>&1
copy /y "%NEW%" "%TARGET%" >nul 2>&1
if not errorlevel 1 goto done
set /a TRIES+=1
if %TRIES% lss 30 goto wait
if exist "%BACKUP%" copy /y "%BACKUP%" "%TARGET%" >nul 2>&1
exit /b 1
:done
if exist "%BACKUP%" del "%BACKUP%" >nul 2>&1
start "" "%TARGET%"
exit /b 0
"""


class UpdateError(RuntimeError):
    """Raised when a downloaded release may not be installed."""


@dataclass(frozen=True, slots=True)
class Release:
    """The bits of a GitHub release the updater cares about."""

    version: str
    url: str
    notes_url: str
    size: int


@dataclass(frozen=True, slots=True)
class Signature:
    """Result of asking Windows about a file's Authenticode signature."""

    status: str
    subject: str


# -- versions -------------------------------------------------------------
def parse_version(text: str) -> tuple[int, ...]:
    """Turn ``v0.9.1`` (or ``0.9.1``) into ``(0, 9, 1)``; empty when unparseable."""
    match = re.match(r"^v?(\d+(?:\.\d+)*)", text.strip())
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(candidate: str, current: str = __version__) -> bool:
    """Whether ``candidate`` is newer than ``current``."""
    theirs, ours = parse_version(candidate), parse_version(current)
    return bool(theirs) and theirs > ours


def should_install(
    *, candidate: str, current: str, signature: str, subject: str
) -> tuple[bool, str]:
    """Decide whether a downloaded executable may replace the running one.

    Returns the verdict and a human-readable reason (empty when accepted).
    Fails closed: without a valid Authenticode signature nothing is installed.
    """
    if not parse_version(candidate):
        return False, "não foi possível ler a versão do arquivo baixado"
    if not is_newer(candidate, current):
        return False, f"a versão baixada ({candidate}) não é mais nova que a atual ({current})"
    if signature != "Valid":
        return False, f"assinatura digital inválida ({signature or 'sem assinatura'})"
    if SIGNATURE_SUBJECT.lower() not in subject.lower():
        return False, f"arquivo assinado por outra entidade ({subject or 'desconhecida'})"
    return True, ""


# -- talking to GitHub ----------------------------------------------------
def release_for_platform(
    payload: Mapping[str, Any], *, platform: str | None = None
) -> Release | None:
    """Pick the asset this machine can install (nothing outside Windows)."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return None
    tag = str(payload.get("tag_name", "") or "")
    if not is_newer(tag):
        return None
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict) or str(asset.get("name", "")) != ASSET_NAME:
            continue
        return Release(
            version=tag.lstrip("v"),
            url=str(asset.get("browser_download_url", "") or ""),
            notes_url=str(payload.get("html_url", "") or ""),
            size=int(asset.get("size", 0) or 0),
        )
    return None


def fetch_latest(
    *,
    url: str = API_LATEST,
    platform: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> Release | None:
    """Ask GitHub for the newest release; ``None`` when offline or up to date."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"wzsearch/{__version__}",
        },
    )
    try:
        with opener(request, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read())
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return release_for_platform(payload, platform=platform)


# -- downloading ----------------------------------------------------------
def download(
    url: str,
    destination: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> Path:
    """Save ``url`` to ``destination``, reporting ``(done, total)`` bytes.

    Raises:
        UpdateError: when ``should_stop`` asks to give up (partial file removed).
    """
    request = urllib.request.Request(url, headers={"User-Agent": f"wzsearch/{__version__}"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with opener(request, timeout=_TIMEOUT * 5) as response:
            total = int(response.headers.get("Content-Length", 0) or 0)
            done = 0
            with destination.open("wb") as handle:
                for chunk in _chunks(response):
                    if should_stop is not None and should_stop():
                        raise UpdateError("download cancelado")
                    handle.write(chunk)
                    done += len(chunk)
                    if on_progress is not None:
                        on_progress(done, total)
    except UpdateError:
        with contextlib.suppress(OSError):
            destination.unlink()
        raise
    return destination


def _chunks(response: Any) -> Iterator[bytes]:
    while True:
        chunk = response.read(_CHUNK)
        if not chunk:
            return
        yield chunk


def extract_executable(archive: Path, directory: Path) -> Path:
    """Extract (and return) the executable from the release zip."""
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if name.rsplit("/", 1)[-1].lower() == EXE_NAME:
                bundle.extract(name, directory)
                found = directory / name
                if found.exists():
                    return found
    raise UpdateError(f"o pacote baixado não contém {EXE_NAME}")


# -- asking Windows about the file ---------------------------------------
def _powershell(script: str) -> str:
    """Run a PowerShell snippet and return its trimmed output."""
    if not sys.platform.startswith("win"):
        return ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def _quote(path: Path) -> str:
    return str(path).replace("'", "''")


def signature_of(path: Path) -> Signature:
    """Ask Windows for the Authenticode status and signer of ``path``."""
    script = (
        f"$s = Get-AuthenticodeSignature -LiteralPath '{_quote(path)}'; "
        "if ($s.SignerCertificate) { $sub = $s.SignerCertificate.Subject } "
        "else { $sub = '' }; "
        "Write-Output ($s.Status.ToString() + '|' + $sub)"
    )
    status, _, subject = _powershell(script).partition("|")
    return Signature(status=status, subject=subject)


def product_version_of(path: Path) -> str:
    """Read the version stored in the executable's PE resource."""
    script = f"Write-Output (Get-Item -LiteralPath '{_quote(path)}').VersionInfo.ProductVersion"
    return _powershell(script)


# -- installing ----------------------------------------------------------
def update_target() -> Path | None:
    """The executable to replace, when this build is able to replace itself."""
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("win"):
        return None
    return Path(sys.executable)


def can_swap(target: Path) -> bool:
    """Whether the folder holding the executable is writable."""
    return target.parent.is_dir() and os.access(target.parent, os.W_OK)


def windows_script(target: Path, new_exe: Path, *, pid: int) -> str:
    """Build the ``.cmd`` that swaps the executable once this process is gone."""
    return _SWAP_SCRIPT.format(target=target, new=new_exe, pid=pid)


def apply_update(target: Path, new_exe: Path, *, pid: int | None = None) -> Path:
    """Write the swap script and start it detached; returns the script path."""
    script = data_dir() / "updates" / "apply.cmd"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        windows_script(target, new_exe, pid=os.getpid() if pid is None else pid), encoding="utf-8"
    )
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        cwd=str(script.parent),
        creationflags=_DETACHED | _NEW_GROUP | _NO_WINDOW,
        close_fds=True,
    )
    return script


def prepare(
    release: Release,
    work_dir: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Path:
    """Download and verify a release, returning the executable to install.

    Raises:
        UpdateError: when the file is not installable (bad signature, not newer).
    """
    archive = download(
        release.url, work_dir / ASSET_NAME, on_progress=on_progress, should_stop=should_stop
    )
    executable = extract_executable(archive, work_dir)
    signature = signature_of(executable)
    verdict, reason = should_install(
        candidate=product_version_of(executable),
        current=__version__,
        signature=signature.status,
        subject=signature.subject,
    )
    if not verdict:
        # A file that failed verification must not stay around on disk.
        for leftover in (executable, archive):
            with contextlib.suppress(OSError):
                leftover.unlink()
        raise UpdateError(reason)
    return executable


def cleanup_previous(target: Path) -> None:
    """Delete the backup left by a previous update (best effort)."""
    with contextlib.suppress(OSError):
        Path(f"{target}.old").unlink()
