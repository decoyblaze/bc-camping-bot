"""Auto-install Playwright Chromium if not present."""

import subprocess
import sys


def ensure_browsers_installed() -> bool:
    """Check if Playwright Chromium is installed, install if needed. Returns True if ready."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.executable_path
        return True
    except Exception:
        pass

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            timeout=300,
        )
        return True
    except Exception:
        return False
