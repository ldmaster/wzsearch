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
if [ ! -x "$VENV/bin/python" ]; then
    uv venv --python-preference only-managed --python 3.12 "$VENV"
fi
uv pip install --python "$VENV/bin/python" -e ".[gui]" "pyinstaller>=6.6,<7"

echo "==> Compilando binários"
rm -rf build dist ./*.spec
# O CLI local fica "wzsearch-cli" porque o .app (a interface) já usa "wzsearch"
# — no macOS os dois não podem ter o mesmo nome em dist/.
"$PYINSTALLER" --onefile --name wzsearch-cli --paths src packaging/wzsearch_entry.py
# A GUI vira um .app: no macOS isso exige modo onedir (--onefile é depreciado
# com --windowed e vira erro no PyInstaller 7).
"$PYINSTALLER" --windowed --name wzsearch --paths src \
    --icon packaging/icon.icns \
    --collect-all tkinterdnd2 --collect-all pillow_heif packaging/wzsearch_gui_entry.py

echo
echo "Pronto!"
echo "  App:               open \"$PWD/dist/wzsearch.app\""
echo "  Linha de comando:  \"$PWD/dist/wzsearch-cli\" --photos --csv fotos.csv \"<export>.zip\""
