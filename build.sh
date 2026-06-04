#!/usr/bin/env bash
#
# build.sh — costruisce il bundle Lettera25.app in modalita' standalone.
#
# Crea un virtualenv pulito, installa le dipendenze, elimina i build
# precedenti e produce dist/Lettera25.app pronto per il drag-and-drop
# in /Applications.
#
# Uso:
#     ./build.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_ROOT/.venv"
APP_NAME="Lettera 25"

cd "$PROJECT_ROOT"

echo "==> Pulizia delle build precedenti..."
rm -rf build dist

echo "==> Setup virtualenv ($VENV)..."
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Aggiornamento pip e installazione dipendenze..."
pip install --upgrade pip wheel setuptools >/dev/null
pip install -r requirements.txt

echo "==> Rigenerazione icon.icns con iconutil (se disponibile)..."
if command -v iconutil >/dev/null 2>&1; then
    iconutil -c icns assets/icon.iconset -o assets/icon.icns
    echo "    icon.icns rigenerato con iconutil"
else
    echo "    iconutil non trovato, uso il .icns gia' presente"
fi

echo "==> Esecuzione py2app (build standalone)..."
python setup.py py2app

deactivate

BUNDLE="$PROJECT_ROOT/dist/$APP_NAME.app"
# L'eseguibile dentro il bundle è il CFBundleExecutable del setup.py
# (senza spazio), separato dal nome del bundle (con spazio).
EXEC_NAME="Lettera25"

if [[ -d "$BUNDLE" ]]; then
    echo
    echo "==> Build completata: $BUNDLE"
    echo
    echo "Per aprire l'app:"
    echo "   open \"$BUNDLE\""
    echo
    echo "Per installarla nel sistema:"
    echo "   cp -R \"$BUNDLE\" /Applications/"
    echo
    echo "Per diagnosticare eventuali crash da bundle (NON da doppio clic):"
    echo "   \"$BUNDLE/Contents/MacOS/$EXEC_NAME\""
    echo
else
    echo "ERRORE: bundle non trovato in $BUNDLE" >&2
    echo "Verifica che dist/ contenga effettivamente un .app:" >&2
    ls -la "$PROJECT_ROOT/dist/" 2>&1 >&2 || true
    exit 1
fi
