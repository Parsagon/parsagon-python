#!/usr/bin/env bash

set -euo pipefail

APP_CERT="$1"
INSTALLER_CERT="$2"
CERT_PASSWORD="$3"
KEYCHAIN_NAME="builder"
KEYCHAIN_PASSWORD="$4"

# Decode the certificates and save to temporary files
echo "$APP_CERT" | base64 --decode > /tmp/certificate_app.p12
echo "$INSTALLER_CERT" | base64 --decode > /tmp/certificate_installer.p12

# Create a keychain
security list-keychains -d user -s login.keychain
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Append temp keychain to the user domain
security list-keychains -d user -s "$KEYCHAIN_NAME" $(security list-keychains -d user | sed s/\"//g)

# Remove relock timeout
security set-keychain-settings "$KEYCHAIN_NAME"

# Unlock
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Import the certificates into the keychain
security import /tmp/certificate_app.p12 -k "$KEYCHAIN_NAME" -P "$CERT_PASSWORD" -A -T /usr/bin/codesign -T /usr/bin/productbuild
security import /tmp/certificate_installer.p12 -k "$KEYCHAIN_NAME" -P "$CERT_PASSWORD" -A -T /usr/bin/productbuild -T /usr/bin/codesign

# Set key partition list
security set-key-partition-list -S apple-tool:,apple:, -s -k $KEYCHAIN_PASSWORD -t private $KEYCHAIN_NAME
