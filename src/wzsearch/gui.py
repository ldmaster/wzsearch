"""Tkinter desktop front-end so people can use wzsearch without a terminal.

Pick the WhatsApp export (drag it in or use the button), press *Gerar* and the
rows appear in the *Resultados* tab, with photo preview, sender avatars and a
*Salvar CSV* button. Nothing is written to disk until you save. Generation runs
on a worker thread so the window keeps responding while a progress bar shows.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .avatars import config_dir
from .gui_analytics import AnalyticsView
from .gui_results import ResultsView
from .images import HEIF_AVAILABLE, PILLOW_AVAILABLE
from .pipeline import (
    MODE_PHOTOS,
    MODE_SEARCH,
    WzsearchError,
    collect_photos,
    collect_search,
    save_rows,
)

try:  # optional: real drag-and-drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover - the button still works without it
    DND_FILES = None
    TkinterDnD = None

_LOG = logging.getLogger("wzsearch.gui")

_EXPORT_TYPES = [("Export do WhatsApp", "*.zip *.txt"), ("Todos os arquivos", "*.*")]


@dataclass(frozen=True, slots=True)
class _Request:
    """Everything one run needs, gathered from a tab."""

    mode: str
    source: Path | None
    terms: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()
    ignore_case: bool = False


def default_output_name(source: Path | None, mode: str) -> str:
    """Suggest an output file name based on the export's name."""
    stem = source.stem if source is not None and source.stem else "conversa"
    return f"{stem}_fotos.csv" if mode == MODE_PHOTOS else f"{stem}_ocorrencias.csv"


def validate_source(source: Path | None) -> list[str]:
    """Return problems with the chosen export (empty when fine)."""
    if source is None:
        return [
            "Escolha o arquivo exportado do WhatsApp (arraste ou clique em “Escolher arquivo…”)."
        ]
    if not source.exists():
        return [f"Arquivo não encontrado: {source}"]
    if source.suffix.lower() not in {".zip", ".txt"}:
        return ["O arquivo precisa ser .zip ou .txt."]
    return []


def dnd_available() -> bool:
    """Whether real drag-and-drop is available."""
    return DND_FILES is not None


def _register_drop(widget: tk.Widget, callback: Callable[[str], None]) -> None:
    """Enable drop on ``widget`` when tkinterdnd2 is available."""
    register = getattr(widget, "drop_target_register", None)
    bind = getattr(widget, "dnd_bind", None)
    if DND_FILES is None or register is None or bind is None:
        return
    register(DND_FILES)
    bind("<<Drop>>", lambda event: callback(str(event.data)))


class _GeneratorPanel(ttk.Frame):
    """Widgets for one input tab (photo listing or term search)."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        mode: str,
        on_generate: Callable[[_Request], None],
    ) -> None:
        super().__init__(master, padding=12)
        self.mode = mode
        self._on_generate = on_generate
        self.source: Path | None = None
        self.terms_var = tk.StringVar()
        self.regex_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        drop_text = "Arraste o export do WhatsApp (.zip ou .txt) aqui"
        if dnd_available():
            drop_text += "\nou clique para escolher"
        self.drop = tk.Label(
            self,
            text=drop_text,
            relief="groove",
            borderwidth=2,
            background="#f2f2f2",
            foreground="#333333",
            cursor="hand2",
            height=4,
            justify="center",
        )
        self.drop.pack(fill="x")
        self.drop.bind("<Button-1>", lambda _event: self._choose_file())
        _register_drop(self.drop, self._on_drop)

        pick = ttk.Frame(self)
        pick.pack(fill="x", pady=(8, 4))
        ttk.Button(pick, text="Escolher arquivo…", command=self._choose_file).pack(side="left")
        self.source_label = ttk.Label(pick, text="nenhum arquivo escolhido", foreground="#c0392b")
        self.source_label.pack(side="left", padx=10)

        if self.mode == MODE_SEARCH:
            self._row("Termos (separados por vírgula):", self.terms_var)
            self._row("Regex (opcional):", self.regex_var)
            ttk.Checkbutton(
                self, text="Ignorar maiúsculas/minúsculas", variable=self.case_var
            ).pack(anchor="w", pady=(4, 0))

        ttk.Label(
            self,
            text="Nada é gravado até você clicar em “Salvar CSV…” na aba Resultados.",
            foreground="#666",
        ).pack(anchor="w", pady=(8, 0))
        self.generate_button = ttk.Button(self, text="Gerar", command=self._generate)
        self.generate_button.pack(pady=(8, 0))

    def _row(self, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", pady=(4, 0))
        ttk.Label(frame, text=label, width=32).pack(side="left")
        ttk.Entry(frame, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _choose_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Escolha o export", filetypes=_EXPORT_TYPES)
        if chosen:
            self._set_source(Path(chosen))

    def _on_drop(self, data: str) -> None:
        paths = self.tk.splitlist(data)
        if paths:
            self._set_source(Path(str(paths[0])))

    def _set_source(self, path: Path) -> None:
        self.source = path
        self.source_label.configure(text=str(path), foreground="#1a7f37")

    def _generate(self) -> None:
        self._on_generate(self.build_request())

    def build_request(self) -> _Request:
        """Read the current widgets into a :class:`_Request`."""
        return _Request(
            mode=self.mode,
            source=self.source,
            terms=tuple(part.strip() for part in self.terms_var.get().split(",") if part.strip()),
            regexes=(self.regex_var.get().strip(),) if self.regex_var.get().strip() else (),
            ignore_case=bool(self.case_var.get()),
        )

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the *Gerar* button."""
        self.generate_button.configure(state="disabled" if busy else "normal")


class WzsearchApp:
    """The main window."""

    def __init__(self, root: tk.Tk, *, log_path: Path | None = None) -> None:
        self.root = root
        self.root.title("wzsearch — fotos e buscas do WhatsApp")
        self.root.minsize(780, 560)
        self.log_path = log_path
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._panels: list[_GeneratorPanel] = []
        self._rows: list[dict[str, object]] = []
        self._mode = MODE_PHOTOS
        self._source: Path | None = None
        self._build()

    def _build(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        for mode, title in ((MODE_PHOTOS, "Fotos"), (MODE_SEARCH, "Buscar termo")):
            panel = _GeneratorPanel(self.notebook, mode=mode, on_generate=self._start)
            self.notebook.add(panel, text=title)
            self._panels.append(panel)

        self.results = ResultsView(self.notebook, on_save=self._save, on_status=self._set_status)
        self.notebook.add(self.results, text="Resultados")
        self.analytics = AnalyticsView(self.notebook)
        self.notebook.add(self.analytics, text="Análises")

        bottom = ttk.Frame(self.root, padding=(10, 6, 10, 10))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=140)
        self.progress.pack(side="left")
        self.status = tk.Label(
            bottom, text="Pronto. Escolha o export e clique em Gerar.", anchor="w"
        )
        self.status.configure(foreground="#333")
        self.status.pack(side="left", fill="x", expand=True, padx=10)

    # -- actions ----------------------------------------------------------
    def _start(self, request: _Request) -> None:
        errors = validate_source(request.source)
        if request.mode == MODE_SEARCH and not request.terms and not request.regexes:
            errors.append("Informe pelo menos um termo ou um regex.")
        if errors or request.source is None:
            self._fail(" ".join(errors) or "Escolha o arquivo exportado.")
            return

        self._source = request.source
        self._mode = request.mode
        self._set_busy(True)
        self._set_status("Lendo a conversa…")
        _LOG.info("generate mode=%s source=%s", request.mode, request.source)
        threading.Thread(target=self._worker, args=(request,), daemon=True).start()
        self.root.after(100, self._poll)

    def _worker(self, request: _Request) -> None:
        source = request.source
        if source is None:
            return
        try:
            if request.mode == MODE_PHOTOS:
                rows = collect_photos([source])
            else:
                rows = collect_search(
                    [source], request.terms, request.regexes, ignore_case=request.ignore_case
                )
            self._queue.put(("rows", (rows, request.mode, source)))
        except WzsearchError as exc:
            _LOG.warning("generation error: %s", exc)
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # surface any unexpected failure to the user
            _LOG.exception("unexpected generation failure")
            self._queue.put(("error", f"Erro inesperado: {exc}"))

    def _poll(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return
        self._set_busy(False)
        if kind == "rows" and isinstance(payload, tuple):
            rows, mode, source = payload
            self._present(rows, mode, source)
        else:
            self._fail(str(payload))

    def _present(self, rows: list[dict[str, object]], mode: str, source: Path) -> None:
        self._rows = rows
        self._mode = mode
        self._source = source
        self.results.show(rows, mode=mode, source=source)
        self.analytics.show(rows)
        self.notebook.select(self.results)  # type: ignore[no-untyped-call]
        what = "foto(s)" if mode == MODE_PHOTOS else "ocorrência(s)"
        self._set_status(f"{len(rows)} {what} — veja as abas Resultados e Análises.")

    def _save(self) -> None:
        if not self._rows:
            self._fail("Gere uma lista antes de salvar.")
            return
        source = self._source
        default_dir = str(source.parent) if source is not None else str(Path.home())
        chosen = filedialog.asksaveasfilename(
            title="Salvar CSV",
            defaultextension=".csv",
            initialfile=default_output_name(source, self._mode),
            initialdir=default_dir,
            filetypes=[("CSV", "*.csv")],
        )
        if not chosen:
            return
        try:
            result = save_rows(self._rows, self._mode, Path(chosen))
        except WzsearchError as exc:
            self._fail(str(exc))
            return
        extra = f" ({result.skipped} já existiam)" if result.skipped else ""
        self._set_status(f"{result.added} linha(s) salva(s) em {chosen}{extra}")
        _LOG.info("saved %s rows to %s", result.added, chosen)

    # -- helpers ----------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        for panel in self._panels:
            panel.set_busy(busy)

    def _set_status(self, message: str, *, ok: bool = True) -> None:
        self.status.configure(text=message, foreground="#1a7f37" if ok else "#c0392b")

    def _fail(self, message: str) -> None:
        """Show a visible error (status line *and* a dialog)."""
        self._set_status(message, ok=False)
        _LOG.warning("user-facing error: %s", message)
        hint = f"\n\nDetalhes: {self.log_path}" if self.log_path else ""
        messagebox.showerror("wzsearch", f"{message}{hint}")


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
    WzsearchApp(root, log_path=log_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
