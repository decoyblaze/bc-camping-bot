"""Desktop notifications for booking results (macOS)."""

import subprocess


def notify(title: str, message: str):
    """Send a macOS notification."""
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}" sound name "Glass"',
            ],
            check=False,
            timeout=5,
        )
    except Exception:
        pass
