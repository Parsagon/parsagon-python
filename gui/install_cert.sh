#!/usr/bin/env bash

set -euo pipefail

APP_CERT=$1
INSTALLER_CERT=$2
SECURE_PASSWORD=$3
KEYCHAIN_NAME="builder2"

# Decode the certificates and save to temporary files
echo "$APP_CERT" | base64 --decode > /tmp/certificate_app.p12
echo "$INSTALLER_CERT" | base64 --decode > /tmp/certificate_installer.p12

# Create a keychain
security list-keychains -d user -s login.keychain
security create-keychain -p "$SECURE_PASSWORD" "$KEYCHAIN_NAME"
# security default-keychain -s "$KEYCHAIN_NAME"

# Append temp keychain to the user domain
security list-keychains -d user -s "$KEYCHAIN_NAME" $(security list-keychains -d user | sed s/\"//g)

# Remove relock timeout
security set-keychain-settings "$KEYCHAIN_NAME"

# Unlock
security unlock-keychain -p "$SECURE_PASSWORD" "$KEYCHAIN_NAME"

# Import the certificates into the keychain
security import /tmp/certificate_app.p12 -k "$KEYCHAIN_NAME" -P "$SECURE_PASSWORD" -A -T /usr/bin/codesign -T /usr/bin/productbuild
security import /tmp/certificate_installer.p12 -k "$KEYCHAIN_NAME" -P "$SECURE_PASSWORD" -A -T /usr/bin/productbuild -T /usr/bin/codesign

# Set key partition list
# security set-key-partition-list -S apple-tool:,apple: -s -k "$SECURE_PASSWORD" "$KEYCHAIN_NAME"
security set-key-partition-list -S apple-tool:,apple:, -s -k $SECURE_PASSWORD -t private $KEYCHAIN_NAME
# security set-key-partition-list -S apple-tool:,apple:, -s -k $SECURE_PASSWORD -D "${IDENTITY_CERTIFICATE}" -t private $KEYCHAIN_NAME

# Add the keychain to the list of search keychains
# security list-keychains -s "$KEYCHAIN_NAME"
