#!/bin/bash
# BC Camping Bot — one-time setup
# Run this once after copying the folder to your machine:
#   cd bc-camping-bot && ./setup.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

echo "=== BC Camping Bot Setup ==="

if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found."
    if command -v brew &>/dev/null; then
        echo "Installing via Homebrew..."
        brew install python3
    else
        echo "Install Python 3 from https://python.org or via Homebrew (https://brew.sh)"
        exit 1
    fi
fi

echo "Python: $(python3 --version)"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "Installing dependencies..."
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -e "$DIR" -q

echo "Installing browser (one-time, may take a minute)..."
"$VENV/bin/playwright" install chromium

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To launch:  ./launch.command"
echo "   or run:  .venv/bin/camping-bot"
echo ""
