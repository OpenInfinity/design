#!/bin/sh
# Download Geist (SIL OFL 1.1) from the official Vercel release into .cache/geist.
set -eu
VERSION="${GEIST_VERSION:-v1.7.2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/.cache/geist"
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/geist.zip" "https://github.com/vercel/geist-font/releases/download/$VERSION/geist-font-$VERSION.zip"
unzip -q "$TMP/geist.zip" -d "$TMP/x"
mkdir -p "$DEST"
cp "$TMP"/x/geist-font/Geist/otf/*.otf "$TMP"/x/geist-font/GeistMono/otf/*.otf "$DEST"/ 2>/dev/null || cp "$TMP"/x/geist-font/Geist/otf/*.otf "$DEST"/
cp "$TMP/x/geist-font/OFL.txt" "$DEST/OFL.txt"
rm -rf "$TMP"
echo "Geist $VERSION -> $DEST"
