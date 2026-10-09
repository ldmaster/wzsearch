"""Tkinter desktop front-end so people can use wzsearch without a terminal.

One working screen: import the export, filter the list, preview the photos and
decide what counts. Remetentes, Lixeira and Dados live behind the *Ajustes*
menu, and a Help menu explains each part. Importing runs on a worker thread so
the window keeps responding while a progress bar shows.
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections.abc import Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__, backup, senders, settings, update
from .avatars import config_dir
from .dnd import TkinterDnD, dnd_available
from .gui_analytics import AnalyticsView
from .gui_data import DataView
from .gui_help import HelpWindow
from .gui_results import ResultsView, TrashView
from .gui_senders import SendersView
from .gui_update import UpdateBanner, UpdateProgress
from .gui_updates import UpdatesView
from .images import HEIF_AVAILABLE, PILLOW_AVAILABLE
from .paths import data_dir
from .pipeline import (
    MODE_PHOTOS,
    ImportResult,
    WzsearchError,
    import_photos,
)
from .scroll import bind_wheel
from .store import Store
from .writer import DB_COLUMNS, write_rows

_LOG = logging.getLogger("wzsearch.gui")

#: Window size on startup (the notebook would otherwise open as big as its
#: tallest tab).
_DEFAULT_GEOMETRY = "1120x720"
_MIN_WIDTH = 880
_MIN_HEIGHT = 540

_REPO_URL = "https://github.com/ldmaster/wzsearch"
_AUTHOR = "ldmaster"


def _wheel_scroll(tree: ttk.Treeview, rows: int) -> None:
    """Scroll a tree by ``rows`` (used as the wheel callback)."""
    tree.yview_scroll(rows, "units")


def _is_inside(widget: tk.Misc, ancestor: tk.Misc) -> bool:
    """Whether ``widget`` is ``ancestor`` or one of its descendants."""
    node: tk.Misc | None = widget
    while node is not None:
        if node is ancestor:
            return True
        node = node.master
    return False


def default_output_name(source: Path | None, mode: str) -> str:
    """Suggest an output file name based on the export's name."""
    stem = source.stem if source is not None and source.stem else "conversa"
    return f"{stem}_fotos.csv" if mode == MODE_PHOTOS else f"{stem}_ocorrencias.csv"


def validate_source(source: Path | None) -> list[str]:
    """Return problems with the chosen export (empty when fine)."""
    if source is None:
        return ["Escolha o arquivo exportado do WhatsApp (.zip ou .txt)."]
    if not source.exists():
        return [f"Arquivo não encontrado: {source}"]
    if source.suffix.lower() not in {".zip", ".txt"}:
        return ["O arquivo precisa ser .zip ou .txt."]
    return []


class WzsearchApp:
    """The main window."""

    def __init__(self, root: tk.Tk, *, log_path: Path | None = None) -> None:
        self.root = root
        self.root.title("wzsearch — fotos e buscas do WhatsApp")
        self.root.geometry(_DEFAULT_GEOMETRY)
        self.root.minsize(_MIN_WIDTH, _MIN_HEIGHT)
        self.log_path = log_path
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._window_refreshers: list[Callable[[], None]] = []
        self._tabs: dict[str, tk.Widget] = {}
        self._checking = False
        self._release: update.Release | None = None
        self._updates_view: UpdatesView | None = None
        self._update_target: Path | None = None
        self.store, self._store_warning = _open_store()
        self._build_menu()
        self._build()
        self._refresh()
        self.root.after(1500, self.check_updates)

    # -- menus ------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Como usar…", command=self._show_help)
        help_menu.add_separator()
        help_menu.add_command(label="Verificar atualizações…", command=self._check_manually)
        help_menu.add_command(label="Sobre o wzsearch", command=self._show_about)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        self.root.configure(menu=menubar)

    def _show_help(self) -> None:
        """Open the help window (topics on the left, content on the right)."""
        HelpWindow(self.root, on_open_tab=self._select_tab)

    def _show_about(self) -> None:
        """Show a short about box."""
        messagebox.showinfo(
            "Sobre o wzsearch",
            f"wzsearch {__version__}\n\n"
            "Lê uma conversa exportada do WhatsApp e mostra as fotos do chat "
            "com estatísticas.\n\n"
            f"Feito por {_AUTHOR}.\n{_REPO_URL}\n\n"
            "Python + Tkinter. O conteúdo das suas conversas não sai da máquina: a única "
            "conexão é a checagem de atualização, que pode ser desligada em Ajustes.",
        )

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="wzsearch", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self.ajustes_summary = ttk.Label(top, text="", foreground="#666")
        self.ajustes_summary.pack(side="right", padx=(0, 8))
        self.ajustes = ttk.Menubutton(top, text="⚙ Ajustes")
        ajustes_menu = tk.Menu(self.ajustes, tearoff=False)
        ajustes_menu.add_command(label="Remetentes…", command=self._open_senders)
        ajustes_menu.add_command(label="Lixeira…", command=self._open_trash)
        ajustes_menu.add_separator()
        ajustes_menu.add_command(label="Atualizações…", command=self._open_updates)
        ajustes_menu.add_command(label="Dados e backup…", command=self._open_data)
        self.ajustes.configure(menu=ajustes_menu)
        self.ajustes.pack(side="right")

        self._update_target = update.update_target()
        self.banner = UpdateBanner(
            self.root,
            installable=self._can_install(),
            on_action=self._start_update,
            on_notes=self._open_notes,
            on_dismiss=self._dismiss_update,
        )

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        self.results = ResultsView(
            self.notebook,
            store=self.store,
            on_status=self._set_status,
            on_changed=self._refresh,
            on_save=self._save,
            on_import=self._import,
            on_analytics=self._refresh_analytics,
        )
        self.notebook.add(self.results, text="Explorar")
        self.analytics = AnalyticsView(self.notebook)
        self.notebook.add(self.analytics, text="Análises")
        self._tabs = {"Explorar": self.results, "Análises": self.analytics}
        bind_wheel(self.results.tree, partial(_wheel_scroll, self.results.tree))
        # Safety net: anything over the analytics page that no widget claimed
        # (new widgets, empty areas) still scrolls it.
        self.root.bind("<MouseWheel>", self._catch_all_wheel, add="+")
        self.root.bind("<Button-4>", lambda _event: self._scroll_analytics(-1), add="+")
        self.root.bind("<Button-5>", lambda _event: self._scroll_analytics(1), add="+")

        bottom = ttk.Frame(self.root, padding=(10, 6, 10, 10))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=120)
        self.progress.pack(side="left")
        self.status = tk.Label(
            bottom, text="Pronto. Escolha o export e clique em Gerar.", anchor="w"
        )
        self.status.configure(foreground="#333")
        self.status.pack(side="left", fill="x", expand=True, padx=10)
        self.summary = ttk.Label(bottom, text="")
        self.summary.pack(side="right")

    def _select_tab(self, name: str) -> None:
        """Select a notebook tab by name (used by the Help window)."""
        widget = self._tabs.get(name)
        if widget is not None:
            self.notebook.select(widget)  # type: ignore[no-untyped-call]

    def _catch_all_wheel(self, event: tk.Event) -> None:
        """Scroll the analytics page when nothing else handled the wheel."""
        self._scroll_analytics(1 if int(getattr(event, "delta", 0) or 0) < 0 else -1)

    def _scroll_analytics(self, rows: int) -> None:
        widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        if widget is not None and _is_inside(widget, self.analytics):
            self.analytics.scroll(rows)

    # -- atualizações -----------------------------------------------------
    def _can_install(self) -> bool:
        """Whether this build is able to replace its own executable."""
        target = self._update_target
        return target is not None and update.can_swap(target)

    def _check_manually(self) -> None:
        """Look for updates when the user asks (Ajuda → Verificar atualizações…)."""
        self.check_updates(manual=True)

    def check_updates(self, *, manual: bool = False) -> None:
        """Ask GitHub for the newest release, without blocking the window."""
        if self._checking:
            return
        if self._update_target is not None:
            update.cleanup_previous(self._update_target)
        if not sys.platform.startswith("win"):
            if manual:
                self._report_updates(
                    "Esta build não se atualiza sozinha — por enquanto o updater é só do Windows."
                )
                self._set_status("Atualização automática disponível só no Windows.")
            return
        if not manual and not settings.load().check_updates:
            return
        self._checking = True
        if manual:
            self._set_status("Verificando atualizações…")
            self._report_updates("Consultando o GitHub…")
        url = os.environ.get(update.ENV_API, update.API_LATEST)
        threading.Thread(target=self._check_worker, args=(url, manual), daemon=True).start()
        self.root.after(80, self._poll)

    def _check_worker(self, url: str, manual: bool) -> None:
        self._queue.put(("release", (update.fetch_latest(url=url), manual)))

    def _report_updates(self, message: str, *, ok: bool = True) -> None:
        """Write the outcome in the Ajustes → Atualizações panel, when open."""
        view = self._updates_view
        if view is not None and view.winfo_exists():
            view.show_result(message, ok=ok)

    def _on_release(self, release: update.Release | None, *, manual: bool) -> None:
        self._checking = False
        stored = settings.load()
        stored.last_check = time.time()
        settings.save(stored)
        if release is None:
            if manual:
                self._set_status("Nenhuma versão nova por enquanto.")
                self._report_updates(
                    "Nenhuma versão nova — ou não foi possível consultar o GitHub agora."
                )
            return
        self._release = release
        self._report_updates(f"Nova versão {release.version} disponível.")
        if not manual and stored.skipped_version == release.version:
            return
        self.banner.set_action("Atualizar agora" if self._can_install() else "Baixar")
        self.banner.offer(
            f"Nova versão {release.version} disponível — você está na {__version__}.",
            before=self.notebook,
        )
        self._set_status(f"Atualização disponível: {release.version}.")

    def _open_updates(self) -> None:
        window = self._new_window("Atualizações", "660x430")
        view = UpdatesView(window, on_check=self._check_manually, on_toggle=self._set_check_updates)
        view.pack(fill="both", expand=True)
        self._updates_view = view

    def _set_check_updates(self, enabled: bool) -> None:
        stored = settings.load()
        stored.check_updates = enabled
        settings.save(stored)
        self._set_status(
            "Vou verificar atualizações ao abrir." if enabled else "Não vou checar atualizações."
        )

    def _start_update(self) -> None:
        """Banner button: update in place, or point at the release page."""
        release = self._release
        target = self._update_target
        if release is None:
            return
        if target is None or not self._can_install():
            self._set_status("Abrindo a página do release…")
            self._open_notes()
            return
        UpdateProgress(
            self.root,
            release=release,
            work_dir=data_dir() / "updates" / release.version,
            on_ready=lambda executable: self._install(target, executable),
        )

    def _install(self, target: Path, executable: Path) -> None:
        """Swap the executable and quit, so the helper script can take over."""
        try:
            update.apply_update(target, executable)
        except OSError as exc:
            self._fail(f"não foi possível iniciar a troca: {exc}")
            return
        _LOG.info("updating %s with %s", target, executable)
        self._set_status("Reiniciando na versão nova…")
        self.root.after(600, self.root.destroy)

    def _open_notes(self) -> None:
        url = self._release.notes_url if self._release is not None else _REPO_URL
        webbrowser.open(url or _REPO_URL)

    def _dismiss_update(self) -> None:
        """Hide the banner and remember not to insist on this version."""
        if self._release is not None:
            stored = settings.load()
            stored.skipped_version = self._release.version
            settings.save(stored)
        self.banner.hide()

    def _new_window(self, title: str, size: str = "920x560") -> tk.Toplevel:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry(size)
        return window

    def _track(self, window: tk.Toplevel, refresh: Callable[[], None]) -> None:
        """Keep a section window in sync while it is open."""

        def run() -> None:
            if window.winfo_exists():
                refresh()

        self._window_refreshers.append(run)

    def _deleted_rows(self) -> list[dict[str, object]]:
        deleted = [
            row for row in self.store.rows(include_deleted=True) if row["status"] == "deleted"
        ]
        return senders.rename_rows(deleted)

    def _open_senders(self) -> None:
        window = self._new_window("Remetentes")
        view = SendersView(window, on_status=self._set_status, on_changed=self._refresh)
        view.pack(fill="both", expand=True)
        view.show(self.store.rows())
        self._track(window, lambda: view.show(self.store.rows()))

    def _open_trash(self) -> None:
        window = self._new_window("Lixeira")
        view = TrashView(
            window, store=self.store, on_status=self._set_status, on_changed=self._refresh
        )
        view.pack(fill="both", expand=True)
        view.show(self._deleted_rows())
        self._track(window, lambda: view.show(self._deleted_rows()))

    def _open_data(self) -> None:
        window = self._new_window("Dados e backup", "780x520")
        view = DataView(
            window,
            data_path=self.store.path.parent,
            on_backup=self._backup,
            on_restore=self._restore,
            on_wipe=self._wipe,
        )
        view.pack(fill="both", expand=True)

    # -- data -------------------------------------------------------------
    def _refresh(self) -> None:
        stored = self.store.rows()
        self.results.show(senders.rename_rows(stored))
        self._refresh_analytics()
        self._update_counts(stored)
        for refresher in list(self._window_refreshers):
            refresher()

    def _refresh_analytics(self) -> None:
        """Rebuild the analytics (used after toggling a row in the list)."""
        self.analytics.show(senders.rename_rows(self.store.rows(only_included=True)))

    def _update_counts(self, stored: list[dict[str, object]] | None = None) -> None:
        rows = self.store.rows() if stored is None else stored
        counts = self.store.counts()
        self.summary.configure(
            text=(
                f"ativas {counts['active']} · fora da análise {counts['excluded']}"
                f" · lixeira {counts['deleted']}"
            )
        )
        senders_count = len({str(row.get("remetente", "")) for row in rows})
        self.ajustes.configure(
            text="⚙ Ajustes" if not counts["deleted"] else f"⚙ Ajustes ({counts['deleted']})"
        )
        self.ajustes_summary.configure(
            text=f"Remetentes {senders_count} · Lixeira {counts['deleted']}"
        )

    # -- actions ----------------------------------------------------------
    def _import(self, source: Path) -> None:
        errors = validate_source(source)
        if errors:
            self._fail(" ".join(errors))
            return
        self._set_busy(True)
        self._set_status("Lendo a conversa…")
        _LOG.info("import source=%s", source)
        threading.Thread(target=self._worker, args=(source,), daemon=True).start()
        self.root.after(100, self._poll)

    def _worker(self, source: Path) -> None:
        try:
            self._queue.put(("imported", import_photos([source], self.store)))
        except WzsearchError as exc:
            _LOG.warning("import error: %s", exc)
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # surface any unexpected failure to the user
            _LOG.exception("unexpected import failure")
            self._queue.put(("error", f"Erro inesperado: {exc}"))

    def _poll(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return
        self._set_busy(False)
        if kind == "imported" and isinstance(payload, ImportResult):
            self._refresh()
            self._set_status(f"{payload.added} nova(s) no banco · {payload.skipped} já estavam lá.")
        elif kind == "release" and isinstance(payload, tuple):
            release, manual = payload
            self._on_release(release, manual=bool(manual))
        else:
            self._fail(str(payload))

    def _save(self) -> None:
        rows = self.results.exportable()
        if not rows:
            self._fail("Não há linhas para salvar.")
            return
        chosen = filedialog.asksaveasfilename(
            title="Salvar CSV",
            defaultextension=".csv",
            initialfile="fotos.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not chosen:
            return
        try:
            with Path(chosen).open("w", encoding="utf-8-sig", newline="") as handle:
                write_rows(rows, handle, DB_COLUMNS)
        except OSError as exc:
            self._fail(str(exc))
            return
        self._set_status(f"{len(rows)} linha(s) salva(s) em {chosen}")
        _LOG.info("saved %s rows to %s", len(rows), chosen)

    # -- helpers ----------------------------------------------------------
    def _backup(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        chosen = filedialog.asksaveasfilename(
            title="Salvar backup",
            defaultextension=".zip",
            initialfile=f"wzsearch-backup-{stamp}.zip",
            filetypes=[("Backup do wzsearch", "*.zip")],
        )
        if not chosen:
            return
        try:
            path = backup.backup_zip(Path(chosen))
        except OSError as exc:
            self._fail(f"não foi possível criar o backup: {exc}")
            return
        self._set_status(f"Backup salvo em {path}")
        _LOG.info("backup written to %s", path)

    def _restore(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Escolher backup", filetypes=[("Backup do wzsearch", "*.zip")]
        )
        if not chosen:
            return
        confirmed = messagebox.askyesno(
            "Restaurar backup",
            "Restaurar este backup?\n\nOs dados atuais serão substituídos.",
        )
        if not confirmed:
            return
        try:
            self.store.close()
            restored = backup.restore_zip(Path(chosen))
        except (OSError, ValueError) as exc:
            self.store.reopen()
            self._fail(f"não foi possível restaurar: {exc}")
            return
        self.store.reopen()
        self.results.reset_caches()
        self._refresh()
        self._set_status(f"Backup restaurado ({', '.join(restored)}).")
        _LOG.info("restored %s", restored)

    def _wipe(self) -> None:
        confirmed = messagebox.askyesno(
            "Apagar todos os dados",
            "Apagar TODOS os dados?\n\n"
            "Isto remove as fotos registradas, os nomes de remetentes e os avatares.\n"
            "Não dá para desfazer (faça um backup antes, se precisar).",
            icon="warning",
        )
        if not confirmed:
            return
        removed = self.store.clear_all()
        backup.clear_all_data()
        self.results.reset_caches()
        self._refresh()
        self._set_status(f"Todos os dados foram apagados ({removed} registro(s)).")
        _LOG.info("wiped all data (%s records)", removed)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        self.results.set_busy(busy)

    def _set_status(self, message: str, *, ok: bool = True) -> None:
        self.status.configure(text=message, foreground="#1a7f37" if ok else "#c0392b")

    def _fail(self, message: str) -> None:
        """Show a visible error (status line *and* a dialog)."""
        self._set_status(message, ok=False)
        _LOG.warning("user-facing error: %s", message)
        hint = f"\n\nDetalhes: {self.log_path}" if self.log_path else ""
        messagebox.showerror("wzsearch", f"{message}{hint}")


def _open_store() -> tuple[Store, str | None]:
    """Open the database, falling back to memory when it cannot be created."""
    try:
        return Store(), None
    except Exception as exc:  # noqa: BLE001 - report and keep the app usable
        _LOG.exception("could not open the database")
        return Store(":memory:"), f"não foi possível abrir o banco ({exc}); usando memória"


def _setup_logging() -> Path:
    """Send a lightweight log to the user config dir and return its path."""
    path = config_dir() / "wzsearch.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )
    except OSError:  # pragma: no cover - read-only home
        pass
    return path


def _safe_stderr(message: str) -> None:
    """Write to stderr when a console is attached (windowed builds have none)."""
    if sys.stderr is not None:
        print(message, file=sys.stderr)


def main() -> int:
    """Start the graphical interface and return an exit code."""
    log_path = _setup_logging()
    try:
        root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    except tk.TclError as exc:
        _safe_stderr(f"não foi possível abrir a interface gráfica: {exc}")
        return 1

    _LOG.info(
        "start frozen=%s dnd=%s pillow=%s heif=%s",
        getattr(sys, "frozen", False),
        dnd_available(),
        PILLOW_AVAILABLE,
        HEIF_AVAILABLE,
    )

    def _report(_exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
        _LOG.error("unhandled callback error", exc_info=(type(exc), exc, tb))  # type: ignore[arg-type]
        messagebox.showerror("wzsearch", f"Erro inesperado: {exc}\n\nDetalhes: {log_path}")

    root.report_callback_exception = _report
    app = WzsearchApp(root, log_path=log_path)
    if app._store_warning is not None:
        app._set_status(app._store_warning, ok=False)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
