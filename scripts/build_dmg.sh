#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

VERSION=$(python -c "from rawspeak import __version__; print(__version__)")
APP_NAME="RawSpeak"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "==> Building ${APP_NAME} v${VERSION}"

echo "--- Running PyInstaller ---"
pyinstaller rawspeak.spec --noconfirm

echo "--- Preparing DMG staging ---"
mkdir -p dist/dmg
rm -rf dist/dmg/*
cp -R "dist/${APP_NAME}.app" dist/dmg/

echo "--- Creating DMG ---"
test -f "dist/${DMG_NAME}" && rm "dist/${DMG_NAME}"

create-dmg \
  --volname "${APP_NAME}" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 200 190 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 600 185 \
  "dist/${DMG_NAME}" \
  "dist/dmg/" \
  || true

if [ -f "dist/${DMG_NAME}" ]; then
  echo "==> DMG created: dist/${DMG_NAME}"
else
  ls dist/*.dmg 2>/dev/null && echo "==> DMG created (name may vary from create-dmg)" \
    || { echo "ERROR: DMG creation failed"; exit 1; }
fi
