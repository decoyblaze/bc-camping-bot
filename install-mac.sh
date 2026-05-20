#!/bin/bash

echo ""
echo "=== Installing BC Camping Bot ==="
echo ""

echo "Downloading latest release..."
DOWNLOAD_URL=$(curl -s https://api.github.com/repos/decoyblaze/bc-camping-bot/releases/latest | grep "browser_download_url.*macOS" | cut -d '"' -f 4)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Error: Could not find latest release."
    echo "Check https://github.com/decoyblaze/bc-camping-bot/releases"
    exit 1
fi

TMPDIR=$(mktemp -d)
curl -L "$DOWNLOAD_URL" -o "$TMPDIR/app.zip"

echo "Installing to Applications..."
unzip -q "$TMPDIR/app.zip" -d "$TMPDIR"
rm -rf "/Applications/BC Camping Bot.app" 2>/dev/null
mv "$TMPDIR/BC Camping Bot.app" /Applications/
xattr -cr "/Applications/BC Camping Bot.app"
rm -rf "$TMPDIR"

echo ""
echo "=== BC Camping Bot installed! ==="
echo ""
echo "Launching..."
open "/Applications/BC Camping Bot.app"
