#!/bin/bash
set -e

echo ""
echo "=== Installing BC Camping Bot ==="
echo ""

# Download latest release
echo "Downloading latest release..."
DOWNLOAD_URL=$(curl -s https://api.github.com/repos/decoyblaze/bc-camping-bot/releases/latest | grep "browser_download_url.*macOS" | cut -d '"' -f 4)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Error: Could not find latest release. Check https://github.com/decoyblaze/bc-camping-bot/releases"
    exit 1
fi

TMPDIR=$(mktemp -d)
curl -L "$DOWNLOAD_URL" -o "$TMPDIR/app.zip"

# Unzip and install
echo "Installing to Applications..."
unzip -q "$TMPDIR/app.zip" -d "$TMPDIR"

if [ -d "/Applications/BC Camping Bot.app" ]; then
    rm -rf "/Applications/BC Camping Bot.app"
fi
mv "$TMPDIR/BC Camping Bot.app" /Applications/
xattr -cr "/Applications/BC Camping Bot.app"

echo "Signing app (required for Apple Silicon)..."
find "/Applications/BC Camping Bot.app" -type f \( -name "*.so" -o -name "*.dylib" -o -name "*.o" \) | while read -r f; do
    codesign --force -s - "$f" 2>/dev/null || true
done
codesign --force -s - "/Applications/BC Camping Bot.app/Contents/MacOS/BC Camping Bot"
codesign --force --deep -s - "/Applications/BC Camping Bot.app"

rm -rf "$TMPDIR"

echo ""
echo "=== BC Camping Bot installed! ==="
echo ""
echo "Launching..."
open "/Applications/BC Camping Bot.app"
