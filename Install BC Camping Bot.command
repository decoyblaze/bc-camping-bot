#!/bin/bash
# Double-click this file to install and launch BC Camping Bot.
# It removes the macOS quarantine flag so the app opens without issues.

cd "$(dirname "$0")"

echo "Installing BC Camping Bot..."
xattr -cr "BC Camping Bot.app" 2>/dev/null

# Move to Applications if not already there
if [ ! -d "/Applications/BC Camping Bot.app" ]; then
    echo "Moving to Applications folder..."
    cp -R "BC Camping Bot.app" /Applications/
    xattr -cr "/Applications/BC Camping Bot.app" 2>/dev/null
fi

echo "Launching BC Camping Bot..."
open "/Applications/BC Camping Bot.app"
echo ""
echo "Done! You can close this window."
