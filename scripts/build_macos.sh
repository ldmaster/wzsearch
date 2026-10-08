#!/usr/bin/env bash
# Build standalone macOS binaries (CLI + GUI) for local testing.
#
# Uses a uv-managed Python because the Homebrew Python does not ship Tkinter
# (needed by the GUI). Reuses the venv on subsequent runs.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv-mac"
PYINSTALLER="$VENV/bin/pyinstaller"

echo "==> Ambiente em $VENV (Python gerenciado pelo uv, com Tkinter)"
uv python install 3.12
uv venv --python-preference only-managed --python 3.12 "$VENV"
uv pip install --python "$VENV/bin/python" -e ".[gui]" "pyinstaller>=6.6,<7"

echo "==> Compilando binários"
rm -rf build dist ./*.spec
"$PYINSTALLER" --onefile --name wzsearch --paths src packaging/wzsearch_entry.py
# A GUI vira um .app: no macOS isso exige modo onedir (--onefile é depreciado
# com --windowed e vira erro no PyInstaller 7).
"$PYINSTALLER" --windowed --name wzsearch-gui --paths src \
    --collect-all tkinterdnd2 packaging/wzsearch_gui_entry.py

echo
echo "Pronto!"
echo "  Tela (GUI):        open \"$PWD/dist/wzsearch-gui.app\""
echo "  Linha de comando:  \"$PWD/dist/wzsearch\" --photos --csv fotos.csv \"<export>.zip\""
