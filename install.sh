#!/bin/bash
# BC Camping Bot — one-command installer for macOS
# Usage: curl -sL <url> | bash  OR  ./install.sh

set -e

INSTALL_DIR="$HOME/bc-camping-bot"
VENV="$INSTALL_DIR/.venv"

echo "=== BC Camping Bot Installer ==="
echo ""

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found. Installing via Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "Error: Need Homebrew or Python 3. Install from https://brew.sh"
        exit 1
    fi
    brew install python3
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Found Python $PYVER"

# Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing install..."
    cd "$INSTALL_DIR"
    git pull
else
    if [ -d "$INSTALL_DIR" ]; then
        echo "Directory exists but isn't a git repo. Using existing files."
    else
        echo "This installer expects the bc-camping-bot folder at $INSTALL_DIR"
        echo "Copy the project folder there first, or clone it."
        exit 1
    fi
fi

cd "$INSTALL_DIR"

# Create venv
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"
pip install --upgrade pip -q
pip install -e "." -q

# Install Playwright browsers
echo "Installing browser (this may take a minute)..."
playwright install chromium

# Create launcher script
LAUNCHER="$INSTALL_DIR/launch.command"
cat > "$LAUNCHER" << 'LAUNCH_EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 -m bc_camping_bot.gui
LAUNCH_EOF
chmod +x "$LAUNCHER"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To launch: double-click launch.command in $INSTALL_DIR"
echo "Or run:    cd $INSTALL_DIR && source .venv/bin/activate && camping-bot"
echo ""
