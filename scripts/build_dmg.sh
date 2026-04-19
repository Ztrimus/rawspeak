#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

VERSION=$(python -c "from rawspeak import __version__; print(__version__)")
APP_NAME="RawSpeak"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "==> Building ${APP_NAME} v${VERSION}"

echo "--- Building headless backend binary ---"
mkdir -p electron/resources/backend
pyinstaller backend_entry.py \
  --name rawspeak-backend \
  --onefile \
  --noconsole \
  --distpath electron/resources/backend \
  --workpath build/backend \
  --specpath build/backend \
  --clean

echo "--- Installing Electron dependencies ---"
(cd electron && npm ci)

echo "--- Building Electron DMG ---"
(cd electron && npm run dist:mac)

if [ -f "electron/dist/${DMG_NAME}" ]; then
  echo "==> DMG created: electron/dist/${DMG_NAME}"
else
  ls dist/*.dmg 2>/dev/null && echo "==> DMG created (name may vary from create-dmg)" \
    || { echo "ERROR: DMG creation failed"; exit 1; }
fi
