#!/bin/bash
cd "$(dirname "$0")"

echo "=== Updating BC Camping Bot ==="
echo ""

if [ ! -d ".git" ]; then
    echo "This folder wasn't installed with git, so auto-update won't work."
    echo "Re-download the ZIP from: https://github.com/decoyblaze/bc-camping-bot"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

git pull origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Update Complete ==="
    echo "You can close this window and launch the bot."
else
    echo ""
    echo "Update failed. Try re-downloading from:"
    echo "https://github.com/decoyblaze/bc-camping-bot"
fi

echo ""
read -p "Press Enter to close..."
