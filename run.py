"""Entry point for PyInstaller builds."""

import os
from pathlib import Path

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path.home() / ".bc-camping-bot" / "browsers"),
)

from bc_camping_bot.gui import main

if __name__ == "__main__":
    main()
