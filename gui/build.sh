#!/usr/bin/env bash

set -euo pipefail

SHOULD_SIGN="${1:-1}"
REUSE_VENV="${2:-0}"
KEYCHAIN_PROFILE="parsagon_notarization"

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

  xcrun notarytool store-credentials "$KEYCHAIN_PROFILE" --apple-id "$DEV_EMAIL" --team-id "$TEAM_ID" --password "$APP_SPECIFIC_PASSWORD"
fi

cd "$SRC_DIR"

# Virtual environment setup, cleaning old builds
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
  pip3 install pyinstaller==6.3.0
fi

# Generate/gui_env.py
VERSION=$(python "${GUI_DIR}/update_gui_env.py")

# Make the app
python3 -m PyInstaller \
    --name Parsagon \
    --icon "$GUI_DIR/macos.icns" \
    --windowed \
    --osx-bundle-identifier "com.parsagon.parsagon" \
    --add-data "$PARSAGON_DIR/highlights.js:." \
    --add-data "$GRAPHICS_DIR/*:graphics" \
    --clean ./parsagon/gui_entry.py

# Signing
if [ "$SHOULD_SIGN" -eq 1 ]; then
  codesign --deep --force --options=runtime --entitlements "$GUI_DIR/entitlements.plist" --sign "$APP_HASH" --timestamp ./dist/Parsagon.app

  if [ -d "/tmp/parsagon" ]; then
    rm -rf "/tmp/parsagon"
  fi
  mkdir -p /tmp/parsagon

  ditto ../src/dist /tmp/parsagon/
  productbuild --identifier "com.parsagon.parsagon" --sign "$INSTALLER_HASH" --timestamp --root /tmp/parsagon /Applications "./dist/Parsagon_Installer_v${VERSION}.pkg"

  # Notarize the app
  xcrun notarytool submit "./dist/Parsagon_Installer_v${VERSION}.pkg" --keychain-profile "$KEYCHAIN_PROFILE" --wait

  # Staple the notarization ticket
  xcrun stapler staple "./dist/Parsagon_Installer_v${VERSION}.pkg"
fi

if [ -n "${GITHUB_ENV-}" ]; then
  echo "VERSION=$VERSION" >> $GITHUB_ENV
fi

