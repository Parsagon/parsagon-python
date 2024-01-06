#!/usr/bin/env bash

set -euo pipefail

APP_CERT=$1
INSTALLER_CERT=$2
SECURE_PASSWORD=$3
KEYCHAIN_NAME="builder"

# Decode the certificates and save to temporary files
echo "$APP_CERT" | base64 --decode > /tmp/certificate_app.p12
echo "$INSTALLER_CERT" | base64 --decode > /tmp/certificate_installer.p12

# Create a keychain
security create-keychain -p "$SECURE_PASSWORD" "$KEYCHAIN_NAME"
security default-keychain -s "$KEYCHAIN_NAME"
security unlock-keychain -p "$SECURE_PASSWORD" "$KEYCHAIN_NAME"

# Import the certificates into the keychain
security import /tmp/certificate_app.p12 -k "$KEYCHAIN_NAME" -P "$SECURE_PASSWORD" -T /usr/bin/codesign
security import /tmp/certificate_installer.p12 -k "$KEYCHAIN_NAME" -P "$SECURE_PASSWORD" -T /usr/bin/codesign

# Set key partition list
security set-key-partition-list -S apple-tool:,apple: -s -k "$SECURE_PASSWORD" "$KEYCHAIN_NAME"

# Add the keychain to the list of search keychains
security list-keychains -s "$KEYCHAIN_NAME"
