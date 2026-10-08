"""Tkinter desktop front-end so people can use wzsearch without a terminal.

Drag the WhatsApp export onto the window (or click to pick it), press *Gerar*
and the rows appear in the *Resultados* tab, with photo preview, sender avatars
and a *Salvar CSV* button. Generation runs on a worker thread so the window
keeps responding while a progress bar is shown.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .gui_analytics import AnalyticsView
from .gui_results import ResultsView
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

_EXPORT_TYPES = [("Export do WhatsApp", "*.zip *.txt"), ("Todos os arquivos", "*.*")]


@dataclass(frozen=True, slots=True)
class _Request:
    """Everything one run needs, gathered from a tab."""

    mode: str
    source: Path | None
    output_name: str
    dest: Path
    terms: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()
    ignore_case: bool = False


def default_output_name(source: Path, mode: str) -> str:
    """Suggest an output file name based on the export's name."""
    stem = source.stem or "conversa"
    return f"{stem}_fotos.csv" if mode == MODE_PHOTOS else f"{stem}_ocorrencias.csv"


def resolve_output_path(source: Path, name: str, dest: Path) -> Path:
    """Combine the destination folder with the (sanitised) output file name."""
    filename = name.strip() or default_output_name(source, MODE_PHOTOS)
    if not filename.lower().endswith(".csv"):
        filename += ".csv"
    return Path(dest) / filename


def validate_source(source: Path | None) -> list[str]:
    """Return problems with the chosen export (empty when fine)."""
    if source is None:
        return ["Escolha o arquivo exportado do WhatsApp (.zip ou .txt)."]
    if not source.exists():
        return [f"Arquivo não encontrado: {source}"]
    if source.suffix.lower() not in {".zip", ".txt"}:
        return ["O arquivo precisa ser .zip ou .txt."]
    return []


def validate_inputs(source: Path | None, name: str, dest: Path | None) -> list[str]:
    """Return problems with the inputs for *saving* (empty when fine)."""
    errors = validate_source(source)
    if not name.strip():
        errors.append("Digite o nome do arquivo de saída.")
    elif any(sep in name for sep in ("/", "\\")):
        errors.append("No nome do arquivo use só o nome, sem pastas.")
    if dest is None or not Path(dest).is_dir():
        errors.append("Escolha uma pasta de destino válida.")
    return errors


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
        self.name_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.terms_var = tk.StringVar()
        self.regex_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        self.drop = tk.Label(
            self,
            text="Arraste o export do WhatsApp (.zip ou .txt) aqui\nou clique para escolher",
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

        self.source_label = ttk.Label(self, text="Nenhum arquivo escolhido", foreground="#666")
        self.source_label.pack(fill="x", pady=(6, 10))

        if self.mode == MODE_SEARCH:
            self._row("Termos (separados por vírgula):", self.terms_var)
            self._row("Regex (opcional):", self.regex_var)
            ttk.Checkbutton(
                self, text="Ignorar maiúsculas/minúsculas", variable=self.case_var
            ).pack(anchor="w", pady=(4, 0))
        else:
            ttk.Label(
                self,
                text="A saída (nome e pasta) é só o padrão sugerido ao salvar o CSV.",
                foreground="#666",
            ).pack(anchor="w", pady=(4, 0))
        self._row("Nome do arquivo de saída:", self.name_var)
        self._dest_row()

        self.generate_button = ttk.Button(self, text="Gerar", command=self._generate)
        self.generate_button.pack(pady=(12, 0))

    def _row(self, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", pady=(4, 0))
        ttk.Label(frame, text=label, width=32).pack(side="left")
        ttk.Entry(frame, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _dest_row(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", pady=(4, 0))
        ttk.Label(frame, text="Pasta de destino:", width=32).pack(side="left")
        ttk.Entry(frame, textvariable=self.dest_var).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="Escolher…", command=self._choose_dest).pack(
            side="left", padx=(6, 0)
        )

    def _choose_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Escolha o export", filetypes=_EXPORT_TYPES)
        if chosen:
            self._set_source(Path(chosen))

    def _choose_dest(self) -> None:
        chosen = filedialog.askdirectory(title="Escolha a pasta de destino")
        if chosen:
            self.dest_var.set(chosen)

    def _on_drop(self, data: str) -> None:
        paths = self.tk.splitlist(data)
        if paths:
            self._set_source(Path(str(paths[0])))

    def _set_source(self, path: Path) -> None:
        self.source = path
        self.source_label.configure(text=str(path), foreground="#222")
        self.name_var.set(default_output_name(path, self.mode))
        self.dest_var.set(str(path.parent))

    def _generate(self) -> None:
        self._on_generate(self.build_request())

    def build_request(self) -> _Request:
        """Read the current widgets into a :class:`_Request`."""
        dest_text = self.dest_var.get().strip()
        return _Request(
            mode=self.mode,
            source=self.source,
            output_name=self.name_var.get().strip(),
            dest=Path(dest_text) if dest_text else Path(),
            terms=tuple(part.strip() for part in self.terms_var.get().split(",") if part.strip()),
            regexes=(self.regex_var.get().strip(),) if self.regex_var.get().strip() else (),
            ignore_case=bool(self.case_var.get()),
        )

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the *Gerar* button."""
        self.generate_button.configure(state="disabled" if busy else "normal")


class WzsearchApp:
    """The main window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("wzsearch — fotos e buscas do WhatsApp")
        self.root.minsize(760, 560)
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._panels: list[_GeneratorPanel] = []
        self._request: _Request | None = None
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
        self.status = tk.Label(bottom, text="Pronto.", anchor="w", foreground="#333")
        self.status.pack(side="left", fill="x", expand=True, padx=10)
        self.open_button = ttk.Button(
            bottom, text="Abrir pasta", command=self._open_folder, state="disabled"
        )
        self.open_button.pack(side="right")

    def _start(self, request: _Request) -> None:
        errors = validate_source(request.source)
        if request.mode == MODE_SEARCH and not request.terms and not request.regexes:
            errors.append("Informe pelo menos um termo ou um regex.")
        if errors or request.source is None:
            self._set_status(" ".join(errors) or "Escolha o arquivo exportado.", ok=False)
            return

        self._request = request
        self._set_busy(True)
        self._set_status("Lendo a conversa…")
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
                    [source],
                    request.terms,
                    request.regexes,
                    ignore_case=request.ignore_case,
                )
            self._queue.put(("rows", (rows, request.mode, source)))
        except WzsearchError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # surface any unexpected failure to the user
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
            self._set_status(str(payload), ok=False)

    def _present(self, rows: list[dict[str, object]], mode: str, source: Path) -> None:
        self._rows = rows
        self._mode = mode
        self._source = source
        self.results.show(rows, mode=mode, source=source)
        self.analytics.show(rows)
        self.notebook.select(self.results)  # type: ignore[no-untyped-call]
        what = "foto(s)" if mode == MODE_PHOTOS else "ocorrência(s)"
        pending = " · veja a aba Análises" if mode == MODE_PHOTOS else ""
        self._set_status(f"{len(rows)} {what} geradas{pending}", ok=True)

    def _save(self) -> None:
        if not self._rows:
            self._set_status("Gere uma lista antes de salvar.", ok=False)
            return
        request = self._request
        default_dir = str(request.dest) if request is not None else str(Path.home())
        default_name = (
            request.output_name
            if request is not None and request.output_name
            else default_output_name(self._source or Path("conversa"), self._mode)
        )
        chosen = filedialog.asksaveasfilename(
            title="Salvar CSV",
            defaultextension=".csv",
            initialfile=default_name,
            initialdir=default_dir,
            filetypes=[("CSV", "*.csv")],
        )
        if not chosen:
            return
        try:
            result = save_rows(self._rows, self._mode, Path(chosen))
        except WzsearchError as exc:
            self._set_status(str(exc), ok=False)
            return
        extra = f" ({result.skipped} já existiam)" if result.skipped else ""
        self._set_status(f"{result.added} linha(s) salva(s) em {chosen}{extra}", ok=True)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        for panel in self._panels:
            panel.set_busy(busy)

    def _set_status(self, message: str, *, ok: bool = True) -> None:
        self.status.configure(text=message, foreground="#1a7f37" if ok else "#c0392b")

    def _open_folder(self) -> None:
        target = self._source
        if target is None:
            return
        folder = str(target.parent)
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])


def _safe_stderr(message: str) -> None:
    """Write to stderr when a console is attached (windowed builds have none)."""
    if sys.stderr is not None:
        print(message, file=sys.stderr)


def main() -> int:
    """Start the graphical interface and return an exit code."""
    try:
        root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    except tk.TclError as exc:
        _safe_stderr(f"não foi possível abrir a interface gráfica: {exc}")
        return 1

    def _report(_exc_type: type[BaseException], exc: BaseException, _tb: object) -> None:
        messagebox.showerror("wzsearch", f"Erro inesperado: {exc}")

    root.report_callback_exception = _report
    WzsearchApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
