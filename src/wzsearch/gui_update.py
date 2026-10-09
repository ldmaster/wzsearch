"""The update banner (top of the window) and the download window."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from . import update

_BANNER_BG = "#e8f5f2"
_BANNER_FG = "#0b5c50"
_ERROR_FG = "#c0392b"
_OK_FG = "#1a7f37"
_MUTED_FG = "#666666"


def human_size(size: int) -> str:
    """Format a byte count the way people read it (``12,4 MB``)."""
    if size <= 0:
        return "—"
    value = float(size)
    units = ("B", "KB", "MB", "GB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{value:.1f} GB"


def human_elapsed(seconds: float) -> str:
    """Format an elapsed time as ``m:ss``."""
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


class UpdateBanner(ttk.Frame):
    """Strip at the top of the window announcing a newer version."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        installable: bool,
        on_action: Callable[[], None],
        on_notes: Callable[[], None],
        on_dismiss: Callable[[], None],
    ) -> None:
        super().__init__(master)
        strip = tk.Frame(self, background=_BANNER_BG, padx=12, pady=8)
        strip.pack(fill="x")
        self.label = tk.Label(
            strip,
            text="",
            background=_BANNER_BG,
            foreground=_BANNER_FG,
            anchor="w",
            justify="left",
        )
        self.label.pack(side="left", fill="x", expand=True)
        self.action = ttk.Button(
            strip, text="Atualizar agora" if installable else "Baixar", command=on_action
        )
        self.action.pack(side="right")
        ttk.Button(strip, text="Ver novidades", command=on_notes).pack(side="right", padx=6)
        ttk.Button(strip, text="✕", width=3, command=on_dismiss).pack(side="right")

    def offer(self, text: str, *, before: tk.Misc) -> None:
        """Show the banner with ``text``, just above ``before``."""
        self.label.configure(text=text)
        self.pack(fill="x", padx=10, pady=(6, 0), before=before)

    def hide(self) -> None:
        """Take the banner off the window."""
        self.pack_forget()

    def set_action(self, text: str) -> None:
        """Rename the main button (``Atualizar agora`` / ``Baixar``)."""
        self.action.configure(text=text)


class UpdateProgress(tk.Toplevel):
    """Modal window with the download, so a long update is never invisible."""

    def __init__(
        self,
        master: tk.Tk | tk.Toplevel,
        *,
        release: update.Release,
        work_dir: Path,
        on_ready: Callable[[Path], None],
    ) -> None:
        super().__init__(master)
        self.title("Atualizando o wzsearch")
        self.geometry("480x210")
        self.minsize(420, 190)
        self.transient(master)
        self._release = release
        self._work_dir = work_dir
        self._on_ready = on_ready
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancelled = False
        self._started = time.monotonic()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        threading.Thread(target=self._worker, daemon=True).start()
        self.after(150, self._poll)
        self.after(500, self._tick)

    def _build(self) -> None:
        ttk.Label(
            self,
            text=f"Baixando a versão {self._release.version}",
            font=("TkDefaultFont", 12, "bold"),
            padding=(14, 12, 14, 0),
        ).pack(anchor="w")
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100, length=400)
        self.progress.pack(fill="x", padx=14, pady=(10, 4))
        self.detail = ttk.Label(self, text="começando…", foreground=_MUTED_FG)
        self.detail.pack(anchor="w", padx=14)
        self.timer = ttk.Label(self, text="0:00", foreground=_MUTED_FG)
        self.timer.pack(anchor="w", padx=14)
        self.status = ttk.Label(self, text="", wraplength=440, justify="left")
        self.status.pack(anchor="w", padx=14, pady=(8, 0))
        self.close_button = ttk.Button(self, text="Fechar", command=self.destroy, state="disabled")
        self.close_button.pack(anchor="e", padx=14, pady=10)

    # -- work -------------------------------------------------------------
    def _worker(self) -> None:
        try:
            executable = update.prepare(
                self._release,
                self._work_dir,
                on_progress=lambda done, total: self._queue.put(("progress", (done, total))),
                should_stop=lambda: self._cancelled,
            )
        except update.UpdateError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self._queue.put(("error", f"erro inesperado: {exc}"))
        else:
            self._queue.put(("ready", executable))

    def _poll(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.after(150, self._poll)
            return
        if kind == "progress" and isinstance(payload, tuple):
            self._show_progress(int(payload[0]), int(payload[1]))
            self.after(150, self._poll)
            return
        if kind == "ready" and isinstance(payload, Path):
            self.progress.configure(value=100)
            self.detail.configure(text="verificado e pronto")
            self.status.configure(
                text="Concluído — o wzsearch vai fechar e reabrir na versão nova.",
                foreground=_OK_FG,
            )
            self._on_ready(payload)
            return
        if "cancelado" in str(payload):
            self.destroy()
            return
        self.status.configure(text=f"Não deu para atualizar: {payload}", foreground=_ERROR_FG)
        self.detail.configure(text="")
        self.close_button.configure(state="normal")

    def _show_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.configure(value=done * 100 / total)
            self.detail.configure(text=f"{human_size(done)} de {human_size(total)}")
        else:
            self.detail.configure(text=f"{human_size(done)} baixados")

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self.timer.configure(text=human_elapsed(time.monotonic() - self._started))
        self.after(500, self._tick)

    def _cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        self.detail.configure(text="cancelando…")
        self.close_button.configure(state="normal")
