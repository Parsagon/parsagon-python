#!/usr/bin/env bash

set -euo pipefail

# Make sure CODESIGN_ID_NAME is set e.g: "Apple Development: Name (TeamID)"

echo "Environment variables:"
set -x
echo "$APP_HASH"
echo "$INSTALLER_HASH"
echo "$DEV_EMAIL"
echo "$TEAM_ID"
set +x

# Get directory of this bash script
GUI_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Get root repo dir (parent of GUI dir)
REPO_DIR="$(dirname "$GUI_DIR")"

cd "$REPO_DIR/src"

rm -f *.spec && rm -rf dist/ build/

python3 -m PyInstaller \
    --name Parsagon \
    --icon "$GUI_DIR/macos.icns" \
    --onefile \
    --windowed \
    --osx-bundle-identifier "com.parsagon.parsagon" \
    --add-data "parsagon/highlights.js:." \
    --add-data "parsagon/loading.gif:." \
    --add-data "parsagon/send@2x.png:." \
    --add-data "parsagon/send.png:." \
    --add-data "parsagon/callout_arrow@2x.png:." \
    --add-data "parsagon/callout_arrow.png:." \
    --clean ./parsagon/gui.py

codesign --deep --force --options=runtime --entitlements "$GUI_DIR/entitlements.plist" --sign "$APP_HASH" --timestamp ./dist/Parsagon.app

if [ -d "/tmp/parsagon" ]; then
  rm -rf "/tmp/parsagon"
fi
mkdir /tmp/parsagon

ditto ../src/dist /tmp/parsagon/
rm /tmp/parsagon/Parsagon
productbuild --identifier "com.parsagon.parsagon.pkg" --sign "$INSTALLER_HASH" --timestamp --root /tmp/parsagon /Applications ./dist/Parsagon.pkg

xcrun altool --notarize-app --primary-bundle-id "com.parsagon.parsagon" --username="$DEV_EMAIL" --password "@keychain:Developer-altool" --file ./dist/Parsagon.pkg --asc-provider "$TEAM_ID"
