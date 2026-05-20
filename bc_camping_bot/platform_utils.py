"""Cross-platform utilities — macOS + Windows."""

import os
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def chrome_user_data_dir() -> Path:
    if IS_WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return local / "Google" / "Chrome" / "User Data"
    return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def is_chrome_running() -> bool:
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return "chrome.exe" in result.stdout.lower()
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False


def quit_chrome(log=None):
    if log:
        log("Closing Chrome (will reopen when done)...")
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/IM", "chrome.exe"],
                        capture_output=True, timeout=10)
    else:
        subprocess.run(
            ["osascript", "-e", 'tell application "Google Chrome" to quit'],
            capture_output=True, timeout=10,
        )
    for _ in range(30):
        if not is_chrome_running():
            return
        time.sleep(0.2)
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                        capture_output=True, timeout=10)
        for _ in range(15):
            if not is_chrome_running():
                return
            time.sleep(0.2)
    raise RuntimeError("Chrome did not quit in time")


def reopen_chrome():
    if IS_WINDOWS:
        subprocess.Popen(
            ["cmd", "/c", "start", "chrome"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["open", "-a", "Google Chrome"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def send_notification(title: str, message: str):
    if IS_WINDOWS:
        try:
            from plyer import notification as plyer_notif
            plyer_notif.notify(title=title, message=message, timeout=10)
            return
        except ImportError:
            pass
        try:
            ps = (
                '[Windows.UI.Notifications.ToastNotificationManager, '
                'Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; '
                '$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0); '
                '$text = $xml.GetElementsByTagName("text"); '
                f'$text[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null; '
                f'$text[1].AppendChild($xml.CreateTextNode("{message}")) | Out-Null; '
                '$notifier = [Windows.UI.Notifications.ToastNotificationManager]'
                '::CreateToastNotifier("BC Camping Bot"); '
                '$notifier.Show([Windows.UI.Notifications.ToastNotification]::new($xml))'
            )
            subprocess.run(["powershell", "-Command", ps],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    else:
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}" sound name "Glass"'],
                check=False, timeout=5,
            )
        except Exception:
            pass


def format_day(dt, fmt: str) -> str:
    """Cross-platform strftime — handles %-d (macOS/Linux) vs %#d (Windows)."""
    if IS_WINDOWS:
        return dt.strftime(fmt.replace("%-d", "%#d"))
    return dt.strftime(fmt)
