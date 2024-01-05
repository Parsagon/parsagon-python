#!/usr/bin/env bash

set -euo pipefail

SHOULD_SIGN="${1:-1}"
REUSE_VENV="${2:-0}"

GUI_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
REPO_DIR="$(dirname "$GUI_DIR")"
SRC_DIR="$REPO_DIR/src"
PARSAGON_DIR="$SRC_DIR/parsagon"
GRAPHICS_DIR="$PARSAGON_DIR/graphics"

if [ -n "${VIRTUAL_ENV-}" ]; then
    echo "A virtual environment is currently active."
    echo "Please deactivate the virtual environment before running this script."
    exit 1
fi

if [ "$SHOULD_SIGN" -eq 1 ]; then
  echo "Environment variables:"
  echo "App hash: $APP_HASH"
  echo "Installer hash: $INSTALLER_HASH"
  echo "Dev email: $DEV_EMAIL"
  echo "Team ID: $TEAM_ID"
fi

cd "$SRC_DIR"

rm -f *.spec && rm -rf dist/ build/

if [ "$REUSE_VENV" -eq 0 ]; then
  rm -rf venv/
  python3 -m venv venv
fi

source venv/bin/activate

if [ "$REUSE_VENV" -eq 0 ]; then
  pip3 install ..
  pip3 uninstall -y parsagon
  pip3 install PyQt6==6.6.1
  pip3 install pyinstaller
fi

python3 -m PyInstaller \
    --name Parsagon \
    --icon "$GUI_DIR/macos.icns" \
    --onefile \
    --windowed \
    --osx-bundle-identifier "com.parsagon.parsagon" \
    --add-data "$PARSAGON_DIR/highlights.js:." \
    --add-data "$GRAPHICS_DIR/*:graphics" \
    --clean ./parsagon/gui_entry.py

if [ "$SHOULD_SIGN" -eq 1 ]; then
  codesign --deep --force --options=runtime --entitlements "$GUI_DIR/entitlements.plist" --sign "$APP_HASH" --timestamp ./dist/Parsagon.app

  if [ -d "/tmp/parsagon" ]; then
    rm -rf "/tmp/parsagon"
  fi
  mkdir /tmp/parsagon

  ditto ../src/dist /tmp/parsagon/
  rm /tmp/parsagon/Parsagon
  productbuild --identifier "com.parsagon.parsagon.pkg" --sign "$INSTALLER_HASH" --timestamp --root /tmp/parsagon /Applications ./dist/Parsagon.pkg

  xcrun altool --notarize-app --primary-bundle-id "com.parsagon.parsagon" --username="$DEV_EMAIL" --password "@keychain:Developer-altool" --file ./dist/Parsagon.pkg --asc-provider "$TEAM_ID"
fi
