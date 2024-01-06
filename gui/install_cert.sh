#!/usr/bin/env bash

set -euo pipefail

# Usage: ./install_cert.sh [Base64 Encoded Certificate] [Certificate Password] [Keychain Password] [Keychain Name]

ENCODED_CERT=$1
CERT_PASSWORD=$2
KEYCHAIN_PASSWORD=$3
KEYCHAIN_NAME=$4

# Decode the certificate and save to a temporary file
echo "$ENCODED_CERT" | base64 --decode > /tmp/certificate.p12

# Create a keychain
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
security default-keychain -s "$KEYCHAIN_NAME"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Import the certificate into the keychain
security import /tmp/certificate.p12 -k "$KEYCHAIN_NAME" -P "$CERT_PASSWORD" -T /usr/bin/codesign

# Set key partition list
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Add the keychain to the list of search keychains
security list-keychains -s "$KEYCHAIN_NAME"
